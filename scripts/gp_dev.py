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

E2 (D-094)  E1b's cells and periods with long-short stop-and-reverse positions sized to 10%
    annual volatility (trailing 63 bars, capped at 3x), composite fitness, arm 2c and the TA GP,
    10 runs per cell. The benchmark is the 12-month trend rule (long if the 252-bar log return
    is positive, short if negative) scored by the same fitness code, sizing and costs on the
    same validation sandboxes; volatility-sized buy-and-hold is reported beside it.
    pass marks, fixed before any E2 run: E1b's (a) and (b), and
      (c) the median over cells of (the cell's median validation Sharpe of the final rule minus
          the trend rule's validation Sharpe on that cell) is at least 0.

E3 (D-096)  E2 with one change, the fitness: the net Sharpe ratio of the sized positions over
    the whole training window (objective "sharpe"), the minimum-activity rule off, the size
    penalty kept. E2's cells, runs, benchmark and pass marks.

E4 (D-098)  A and B on fresh years: E3's configuration, TA GP only, H1-H7 (validation
    1998-99 .. 2004-05), equities pooled by region (14 cells), 10 runs. After evolution, on
    training data only: the gate (rank-0 rule if its training excess Sharpe over the trend rule
    beats the expected maximum of N null Sharpe ratios, else the trend rule) and ensembles of
    the cell's 10 rank-0 (or gated) rules; each method is compared with the trend rule on the
    validation years (one-sided Wilcoxon over cells, Holm over the four methods).

Usage:  uv run python scripts/gp_dev.py e1|e1b|e2|e3|e4 --mode plan|run|report [--workers 6]
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
E2 = "gpdev-e2"
E2_CONFIGS = ("e2-2c", "e2-TA")
E2_FITNESS = {"position_mode": "reverse", "vol_target": 0.10}
TREND_BARS = 252
E3 = "gpdev-e3"
E3_CONFIGS = ("e3-2c", "e3-TA")
E3_FITNESS = {**E2_FITNESS, "objective": "sharpe", "min_entries_per_year": 0.0}
E4 = "gpdev-e4"
E4_CONFIGS = ("e4-TA",)
E4_PERIODS = tuple(f"H{k}" for k in range(1, 8))
REGIONS = {"americas_europe": ("SPX", "NDX", "CAC", "DAX", "UKX", "SMI"),
           "asia_pacific": ("NKY", "HSI", "AS51", "KOSPI")}  # fmt: skip
E4_METHODS = ("free", "gated", "ensemble", "gated_ensemble")


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


def e2_configs(settings) -> list[Config]:
    return [
        Config(f"e2-{arm}", library, gp=wp4.gp_arm(f"e2-{arm}", library, settings).gp,
               fitness=dict(E2_FITNESS))
        for arm, library in ARMS.items()
    ]  # fmt: skip


def e3_configs(settings) -> list[Config]:
    return [
        Config(f"e3-{arm}", library, gp=wp4.gp_arm(f"e3-{arm}", library, settings).gp,
               fitness=dict(E3_FITNESS))
        for arm, library in ARMS.items()
    ]  # fmt: skip


def e3_plan(paths, settings) -> Path:
    return write_plan(
        E3, e3_configs(settings), e1b_cells(paths, settings), E1_RUNS, paths, settings,
        record_format="json.gz",
    )  # fmt: skip


def e4_cells(paths, settings) -> list[tuple[tuple[str, ...], str]]:
    """Each H period's eligible equity indices, pooled by region (D-098)."""
    from lpstgp.data import eligibility

    table = eligibility.table(paths, settings, E4_PERIODS)
    cells = []
    for period in E4_PERIODS:
        for members in REGIONS.values():
            pool = tuple(sorted(n for n in table[period] if n in members))
            if len(pool) > 1:
                cells.append((pool, period))
    return cells


