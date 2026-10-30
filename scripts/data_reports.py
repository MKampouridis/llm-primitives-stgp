"""Write the per-tier data reports (coverage, gaps, date ranges; counts only) to reports_dir.

Usage: uv run python scripts/data_reports.py
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from lpstgp.config import load_paths, load_settings
from lpstgp.data import manifest as mf
from lpstgp.data import quality, schema, tier_c
from lpstgp.data.tier_a import git_revision, load_universe
from lpstgp.data.tier_b import DEFAULT_COUNTRY_MARKET, SelectionRule
from lpstgp.splits import periods_from_settings

KNOWN_ISSUES_A = """\
## Known issues of the pilot sources (pilot only; see docs/decisions.md)

- **Yahoo Finance (yfinance):** indices are price indices, not total return. Raw OHLC are split-adjusted
  by the vendor (multiplicative). Daily timestamps are exchange-local. Data are "for personal use"
  under Yahoo's terms and are never redistributed. Rate limits per IP; occasional duplicated last rows.
  Continuous futures (`=F`) are unadjusted front-month splices: roll days carry the contract spread as a
  spurious return (see the jump-flag counts of the futures alternates vs the roll-free primaries).
- **ECB reference rates:** a daily fixing at 14:15 CET on TARGET business days, not a market close;
  USD crosses are ratios of two EUR rates on the same date. Close only.
- **EIA spot prices:** official assessments, close only, U.S. federal holiday calendar; the files are
  not range-limited (later rows are dropped at build). WTI printed a negative price on 2020-04-20,
  which the schema marks invalid.
- **Bitstamp / Coinbase:** exchange-specific prices (not composite), UTC days, native 7-day calendar;
  exchange outages appear as gaps. Coinbase XRP has a trading suspension (2021–2023).
- **Close times differ across markets** (Asia, Europe, US, crypto at 00:00 UTC): irrelevant for
  per-asset rules, relevant for the portfolio layer (WP4).
