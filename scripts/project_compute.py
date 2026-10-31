"""Compute and disk projections for the full design, from the smoke test and the calibration runs.

Reads results_dir/tierA/wp1_smoke/summary.json and results_dir/tierA/wp1_calibration/calibration.json,
counts eligible (instrument, period) pairs from the processed Tier A data (availability only), and
writes reports_dir/smoke_and_projections.md plus results_dir/tierA/wp1_projections.json.

Usage: uv run python scripts/project_compute.py
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import timedelta

import numpy as np

from lpstgp.config import load_paths, load_settings
from lpstgp.data import quality, schema
from lpstgp.data.tier_a import git_revision, load_universe
from lpstgp.splits import is_eligible, periods_from_settings

SEEDS = 30
BUDGETS = (10_000, 25_000, 50_000)  # requested fitness evaluations per run
POPULATION = 500
CLUSTER = ((64, 0.9), (128, 0.9))  # cores per node, assumed parallel efficiency
WP3_OVERHEAD = (
    0.05  # extra evaluations for maintenance evidence (knock-out) and gates, arms 4 and 7
)
CONFIGS = (  # (configuration, cost class, overhead)
    ("Arm 2a: whole LLM strategies as Boolean terminals", "terminal", 0.0),
    ("Arm 2b: their signal series as terminals", "terminal", 0.0),
    ("Arm 2c: parameterised operators", "cross", 0.0),
    ("Arm 3: frozen LLM-authored library", "cross", 0.0),
    ("Arm 4-grow: maintained, growth only", "cross", WP3_OVERHEAD),
    ("Arm 4-full: maintained, grow/prune/refine", "cross", WP3_OVERHEAD),
    ("Arm 5: fixed grammar + LLM tree operators", "cross", 0.0),
    ("Arm 6: expert library (this seed library)", "cross", 0.0),
    ("Arm 7a: ALPHAS2-style distillation", "cross", WP3_OVERHEAD),
    ("Arm 7b: EvoQuantLab-style terminal lifecycle", "terminal", WP3_OVERHEAD),
    ("Baseline: GP with TA terminals", "terminal", 0.0),
    ("Baseline: DC-GP", "terminal", 0.0),
    ("Baseline: ActTrade", "terminal", 0.0),
    ("Baseline: LLM code-variation loop", "cross", 0.0),
)
SELECTION_ONLY = (
    "Arm 1: best of ~30 whole LLM strategies",
    "LLQ pipeline (portfolio GA)",
    "Buy-and-hold",
)


def eligible_pairs(paths, settings) -> dict[str, int]:
    periods = periods_from_settings(settings)
    split = settings["splits"]
    last_day = periods[-1].test_end - timedelta(days=1)
    counts: dict[str, int] = defaultdict(int)
    for inst in load_universe():
        path = paths.tier_dir("A") / "processed" / f"{inst.id}.parquet"
        frame = schema.read_frame(path)
        dates = (
            frame["date"].to_numpy().astype("datetime64[D]")[np.isfinite(frame["close"].to_numpy())]
        )
        first = min(dates[0].astype(object), periods[0].fit_start)
        expected = quality.expected_sessions(inst.calendar, inst.qa_calendar, first, last_day)
        n = sum(
            is_eligible(
                dates, expected, p, split["lookback_max_bars"], split["min_session_coverage"]
            )
            for p in periods
        )
        counts[inst.calendar] += int(n)
    return dict(counts)


def gb(x: float) -> str:
    return f"{x / 1e9:.2f}"


def main() -> None:
    paths, settings = load_paths(), load_settings()
    smoke = json.loads((paths.results_dir / "tierA" / "wp1_smoke" / "summary.json").read_text())
    cal = json.loads(
        (paths.results_dir / "tierA" / "wp1_calibration" / "calibration.json").read_text()
    )
    pairs = eligible_pairs(paths, settings)

    # ------------------------------------------------------------------ measured inputs
    seed_smoke_ms = statistics.fmean(r["per_requested_ms"] for r in smoke["runs"])
    conv_smoke_ms = statistics.fmean(r["per_requested_ms"] for r in cal["conventional"])
    terminal_ratio = conv_smoke_ms / seed_smoke_ms
    single = cal["single_worker"]
    concurrent = cal["concurrent"]
    conc_ms = statistics.fmean(r["per_requested_ms"] for r in concurrent["runs"])
    workers = concurrent["workers"]
    speedup = workers * single["per_requested_ms"] / conc_ms
    full = cal.get("full_budget")
    central_ms = full["per_requested_ms"] if full else single["per_requested_ms"]
    high_ms = single["per_requested_ms"]  # small budget, cold cache: an upper bound per evaluation
    crypto_factor = (504 + 730) / (504 + 504)  # 7-day fit windows have ~45% more bars than 504
    smoke_record = statistics.fmean(r["record_bytes"] for r in smoke["runs"])
    per_gen_bytes = (full["record_bytes"] - smoke_record) / (50 - 10) if full else smoke_record / 11
    rss = statistics.fmean(r["peak_rss_mb"] for r in concurrent["runs"])
    cache_mb = statistics.fmean(r["cache_mb"] for r in concurrent["runs"])

    def record_bytes(budget: int) -> float:
        generations = budget / POPULATION - 1
        return smoke_record + (generations - 10) * per_gen_bytes

    def scenario(
        name: str, units: dict[str, float], per_eval_factor: float = 1.0, runs_per_unit: float = 1.0
    ):
        rows = []
        for budget in BUDGETS:
            core_s = {"central": 0.0, "high": 0.0}
            runs = 0.0
            evals = 0.0
            for _, cost_class, overhead in CONFIGS:
                cls = terminal_ratio if cost_class == "terminal" else 1.0
                for calendar, n in units.items():
                    length = crypto_factor if calendar == "7day" else 1.0
                    n_runs = n * SEEDS * runs_per_unit
                    e = n_runs * budget * (1 + overhead)
                    runs += n_runs
                    evals += e
                    for key, ms in (("central", central_ms), ("high", high_ms)):
                        core_s[key] += e * ms / 1000 * cls * length * per_eval_factor
            hours = {k: v / 3600 for k, v in core_s.items()}
            rows.append(
                {
                    "scenario": name,
                    "budget": budget,
                    "runs": runs,
                    "evaluations": evals,
                    "core_hours_central": hours["central"],
                    "core_hours_high": hours["high"],
                    "laptop_days_central": hours["central"] / speedup / 24,
                    "laptop_days_high": hours["high"] / speedup / 24,
                    **{
                        f"node{cores}_days_central": hours["central"] / (cores * eff) / 24
                        for cores, eff in CLUSTER
                    },
                    "disk_bytes": runs * record_bytes(budget),
                }
            )
        return rows

    tier_a = scenario("Tier A (31 instruments)", pairs)
    tier_b1 = scenario("Tier B option 1: one rule per stock", {"business": 100 * 18})
    tier_b2 = scenario(
        "Tier B option 2: one rule per market, pooled", {"business": 4 * 18}, per_eval_factor=25.0
    )
    rows = tier_a + tier_b1 + tier_b2

    # ------------------------------------------------------------------ report
    def table(rows_):
        out = [
            "| Scenario | Evaluations / run | Runs | Evaluations | Core-hours (central / high) | Laptop days (central / high) | 64-core node days | 128-core node days | Disk for run records (GB) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for r in rows_:
            out.append(
                f"| {r['scenario']} | {r['budget']:,} | {r['runs']:,.0f} | {r['evaluations']:.2e} | "
                f"{r['core_hours_central']:,.0f} / {r['core_hours_high']:,.0f} | "
                f"{r['laptop_days_central']:,.1f} / {r['laptop_days_high']:,.1f} | "
                f"{r['node64_days_central']:,.1f} | {r['node128_days_central']:,.1f} | {gb(r['disk_bytes'])} |"
            )
        return "\n".join(out)

    micro = sorted(cal["micro_benchmarks"], key=lambda r: -r["ms"])
    by_domain: dict[str, list[float]] = defaultdict(list)
    for r in cal["micro_benchmarks"]:
        by_domain[r["domain"]].append(r["ms"])
    smoke_rows = "\n".join(
        f"| {r['instrument']} | {r['seed']} | {r['wall_clock_s']:.1f} | {r['requested_evaluations']:,} | "
        f"{r['unique_evaluations']:,} | {r['per_requested_ms']:.1f} | {r['per_unique_ms']:.1f} | "
        f"{r['unique_ms_quantiles']['p50']:.1f} / {r['unique_ms_quantiles']['p90']:.1f} / {r['unique_ms_quantiles']['p99']:.0f} | "
        f"{r['cold_per_unique_ms']:.0f} / {r['warm_per_unique_ms']:.1f} | {r['cache_hit_rate']:.2f} | "
        f"{r['peak_rss_mb']:.0f} | {r['record_bytes'] / 1024:.0f} |"
        for r in smoke["runs"]
    )
    curve = ""
    if full:
        picks = [g for g in full["generation_curve"] if g["gen"] in (0, 1, 10, 25, 50)]
        curve = "\n".join(
            f"| {g['gen']} | {g['new_unique']} | {1000 * g['eval_s'] / max(g['new_unique'], 1):.1f} | "
            f"{g['mean_nodes']:.1f} | {g['mean_size_w']:.1f} | {g['cache_hit_rate']:.2f} | {g['elapsed_s']:.0f} |"
            for g in picks
        )
    lines = [
        "# WP1 smoke test, calibration and compute/disk projections",
        "",
        f"Generated from code `{git_revision()}`. All runs use P01 training data (fit 2005-07..2007-06) and its "
        "validation year (2007-07..2008-06) only; P01's test year is sealed. Machine: Apple M1 (4 performance + "
        "4 efficiency cores), 16 GB RAM, one BLAS/numba thread per run.",
        "",
        "## Smoke test (as specified)",
        "",
        f"S&P 500 and EUR/USD, P01, seed library (28 cross-domain operators + core), population {smoke['population']} x "
        f"{smoke['generations']} generations, 2 seeds per asset, {smoke['workers']} parallel workers: "
        f"**{len(smoke['runs'])} runs in {smoke['elapsed_s']:.0f} s**.",
        "",
        "| Asset | Seed | Wall-clock (s) | Requested evals | Unique evals | ms / requested eval | ms / unique eval | Unique eval ms p50 / p90 / p99 | Cold (gen 0) / warm ms per unique eval | Subtree-cache hit rate | Peak RSS (MB) | Run record (KB) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        smoke_rows,
        "",
        f"- **Runtime per fitness evaluation:** {seed_smoke_ms:.1f} ms per requested evaluation on average "
        f"({statistics.fmean(r['per_unique_ms'] for r in smoke['runs']):.1f} ms per unique, i.e. not-yet-seen, rule). "
        "A unique evaluation costs ~70 ms while the subtree cache is cold (generation 0) and ~9-13 ms once warm; "
        "requested evaluations are cheaper because repeated rules are not re-evaluated.",
        f"- **Disk use of the run:** {smoke['records_bytes_total'] / 1024:.0f} KB of run records for the 4 runs "
        f"(~{smoke_record / 1024:.0f} KB per run: summaries and the hall of fame only, no populations). The subtree "
        f"cache is in memory only; the numba compilation cache is {smoke['numba_cache_bytes'] / 2**20:.1f} MB in the "
        "local clone (git-ignored, outside Box).",
        "",
        "## Calibration",
        "",
        f"- **Conventional (TA/DC) library**, same configuration: {conv_smoke_ms:.1f} ms per requested evaluation, "
        f"i.e. {terminal_ratio:.2f}x the cross-domain library.",
        f"- **Single worker** (smoke size, alone): {single['per_requested_ms']:.1f} ms per requested evaluation, "
        f"peak RSS {single['peak_rss_mb']:.0f} MB.",
        f"- **{workers} concurrent workers:** {conc_ms:.1f} ms per requested evaluation each, i.e. a throughput "
        f"speed-up of {speedup:.1f}x on this laptop (4 of the 8 cores are efficiency cores); "
        f"{rss:.0f} MB peak RSS per worker (subtree cache ~{cache_mb:.0f} MB).",
    ]
    if full:
        lines += [
            f"- **Full-budget run** (SPX, population 500 x 50 generations = {full['requested_evaluations']:,} "
            f"requested, {full['unique_evaluations']:,} unique evaluations): {full['wall_clock_s'] / 60:.1f} min, "
            f"{full['per_requested_ms']:.1f} ms per requested and {full['per_unique_ms']:.1f} ms per unique "
            f"evaluation, peak RSS {full['peak_rss_mb']:.0f} MB, record {full['record_bytes'] / 1024:.0f} KB.",
            "",
            "| Generation | New unique evals | ms per unique eval | Mean nodes (both trees) | Mean weighted size | Cache hit rate | Elapsed (s) |",
            "|---:|---:|---:|---:|---:|---:|---:|",
            curve,
        ]
    lines += [
        "",
        "Slowest operator calls (P01 FIT arrays of "
        f"{cal['micro_benchmarks'][0]['bars']} bars; each subtree is computed once per run thanks to memoisation):",
        "",
        "| Contract | Parameters | ms per call |",
        "|---|---|---:|",
        *[f"| `{r['key']}` | {r['params']} | {r['ms']:.1f} |" for r in micro[:12]],
        "",
        "Median ms per call by domain: "
        + "; ".join(f"{d} {statistics.median(v):.2f}" for d, v in sorted(by_domain.items())),
        "",
        "## Projections for the full design",
        "",
        "**Design counted.** The GP configurations, each run on every eligible (instrument, period) pair x 30 seeds:",
        "",
        *[
            f"- {name} (cost class: {cls}{', +5% evaluations for maintenance/gates' if oh else ''})"
            for name, cls, oh in CONFIGS
        ],
        "",
        "Selection-only items need negligible compute: " + "; ".join(SELECTION_ONLY) + ".",
        "",
        "**Assumptions and measured inputs.**",
        "",
        f"- Eligible Tier A pairs: {sum(pairs.values())} ({pairs.get('business', 0)} business-day, {pairs.get('7day', 0)} crypto); periods P01-P18.",
        f"- Cost per requested evaluation: central {central_ms:.1f} ms (full-budget run, caches warm), high {high_ms:.1f} ms (small budget, cold caches); conventional/terminal-only configurations x{terminal_ratio:.2f}; crypto x{crypto_factor:.2f} (longer fit windows).",
        "- Sandboxes always hold 504 warm-up + fit bars, so the cost per evaluation does not grow across periods.",
        f"- Laptop: measured {speedup:.1f}x throughput with {workers} workers. Cluster nodes: per-core speed of one M1 performance core, 90% parallel efficiency (assumption).",
        f"- Disk: run records of {smoke_record / 1024:.0f} KB at 11 generations plus {per_gen_bytes / 1024:.1f} KB per further generation (population {POPULATION}); gzip would cut this ~5x.",
        "- Tier B option 1: 100 stocks x 18 periods (upper bound; delisted names shorten later periods). Option 2: 4 markets x 18 periods, each evaluation scores 25 stocks (25x the cost per evaluation, 25x fewer runs).",
        "- Not included: LLM tokens and API time (WP3), re-running arms for the cost sweep (re-evaluating fixed rules at 0.5/1/2/3x costs is negligible; re-evolving them would multiply the affected rows by 4).",
        "",
        table(rows),
        "",
        "**Tier B options compared.** Total compute is about the same (both evaluate 1,800 stock-periods per "
        "configuration and seed), but option 2 has 25x fewer runs, 25x longer runs, 25x fewer run records and "
        "25x fewer LLM maintenance cycles in WP3. Memory per pooled run grows with the number of stocks: keeping "
        f"the per-stock subtree cache at its current size (~{cache_mb:.0f} MB) needs ~{(rss + 25 * cache_mb) / 1024:.1f} GB "
        f"per pooled run, so about {int(14 * 1024 // (rss + 25 * cache_mb))} concurrent pooled runs fit in 16 GB "
        "(set `cache_mb` accordingly, it is 512 MB per run by default).",
        "",
        "**Sensitivity to the budget definition (open for WP2).** In the full-budget run only "
        + (
            f"{full['unique_evaluations']:,} of {full['requested_evaluations']:,}"
            if full
            else "a minority of"
        )
        + " requested evaluations were new rules: the population converges and repeated rules are served from the "
        "fitness cache, which is why the central cost is low. If the matched budget is defined in unique evaluations, "
        "or WP2 adds diversity control so that most evaluations are new rules, the cost per budget unit approaches "
        + (
            f"the per-unique cost ({full['per_unique_ms']:.1f} ms, ~{full['per_unique_ms'] / central_ms:.1f}x the central "
            "figure): multiply the central core-hours accordingly."
            if full
            else "the per-unique cost."
        )
        + " Projected disk use also matters for storage: 10-60 GB of uncompressed run records would not fit "
        "comfortably on this laptop (22 GB free) and should go, compressed and sharded, to cluster storage (WP4).",
        "",
    ]
    report = "\n".join(lines)
    out = paths.reports_dir / "smoke_and_projections.md"
    out.write_text(report, encoding="utf-8")
    (paths.results_dir / "tierA" / "wp1_projections.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "pairs": pairs,
                    "central_ms": central_ms,
                    "high_ms": high_ms,
                    "terminal_ratio": terminal_ratio,
                    "speedup": speedup,
                    "workers": workers,
                    "per_gen_bytes": per_gen_bytes,
                    "smoke_record_bytes": smoke_record,
                },
                "rows": rows,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"wrote {out}")
    for r in rows:
        print(
            f"{r['scenario'][:45]:45s} {r['budget']:>6,} evals/run: {r['runs']:>9,.0f} runs, {r['core_hours_central']:>9,.0f} core-h, "
            f"laptop {r['laptop_days_central']:>7,.1f} d, 128-core {r['node128_days_central']:>5,.1f} d, disk {gb(r['disk_bytes'])} GB"
        )


if __name__ == "__main__":
    main()