def e4_plan(paths, settings) -> Path:
    config = Config("e4-TA", "technical", gp=wp4.gp_arm("e4-TA", "technical", settings).gp,
                    fitness=dict(E3_FITNESS))  # fmt: skip
    return write_plan(E4, [config], e4_cells(paths, settings), E1_RUNS, paths, settings,
                      record_format="json.gz")  # fmt: skip


def expected_max_sharpe(n_trials: int, bars: int, periods_per_year: int) -> float:
    """Annualised expected maximum Sharpe ratio of ``n_trials`` strategies with no skill over
    ``bars`` bars (False Strategy Theorem, Bailey and Lopez de Prado 2014)."""
    from scipy.stats import norm

    if n_trials < 2:
        return 0.0
    gamma = 0.5772156649015329
    z = (1 - gamma) * norm.ppf(1 - 1 / n_trials) + gamma * norm.ppf(1 - 1 / (n_trials * np.e))
    return float(np.sqrt(periods_per_year / bars) * z)


def _positions(entry, exit_, bars, lo, hi, cfg):
    """Held positions and net returns of a rule over [lo, hi) bars, E2's sizing and costs."""
    from lpstgp.backtest import engine
    from lpstgp.backtest.costs import from_meta
    from lpstgp.gp import fitness as fit

    costs = from_meta(bars.meta)
    vol = fit.trailing_vol(bars.log_return, cfg.vol_window, fit.PERIODS_PER_YEAR[bars.calendar])
    res = engine.run(entry, exit_, bars.log_return, costs, active_from=lo, lag=cfg.execution_lag,
                     mode=cfg.position_mode, scale=fit.vol_scale(vol, cfg.vol_target))  # fmt: skip
    return res.held, res.net[lo:hi]


def _net_of(held, bars, lo, hi):
    """Net returns of a given held-position path (the averaged positions of an ensemble)."""
    from lpstgp.backtest.costs import from_meta

    lr = bars.log_return
    simple = np.where(np.isnan(lr), 0.0, np.expm1(np.nan_to_num(lr)))
    change = np.diff(held, prepend=0.0)
    buy, sell = from_meta(bars.meta).rates(len(held))
    cost = np.where(change > 0, change * buy, -change * sell)
    return (held * simple - cost)[lo:hi]


def _sharpe(x, ppy):
    from lpstgp.backtest.metrics import sharpe

    return float(sharpe(np.asarray(x), ppy))


