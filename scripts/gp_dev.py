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

    Revised before any confidence-bound run (D-090): only the composite-fitness variants run
    (RUN_CONFIGS). Across 34,000 evolved rules of WP2 and the runs study, no training measure
    (composite, Sharpe, half-year Sharpe statistics, return, Calmar, trades, size) predicts the
    validation Sharpe (Spearman rho -0.05 to +0.05), and the confidence bound over all bars is
    nearly a constant shift of the Sharpe ratio. E1 therefore tests the data question alone;
    the plan keeps all four configurations, so it, its digests and its records stay valid.

E1b (D-092)  the evidence question with longer training: pooled cells on 6-year fit windows
    (G1-G3: fit 1999-2005 ... 2001-2007, the same validation years 2005-06 .. 2007-08; no test
    stage), arm 2c and the TA GP, composite fitness, 10 runs per cell. Only equities (G1-G3) and
    FX (G3) have the history, so there are 4 cells: the gain test (a) runs over runs (each run
    against its own generation 0) instead of over cells, which with 4 cells could never reach
    p < 0.05. The other marks and the decision rule are E1's. E1's 2-year pooled cells of the
    same pools and validation years are reported alongside.

Usage:  uv run python scripts/gp_dev.py e1|e1b --mode plan|run|report [--workers 6]
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
RUN_CONFIGS = ("e1-2c-comp", "e1-TA-comp")  # D-090 revision: the data question only
E1B = "gpdev-e1b"
E1B_PERIODS = ("G1", "G2", "G3")
E1B_CONFIGS = ("e1b-2c", "e1b-TA")


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


def e1b_configs(settings) -> list[Config]:
    return [
        Config(f"e1b-{arm}", library, gp=wp4.gp_arm(f"e1b-{arm}", library, settings).gp)
        for arm, library in ARMS.items()
    ]


def e1b_cells(paths, settings) -> list[tuple[tuple[str, ...], str]]:
    """Every asset class with at least two eligible instruments, pooled, in G1-G3."""
    from lpstgp.data import eligibility

    classes = {i.id: i.asset_class for i in load_universe()}
    table = eligibility.table(paths, settings, E1B_PERIODS)
    cells = []
    for period in E1B_PERIODS:
        pooled = collections.defaultdict(list)
        for name in table[period]:
            pooled[classes[name]].append(name)
        cells += [(tuple(sorted(v)), period) for v in pooled.values() if len(v) > 1]
    return cells


def e1b_plan(paths, settings) -> Path:
    return write_plan(
        E1B, e1b_configs(settings), e1b_cells(paths, settings), E1_RUNS, paths, settings,
        record_format="json.gz",
    )  # fmt: skip


def e1_plan(paths, settings) -> Path:
    return write_plan(
        E1, e1_configs(settings), e1_cells(), E1_RUNS, paths, settings, record_format="json.gz"
    )


# --- analysis ---------------------------------------------------------------------------------


def e1_records(plan_path: Path, settings, configs=RUN_CONFIGS):
    """The records of ``configs``' tasks; every one must be complete."""
    from lpstgp.campaign.execute import IncompleteCampaignError, is_complete, load_plan, run_task
    from lpstgp.runner import read_record, record_path

    plan = load_plan(plan_path)
    for task in plan["tasks"]:
        if task["config"] not in configs:
            continue
        run = run_task(plan, task, settings)
        path = record_path(plan_path.parent, run)
        if not is_complete(path, run):
            raise IncompleteCampaignError(f"{task['id']}: no complete record")
        yield read_record(path)


