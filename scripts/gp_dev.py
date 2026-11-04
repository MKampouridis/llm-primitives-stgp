"""GP development before WP4 (D-090): small, targeted experiments on the overfitting found in the
WP2 and runs-study records (training fitness doubles over 70 generations, validation Sharpe does
not move, and training scores do not predict validation scores).

Every read goes through the sandbox, FIT and VALIDATE only, of periods whose validation years
end by 2008-06-30, before WP4's first test year: PL1 (validation 2005-06), PL2 (2006-07) and P01
(2007-08). DEV is not used: the LLM's whole strategies, the source of arm 2c's operators, were
written on DEV's years (D-036).

E1  2 x 2: training data (one instrument, or pooled over the instruments of an asset class) x
    fitness (the WP2 composite, or the lower confidence bound of the Sharpe ratio), on arm 2c
    and the technical-analysis GP, 10 runs per cell, at WP2's calibrated budget.

    pass marks, fixed before any E1 run (D-090), per (arm, data, fitness) variant:
      (a) evolution helps out of sample: the median over cells of the median over runs of
          (validation Sharpe at the last checkpoint - at generation 0) is at least GAIN_MIN,
          and a one-sided Wilcoxon signed-rank test over cells gives p < ALPHA;
      (b) training scores predict validation: the median over cells of Spearman's rho between
          the runs' training fitness and validation Sharpe (rank-0 rule) is at least RHO_MIN.
    A variant passes on both. Arm 2c decides; the TA GP corroborates. Of the passing variants of
    arm 2c, the one with the highest median final validation Sharpe goes on to E2. If none
    passes, development stops for a rethink before any larger run.

Usage:  uv run python scripts/gp_dev.py e1 --mode plan|run|report [--workers 6]
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wp2_pilot
import wp4
from lpstgp.campaign.plan import Config, write_plan
from lpstgp.config import REPO_ROOT, load_paths, load_settings
from lpstgp.data.tier_a import load_universe

REPORTS = REPO_ROOT / "reports" / "gpdev"
E1 = "gpdev-e1"
E1_PERIODS = ("PL1", "PL2", "P01")
E1_RUNS = 10
ARMS = {"2c": "s2c", "TA": "technical"}
OBJECTIVES = {"comp": "composite", "lcb": "sharpe_lcb"}
GAIN_MIN, ALPHA, RHO_MIN = 0.10, 0.05, 0.10


def e1_configs(settings) -> list[Config]:
    out = []
    for arm, library in ARMS.items():
        base = wp4.gp_arm(f"e1-{arm}", library, settings)
        for short, objective in OBJECTIVES.items():
            fitness = {} if objective == "composite" else {"objective": objective}
            out.append(Config(f"e1-{arm}-{short}", library, gp=base.gp, fitness=fitness))
    return out


def period_instruments(period: str) -> list[str]:
    if period in ("PL1", "PL2"):
        return list(wp2_pilot.PILOT_INSTRUMENTS)  # the go/no-go's instruments
    table = json.loads((wp4.REPORTS / "eligibility.json").read_text())["eligible"]
    return list(table[period])


def e1_cells() -> list[tuple[tuple[str, ...], str]]:
    """Every instrument on its own, and every asset class pooled, in each period."""
    classes = {i.id: i.asset_class for i in load_universe()}
    cells = []
    for period in E1_PERIODS:
        names = period_instruments(period)
        cells += [((name,), period) for name in names]
        pooled = collections.defaultdict(list)
        for name in names:
            pooled[classes[name]].append(name)
        cells += [(tuple(sorted(v)), period) for v in pooled.values() if len(v) > 1]
    return cells


def e1_plan(paths, settings) -> Path:
    return write_plan(
        E1, e1_configs(settings), e1_cells(), E1_RUNS, paths, settings, record_format="json.gz"
    )


# --- analysis ---------------------------------------------------------------------------------


def e1_rows(plan_path: Path, paths, settings) -> list[dict]:
    from lpstgp.campaign.execute import iter_plan_records

    rows = []
    for r in iter_plan_records(plan_path, paths, settings):
        top = r["hall_of_fame"][0]
        per_fit, per_val = top["fit"]["instruments"], top["validation"]["instruments"]
        checkpoints = r["validation_checkpoints"]
        rows.append({
            "config": r["campaign"]["config"],
            "data": "pooled" if len(r["instruments"]) > 1 else "single",
            "cell": ("+".join(r["instruments"]), r["period"]["id"]),
            "fit_score": top["fit"]["fitness"],
            "fit_sharpe": float(np.mean([c.get("sharpe", 0.0) for c in per_fit.values()])),
            "val_sharpe": float(np.mean([c.get("sharpe", 0.0) for c in per_val.values()])),
            "val_gen0": checkpoints[0]["validation_sharpe"],
            "val_last": checkpoints[-1]["validation_sharpe"],
            "trades_fit": float(np.mean([c.get("trades", 0) for c in per_fit.values()])),
            "exposure_fit": float(np.mean([c.get("exposure", 0.0) for c in per_fit.values()])),
            "exposure_val": float(np.mean([c.get("exposure", 0.0) for c in per_val.values()])),
        })  # fmt: skip
    return rows


def e1_summary(rows: list[dict]) -> dict:
    from scipy.stats import spearmanr, wilcoxon

    groups = collections.defaultdict(lambda: collections.defaultdict(list))
    for row in rows:
        groups[(row["config"], row["data"])][row["cell"]].append(row)
    out = {}
    for (config, data), cells in sorted(groups.items()):
        gains = [
            float(np.median([r["val_last"] - r["val_gen0"] for r in v])) for v in cells.values()
        ]
        rhos = [
            float(spearmanr([r["fit_score"] for r in v], [r["val_sharpe"] for r in v])[0])
            for v in cells.values()
            if len({r["fit_score"] for r in v}) > 2 and len({r["val_sharpe"] for r in v}) > 2
        ]
        p = float(wilcoxon(gains, alternative="greater").pvalue) if any(gains) else 1.0
        flat = [r for v in cells.values() for r in v]
        med = {k: float(np.median([r[k] for r in flat])) for k in
               ("fit_sharpe", "val_sharpe", "val_gen0", "val_last", "trades_fit", "exposure_fit",
                "exposure_val")}  # fmt: skip
        gain, rho = float(np.median(gains)), float(np.median(rhos)) if rhos else float("nan")
        out[f"{config}/{data}"] = {
            "config": config, "data": data, "cells": len(cells), "runs": len(flat),
            "median_gain": gain, "gain_p": p, "median_rho": rho, **med,
            "pass_gain": gain >= GAIN_MIN and p < ALPHA, "pass_rho": rho >= RHO_MIN,
        }  # fmt: skip
        out[f"{config}/{data}"]["passes"] = (
            out[f"{config}/{data}"]["pass_gain"] and (out[f"{config}/{data}"]["pass_rho"])
        )
    return out


def e1_report(summary: dict) -> str:
    lines = [
        "# GP development E1: more data per search x a confidence-bound fitness",
        "",
        f"Pass marks (fixed before the runs, D-090): median evolution gain in validation Sharpe "
        f">= {GAIN_MIN} with one-sided Wilcoxon p < {ALPHA} over cells; median Spearman rho "
        f"(training fitness, validation Sharpe) >= {RHO_MIN}. Validation years 2005-06, 2006-07 "
        "and 2007-08; no test data.",
        "",
        "| variant | cells | runs | fit Sharpe | val Sharpe gen 0 | val Sharpe last | gain (p) "
        "| rho | trades (fit) | exposure fit / val | passes |",
        "|---|---:|---:|---:|---:|---:|---|---:|---:|---|---|",
    ]
    for key, s in summary.items():
        lines.append(
            f"| {key} | {s['cells']} | {s['runs']} | {s['fit_sharpe']:.2f} | {s['val_gen0']:.2f} "
            f"| {s['val_last']:.2f} | {s['median_gain']:+.2f} ({s['gain_p']:.3f}) "
            f"| {s['median_rho']:+.2f} | {s['trades_fit']:.0f} | {s['exposure_fit']:.2f} / "
            f"{s['exposure_val']:.2f} | {'yes' if s['passes'] else 'no'} |"
        )
    winners = [s for s in summary.values() if s["passes"] and s["config"].startswith("e1-2c")]
    lines += ["", "**Decision (arm 2c):** " + (
        "go to E2 with " + max(winners, key=lambda s: s["val_last"])["config"] + "/"
        + max(winners, key=lambda s: s["val_last"])["data"]
        if winners else "no variant passes: stop and rethink before any larger run"
    )]  # fmt: skip
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)  # fmt: skip
    parser.add_argument("experiment", choices=["e1"])
    parser.add_argument("--mode", choices=["plan", "run", "report"], required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    paths, settings = load_paths(), load_settings()
    plan_path = e1_plan(paths, settings)
    if args.mode == "plan":
        plan = json.loads(plan_path.read_text())
        print(f"{plan_path}: {len(plan['tasks'])} tasks")
    elif args.mode == "run":
        from lpstgp.campaign.execute import execute_plan

        print(execute_plan(plan_path, paths, settings, workers=args.workers), flush=True)
    else:
        summary = e1_summary(e1_rows(plan_path, paths, settings))
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "e1.json").write_text(json.dumps(summary, indent=2) + "\n")
        (REPORTS / "e1.md").write_text(e1_report(summary))
        print(e1_report(summary))


if __name__ == "__main__":
    main()