def e4_evaluate(plan_path: Path, paths, settings, configs=E4_CONFIGS) -> dict:
    """Per cell: the validation Sharpe of every method (mean over instruments), and gate counts."""
    from lpstgp.campaign.plan import Config as _Config
    from lpstgp.data.store import modelling_store
    from lpstgp.gp import fitness as fit
    from lpstgp.pilot import rule_signals
    from lpstgp.sandbox import Sandbox
    from lpstgp.splits import Stage, all_periods

    _gp, cfg = _Config("e", "technical", fitness=dict(E3_FITNESS)).resolved(settings)
    store = modelling_store(paths.tier_dir("A"), settings)
    lmax = settings["splits"]["lookback_max_bars"]
    by_cell = collections.defaultdict(list)
    for r in e1_records(plan_path, settings, configs):
        by_cell[(tuple(r["instruments"]), r["period"]["id"])].append(r)
    out = {}
    for (instruments, pid), recs in sorted(by_cell.items()):
        period = all_periods(settings)[pid]
        boxes = {st: Sandbox.open(store, period, st, instruments, lmax)
                 for st in (Stage.FIT, Stage.VALIDATE)}  # fmt: skip
        per_inst = {}
        gated_runs = 0
        for name in instruments:
            stage_data = {}
            for st, box in boxes.items():
                b = box[name]
                lo_d, hi_d = period.scored_window(st)
                lo = int(np.searchsorted(b.dates, np.datetime64(lo_d)))
                hi = int(np.searchsorted(b.dates, np.datetime64(hi_d)))
                lp = np.asarray(b.log_price, dtype=np.float64)
                mom = np.full(len(lp), np.nan)
                mom[TREND_BARS:] = lp[TREND_BARS:] - lp[:-TREND_BARS]
                trend = _positions((mom > 0).astype(float), (mom < 0).astype(float), b, lo, hi, cfg)
                rules = []
                for r in recs:
                    rank0 = {**r, "selected": 0}  # the training-best rule, not validation's
                    sub = replace_box(box, name)
                    ((_n, _b, _s, entry, exit_),) = rule_signals(rank0, sub)
                    rules.append(_positions(entry, exit_, b, lo, hi, cfg))
                stage_data[st] = (b, lo, hi, trend, rules)
            per_inst[name] = stage_data
        # the gate, on training data: the mean over instruments of the excess Sharpe
        ppy = fit.PERIODS_PER_YEAR[boxes[Stage.FIT][instruments[0]].calendar]
        gate = []
        for k, r in enumerate(recs):
            excess = []
            for name in instruments:
                b, lo, hi, trend, rules = per_inst[name][Stage.FIT]
                excess.append(_sharpe(rules[k][1] - trend[1], ppy))
            bars = per_inst[instruments[0]][Stage.FIT][2] - per_inst[instruments[0]][Stage.FIT][1]
            bar = expected_max_sharpe(int(r["budget"]["unique_evaluations"]), bars, ppy)
            gate.append(float(np.mean(excess)) > bar)
        gated_runs = int(sum(gate))
        methods = {m: [] for m in ("trend", *E4_METHODS)}
        for name in instruments:
            b, lo, hi, trend, rules = per_inst[name][Stage.VALIDATE]
            methods["trend"].append(_sharpe(trend[1], ppy))
            free = [_sharpe(net, ppy) for _held, net in rules]
            chosen = [rules[k] if gate[k] else trend for k in range(len(rules))]
            methods["free"].append(float(np.median(free)))
            methods["gated"].append(float(np.median([_sharpe(net, ppy) for _h, net in chosen])))
            for key, members in (("ensemble", rules), ("gated_ensemble", chosen)):
                avg = np.mean([h for h, _net in members], axis=0)
                methods[key].append(_sharpe(_net_of(avg, b, lo, hi), ppy))
        out[f"{pid} {'+'.join(instruments)}"] = {
            **{m: float(np.mean(v)) for m, v in methods.items()}, "gated_runs": gated_runs,
            "runs": len(recs),
        }  # fmt: skip
    return out


def replace_box(box, name):
    from dataclasses import replace as _replace
    from types import MappingProxyType

    return _replace(box, bars=MappingProxyType({name: box[name]}))


def e4_decision(cells: dict) -> dict:
    """D-098's pass marks: each method against the trend rule over cells, Holm over methods."""
    from scipy.stats import wilcoxon

    raw = {}
    for m in E4_METHODS:
        diffs = [c[m] - c["trend"] for c in cells.values()]
        p = float(wilcoxon(diffs, alternative="greater").pvalue) if any(diffs) else 1.0
        raw[m] = {"median_diff": float(np.median(diffs)), "p": p}
    order = sorted(raw, key=lambda m: raw[m]["p"])
    running = 0.0
    for i, m in enumerate(order):
        running = max(running, min(1.0, (len(order) - i) * raw[m]["p"]))
        raw[m]["p_holm"] = running
        raw[m]["beats_trend"] = raw[m]["median_diff"] > 0 and running < ALPHA
        raw[m]["non_inferior"] = raw[m]["median_diff"] >= -0.10
    return raw