"""


def tier_a_report(paths, settings) -> str:
    tier_dir = paths.tier_dir("A")
    periods = periods_from_settings(settings)
    universe = load_universe()
    processed = tier_dir / "processed"
    primary_rows, alternate_rows = [], []
    for inst in universe:
        files = [("primary", processed / f"{inst.id}.parquet")]
        files += [
            ("alternate", p)
            for p in sorted((processed / "alternates").glob(f"{inst.id}__*.parquet"))
            if not p.name.endswith(".flags.parquet")
        ]
        for role, path in files:
            if not path.is_file():
                meta = {
                    "instrument_id": inst.id,
                    "asset_class": inst.asset_class,
                    "source": "missing",
                    "source_symbol": "",
                }
                (primary_rows if role == "primary" else alternate_rows).append((meta, {"bars": 0}))
                continue
            meta = schema.read_meta(path)
            frame = schema.read_frame(path)
            flags_path = path.with_suffix(".flags.parquet")
            flags = (
                pd.read_parquet(flags_path)
                if flags_path.is_file()
                else pd.DataFrame(columns=["date", "flag"])
            )
            result = quality.assess(frame, flags, meta, periods, settings)
            (primary_rows if role == "primary" else alternate_rows).append((meta, result))

    by_class = Counter(m["asset_class"] for m, r in primary_rows if r.get("bars"))
    per_period = Counter(pid for _, r in primary_rows for pid in r.get("eligible", []))
    total_pairs = sum(per_period.values())
    entries = mf.read_entries(tier_dir / "manifest.csv")
    latest = {}
    for e in entries:
        key = (e["source"], e["symbol"])
        if key not in latest or e["downloaded_at_utc"] > latest[key]["downloaded_at_utc"]:
            latest[key] = e
    raw_bytes = sum(int(e["bytes"]) for e in latest.values())
    dl_dates = sorted({e["downloaded_at_utc"][:10] for e in latest.values()})
    splits_cfg = settings["splits"]

    lines = [
        "# Data report — Tier A (cross-asset pilot)",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC from code `{git_revision()}`. "
        "Counts only: no prices, return statistics or performance are shown for any date.",
        "",
        "## Summary",
        "",
        f"- Instruments with data: {sum(by_class.values())} of {len(universe)} "
        f"({', '.join(f'{k} {v}' for k, v in sorted(by_class.items()))}).",
        f"- Raw series: {len(latest)} (latest downloads on {', '.join(dl_dates) or 'n/a'}), {raw_bytes / 1e6:.1f} MB raw.",
        f"- Walk-forward periods: {len(periods)} ({periods[0].id} fit {periods[0].fit_start} … "
        f"{periods[-1].id} test end {periods[-1].test_end}, exclusive). Eligibility needs "
        f"{splits_cfg['lookback_max_bars']} valid bars before the fit start and ≥ "
        f"{splits_cfg['min_session_coverage']:.0%} of expected sessions in [fit start, test end).",
        f"- Eligible (instrument, period) pairs: **{total_pairs}**.",
        "",
        "Eligible instruments per period:",
        "",
        "| " + " | ".join(p.id for p in periods) + " |",
        "|" + "---:|" * len(periods),
        "| " + " | ".join(str(per_period.get(p.id, 0)) for p in periods) + " |",
        "",
        "## Primary series",
        "",
        "Coverage, missing and longest gap are against the instrument's expected sessions (exchange calendar, "
        "weekdays for ECB fixings, all days for crypto) between its first and last valid bar. *Invalid* = bars "
        "with a missing or non-positive close. *Jump flags* = |log return| > "
        f"{settings['quality']['jump_sigma']:g} trailing robust sds ({settings['quality']['jump_window']} bars).",
        "",
        quality.render_table(primary_rows),
        "## Alternate series (comparison only, not used by default)",
        "",
        quality.render_table(alternate_rows),
        KNOWN_ISSUES_A,
    ]
    return "\n".join(lines)


def tier_b_report(paths) -> str:
    rule = SelectionRule()
    markets = {}
    for country, market in DEFAULT_COUNTRY_MARKET.items():
        markets.setdefault(market, []).append(country)
    tier_dir = paths.tier_dir("B")
    files = (
        sorted(str(p.relative_to(tier_dir)) for p in tier_dir.rglob("*") if p.is_file())
        if tier_dir.exists()
        else []
    )
    return "\n".join(
        [
            "# Data report — Tier B (stocks)",
            "",
            f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC from code `{git_revision()}`.",
            "",
            "**Status: no data.** WP1 implements the selection rule and the loader interface only. The final source "
            "must be survivorship-free (point-in-time constituents and market caps, delisted names and delisting "
            "returns), e.g. WRDS/CRSP + Compustat Global, Refinitiv or Bloomberg; to be provided by the PI.",
            "",
            f"Files currently in `tierB/`: {len(files)}.",
            "",
            "## Selection rule (fixed in advance)",
            "",
            f"- {rule.per_market} largest securities per market by USD market capitalisation as of the last session "
            "before the selection date; primary listings of common equity; one share class per issuer (the largest); "
            "ties broken by security id; names delisted later stay selected.",
            "- Mode `once` (selection at the sample start, 2005-07-01) or `per_period` (point-in-time re-selection at "
            "every fit start); both implemented, choice open for WP2.",
            "- Markets (provisional country mapping): "
            + "; ".join(f"{m}: {', '.join(sorted(c))}" for m, c in sorted(markets.items()))
            + ".",
            "",
            "Coverage, gaps and date ranges will be reported here once the vendor data are loaded.",
            "",
        ]
    )


def tier_c_report(paths) -> str:
    inv = tier_c.inventory(paths.tier_dir("C"))
    lines = [
        "# Data report — Tier C (Essex DC-GP and ActTrade datasets)",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC from code `{git_revision()}`.",
        "",
    ]
    if not inv["files"]:
        lines += [
            "**Status: no data.** `tierC/` is empty. Copy the datasets there together with a `manifest.toml` "
            "(format documented in `src/lpstgp/data/tier_c.py`); the loader maps them to schema v1 and keeps "
            "the published splits.",
            "",
        ]
    else:
        lines += [
            f"Files present: {len(inv['files'])}; datasets described in manifest.toml: {len(inv['datasets'])}.",
            "",
        ]
        lines += [f"- `{f}`" for f in inv["files"]]
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    paths, settings = load_paths(), load_settings()
    out = Path(paths.reports_dir)
    out.mkdir(parents=True, exist_ok=True)
    reports = {
        "data_tierA.md": tier_a_report(paths, settings),
        "data_tierB.md": tier_b_report(paths),
        "data_tierC.md": tier_c_report(paths),
    }
    for name, text in reports.items():
        (out / name).write_text(text, encoding="utf-8")
        print(f"wrote {out / name}")


if __name__ == "__main__":
    main()
