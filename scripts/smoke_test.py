"""WP1 smoke test: the STGP on 2 Tier-A assets x 1 training window, small budget.

Default: S&P 500 and EUR/USD on P01 (fit 2005-07..2007-06, validation 2007-07..2008-06; the test
year is sealed), seed library, population 200 x 10 generations, 2 seeds per asset, 4 workers.
Records go to results_dir/tierA/<experiment>/; a summary (runtime per evaluation, disk use) is
written next to them as summary.json.

Usage: uv run python scripts/smoke_test.py [--library seed] [--population 200] [--generations 10]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from lpstgp.config import REPO_ROOT, load_paths, load_settings
from lpstgp.runner import RunTask, configs_from_settings, run_many


def directory_bytes(path: Path, pattern: str = "*") -> int:
    return sum(p.stat().st_size for p in path.rglob(pattern) if p.is_file())


def summarise(record: dict) -> dict:
    gens = record["generations"]
    cold = gens[0]
    warm_s = sum(g["eval_s"] for g in gens[1:])
    warm_n = sum(g["new_unique"] for g in gens[1:])
    best = record["hall_of_fame"][record["selected"]]
    return {
        "run": record["run_id"],
        "instrument": record["instruments"][0],
        "library": record["library"]["name"],
        "seed": record["seed"],
        "wall_clock_s": record["wall_clock_s"],
        "setup_s": record["setup_s"],
        "requested_evaluations": record["budget"]["requested_evaluations"],
        "unique_evaluations": record["budget"]["unique_evaluations"],
        "per_requested_ms": record["timings"]["per_requested_evaluation_ms"],
        "per_unique_ms": record["timings"]["per_unique_evaluation_ms"],
        "unique_ms_quantiles": record["timings"]["unique_evaluation_ms"],
        "cold_per_unique_ms": 1000 * cold["eval_s"] / max(cold["new_unique"], 1),
        "warm_per_unique_ms": 1000 * warm_s / max(warm_n, 1),
        "cache_hit_rate": record["cache"]["hit_rate"],
        "cache_mb": record["cache"]["bytes"] / 2**20,
        "peak_rss_mb": record["peak_rss_mb"],
        "record_bytes": record["record_bytes"],
        "mean_nodes_last_gen": gens[-1]["mean_nodes"],
        "selected_fit_fitness": best["fit"]["fitness"],
        "selected_validation_fitness": best.get("validation", {}).get("fitness"),
        "hof_no_trade": sum(
            all(c.get("no_trade", False) for c in h["fit"]["instruments"].values())
            for h in record["hall_of_fame"]
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instruments", default="SPX,EURUSD")
    parser.add_argument("--period", default="P01")
    parser.add_argument("--library", default="seed")
    parser.add_argument("--population", type=int, default=200)
    parser.add_argument("--generations", type=int, default=10)
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--first-seed", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--experiment", default="wp1_smoke")
    args = parser.parse_args()

    paths, settings = load_paths(), load_settings()
    gp_cfg, fit_cfg = configs_from_settings(
        settings, population=args.population, generations=args.generations
    )
    tasks = [
        RunTask(args.experiment, args.library, (inst,), args.period, seed, gp_cfg, fit_cfg)
        for inst in args.instruments.split(",")
        for seed in range(args.first_seed, args.first_seed + args.seeds)
    ]
    started = time.perf_counter()
    records = run_many(tasks, args.workers, paths.results_dir)
    elapsed = time.perf_counter() - started
    runs = sorted((summarise(r) for r in records), key=lambda s: (s["instrument"], s["seed"]))
    out_dir = paths.results_dir / "tierA" / args.experiment
    numba_cache = directory_bytes(REPO_ROOT / "src", "*.nb[ic]")
    summary = {
        "experiment": args.experiment,
        "library": args.library,
        "period": args.period,
        "population": args.population,
        "generations": args.generations,
        "workers": args.workers,
        "elapsed_s": elapsed,
        "runs": runs,
        "per_requested_ms_mean": float(np.mean([r["per_requested_ms"] for r in runs])),
        "per_unique_ms_mean": float(np.mean([r["per_unique_ms"] for r in runs])),
        "records_bytes_total": int(sum(r["record_bytes"] for r in runs)),
        "numba_cache_bytes": numba_cache,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"{len(runs)} runs in {elapsed:.0f}s with {args.workers} workers")
    for r in runs:
        print(
            f"{r['instrument']:7s} seed {r['seed']}: {r['wall_clock_s']:6.1f}s wall, "
            f"{r['requested_evaluations']} req / {r['unique_evaluations']} unique evals, "
            f"{r['per_requested_ms']:.1f} ms/req, {r['per_unique_ms']:.1f} ms/unique "
            f"(cold {r['cold_per_unique_ms']:.1f}, warm {r['warm_per_unique_ms']:.1f}), "
            f"hit {r['cache_hit_rate']:.2f}, RSS {r['peak_rss_mb']:.0f} MB, record {r['record_bytes'] / 1024:.0f} KB"
        )
    print(
        f"records total {summary['records_bytes_total'] / 1024:.0f} KB; numba cache {numba_cache / 2**20:.1f} MB"
    )


if __name__ == "__main__":
    main()