def e4_report(cells: dict, decision: dict) -> str:
    lines = ["# GP development E4: significance gate (A) and ensembles (B), fresh years", "",
             "TA GP, E3's configuration, H1-H7 (validation 1998-99 .. 2004-05), equities pooled "
             "by region, 10 runs per cell. Validation Sharpe, mean over a cell's instruments, "
             "net of costs, volatility-targeted long-short. Pass marks fixed before the runs "
             "(D-098). No test data.", "",
             "| cell | trend | free | gated | ensemble | gated ensemble | runs gated in |",
             "|---|---:|---:|---:|---:|---:|---:|"]  # fmt: skip
    for k, c in cells.items():
        lines.append(f"| {k[:40]} | {c['trend']:.2f} | {c['free']:.2f} | {c['gated']:.2f} | "
                     f"{c['ensemble']:.2f} | {c['gated_ensemble']:.2f} | "
                     f"{c['gated_runs']}/{c['runs']} |")  # fmt: skip
    means = {m: float(np.mean([c[m] for c in cells.values()])) for m in ("trend", *E4_METHODS)}
    lines.append("| **mean** | " + " | ".join(f"**{means[m]:.2f}**" for m in ("trend", *E4_METHODS))
                 + " | |")  # fmt: skip
    lines += ["", "| method | median diff vs trend | p | p (Holm) | beats trend | non-inferior |",
              "|---|---:|---:|---:|---|---|"]  # fmt: skip
    for m, d in decision.items():
        lines.append(f"| {m} | {d['median_diff']:+.2f} | {d['p']:.3f} | {d['p_holm']:.3f} | "
                     f"{'yes' if d['beats_trend'] else 'no'} | "
                     f"{'yes' if d['non_inferior'] else 'no'} |")  # fmt: skip
    return "\n".join(lines) + "\n"


def e2_plan(paths, settings) -> Path:
    return write_plan(
        E2, e2_configs(settings), e1b_cells(paths, settings), E1_RUNS, paths, settings,
        record_format="json.gz",
    )  # fmt: skip


def benchmarks(paths, settings, cells) -> dict[tuple[str, str], dict[str, float]]:
    """Per cell, the mean over its instruments of the validation Sharpe of the 12-month trend
    rule and of buy-and-hold, long-short and volatility-sized as E2's rules (VALIDATE only)."""
    from lpstgp.backtest.costs import from_meta
    from lpstgp.campaign.plan import Config as _Config
    from lpstgp.data.store import modelling_store
    from lpstgp.gp import fitness as fit
    from lpstgp.sandbox import Sandbox
    from lpstgp.splits import Stage, all_periods

    _gp, cfg = _Config("b", "technical", fitness=dict(E2_FITNESS)).resolved(settings)
    store = modelling_store(paths.tier_dir("A"), settings)
    lmax = settings["splits"]["lookback_max_bars"]
    out = {}
    for instruments, pid in cells:
        period = all_periods(settings)[pid]
        box = Sandbox.open(store, period, Stage.VALIDATE, instruments, lmax)
        window = period.scored_window(Stage.VALIDATE)
        values = {"trend": [], "hold": []}
        for name in instruments:
            b = box[name]
            data = fit.prepare(b.dates, b.log_return, b.calendar, window, from_meta(b.meta),
                               cfg.segment_months)  # fmt: skip
            lp = np.asarray(b.log_price, dtype=np.float64)
            mom = np.full(len(lp), np.nan)
            mom[TREND_BARS:] = lp[TREND_BARS:] - lp[:-TREND_BARS]
            signals = {
                "trend": ((mom > 0).astype(float), (mom < 0).astype(float)),
                "hold": (np.ones(len(lp)), np.zeros(len(lp))),
            }
            for key, (entry, exit_) in signals.items():
                values[key].append(fit.market_part(entry, exit_, data, cfg)[1].get("sharpe", 0.0))
        out[("+".join(instruments), pid)] = {k: float(np.mean(v)) for k, v in values.items()}
    return out