def e1_execute(plan_path: Path, paths, settings, workers: int, configs=RUN_CONFIGS) -> dict:
    """execute_plan restricted to ``configs``' tasks (same checks, same resumable pool)."""
    from lpstgp.campaign.execute import (
        PlanMismatchError,
        is_complete,
        load_plan,
        run_task,
        verify,
    )  # fmt: skip
    from lpstgp.runner import record_path, run_many

    plan = load_plan(plan_path)
    if problems := verify(plan, paths, settings):
        raise PlanMismatchError("; ".join(problems))
    pending, done = [], 0
    for task in plan["tasks"]:
        if task["config"] not in configs:
            continue
        run = run_task(plan, task, settings)
        if is_complete(record_path(plan_path.parent, run), run):
            done += 1
        else:
            pending.append(run)
    run_many(pending, workers, plan_path.parent)
    return {"skipped": done, "evolved": len(pending)}


def e1_rows(plan_path: Path, paths, settings, configs=RUN_CONFIGS) -> list[dict]:
    rows = []
    for r in e1_records(plan_path, settings, configs):
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


def e1_summary(rows: list[dict], gain_over: str = "cells") -> dict:
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
        tested = gains if gain_over == "cells" else [
            r["val_last"] - r["val_gen0"] for v in cells.values() for r in v
        ]  # fmt: skip
        p = float(wilcoxon(tested, alternative="greater").pvalue) if any(tested) else 1.0
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


def e1_report(summary: dict, title: str = "E1: one instrument or pooled (composite fitness)",
              over: str = "cells", decision: str = "D-090") -> str:  # fmt: skip
    lines = [
        f"# GP development {title}",
        "",
        f"Pass marks (fixed before the runs, {decision}): median evolution gain in validation "
        f"Sharpe >= {GAIN_MIN} with one-sided Wilcoxon p < {ALPHA} over {over}; median Spearman rho "
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
    winners = [s for s in summary.values() if s["passes"] and "-2c" in s["config"]]
    lines += ["", "**Decision (arm 2c):** " + (
        "go to E2 with " + max(winners, key=lambda s: s["val_last"])["config"] + "/"
        + max(winners, key=lambda s: s["val_last"])["data"]
        if winners else "no variant passes: stop and rethink before any larger run"
    )]  # fmt: skip
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)  # fmt: skip
    parser.add_argument("experiment", choices=["e1", "e1b"])
    parser.add_argument("--mode", choices=["plan", "run", "report"], required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    paths, settings = load_paths(), load_settings()
    name, configs = (E1, RUN_CONFIGS) if args.experiment == "e1" else (E1B, E1B_CONFIGS)
    plan_path = paths.results_dir / "campaigns" / name / "tasks.json"
    if args.mode == "plan":
        plan_path = (e1_plan if args.experiment == "e1" else e1b_plan)(paths, settings)
        plan = json.loads(plan_path.read_text())
        print(f"{plan_path}: {len(plan['tasks'])} tasks")
    elif args.mode == "run":
        print(e1_execute(plan_path, paths, settings, args.workers, configs), flush=True)
    else:
        over = "cells" if args.experiment == "e1" else "runs"
        summary = e1_summary(e1_rows(plan_path, paths, settings, configs), gain_over=over)
        if args.experiment == "e1":
            text = e1_report(summary)
        else:  # with E1's 2-year pooled cells of the same pools and validation years
            same = {"PL1": "G1", "PL2": "G2", "P01": "G3"}
            pools = {(tuple(sorted(i)), same[p]) for i, p in e1b_cells(paths, settings)}
            short = [r for r in e1_rows(paths.results_dir / "campaigns" / E1 / "tasks.json",
                                         paths, settings)
                     if r["data"] == "pooled" and (tuple(r["cell"][0].split("+")),
                                                   same[r["cell"][1]]) in pools]  # fmt: skip
            for r in short:
                r["data"] = "pooled-2y"
            summary |= e1_summary(short, gain_over="runs")
            text = e1_report(summary, "E1b: pooled, 6-year training windows", "runs", "D-092")
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / f"{args.experiment}.json").write_text(json.dumps(summary, indent=2) + "\n")
        (REPORTS / f"{args.experiment}.md").write_text(text)
        print(text)


if __name__ == "__main__":
    main()