def e2_compare(rows: list[dict], bench: dict) -> dict:
    """Pass mark (c): per variant, the median over cells of (median final validation Sharpe of
    the cell's runs - the trend rule's), and the same against buy-and-hold."""
    groups = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        groups[r["config"]][r["cell"]].append(r["val_sharpe"])
    out = {}
    for config, cells in groups.items():
        d_trend = [float(np.median(v)) - bench[c]["trend"] for c, v in cells.items()]
        d_hold = [float(np.median(v)) - bench[c]["hold"] for c, v in cells.items()]
        out[config] = {"vs_trend": float(np.median(d_trend)), "vs_hold": float(np.median(d_hold)),
                       "pass_benchmark": float(np.median(d_trend)) >= 0}  # fmt: skip
    return out


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
    parser.add_argument("experiment", choices=["e1", "e1b", "e2", "e3", "e4"])
    parser.add_argument("--mode", choices=["plan", "run", "report"], required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    paths, settings = load_paths(), load_settings()
    name, configs = {"e1": (E1, RUN_CONFIGS), "e1b": (E1B, E1B_CONFIGS),
                     "e2": (E2, E2_CONFIGS), "e3": (E3, E3_CONFIGS),
                     "e4": (E4, E4_CONFIGS)}[args.experiment]  # fmt: skip
    plan_path = paths.results_dir / "campaigns" / name / "tasks.json"
    if args.mode == "plan":
        plans = {"e1": e1_plan, "e1b": e1b_plan, "e2": e2_plan, "e3": e3_plan, "e4": e4_plan}
        plan_path = plans[args.experiment](paths, settings)
        plan = json.loads(plan_path.read_text())
        print(f"{plan_path}: {len(plan['tasks'])} tasks")
    elif args.mode == "run":
        print(e1_execute(plan_path, paths, settings, args.workers, configs), flush=True)
    elif args.experiment == "e4":
        cells = e4_evaluate(plan_path, paths, settings)
        decision = e4_decision(cells)
        text = e4_report(cells, decision)
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "e4.json").write_text(json.dumps({"cells": cells, "decision": decision},
                                                    indent=2) + "\n")  # fmt: skip
        (REPORTS / "e4.md").write_text(text)
        print(text)
    else:
        over = "cells" if args.experiment == "e1" else "runs"
        summary = e1_summary(e1_rows(plan_path, paths, settings, configs), gain_over=over)
        if args.experiment == "e1":
            text = e1_report(summary)
        elif args.experiment in ("e2", "e3"):
            rows = e1_rows(plan_path, paths, settings, configs)
            bench = benchmarks(paths, settings, e1b_cells(paths, settings))
            versus = e2_compare(rows, bench)
            for s_ in summary.values():
                s_ |= versus[s_["config"]]
                s_["passes"] = s_["passes"] and s_["pass_benchmark"]
            title = {
                "e2": "E2: long-short, volatility-targeted, pooled 6-year training",
                "e3": "E3: E2 with the full-window Sharpe fitness",
            }[args.experiment]
            text = e1_report(summary, title, "runs",
                             {"e2": "D-094", "e3": "D-096"}[args.experiment])  # fmt: skip
            text += "\n| cell | trend rule | buy-and-hold |\n|---|---:|---:|\n" + "".join(
                f"| {c[1]} {c[0][:30]} | {v['trend']:.2f} | {v['hold']:.2f} |\n"
                for c, v in bench.items()
            ) + "\n| variant | GP - trend (median over cells) | GP - hold |\n|---|---:|---:|\n" + (
                "".join(f"| {k} | {v['vs_trend']:+.2f} | {v['vs_hold']:+.2f} |\n"
                        for k, v in versus.items())
            )  # fmt: skip
        else:  # with E1's 2-year pooled cells of the same pools and validation years
            same = {"PL1": "G1", "PL2": "G2", "P01": "G3"}
            pools = {(tuple(sorted(i)), p) for i, p in e1b_cells(paths, settings)}
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
