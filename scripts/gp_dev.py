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

E5 (D-101)  planted-signal recovery: can the GP find an edge that is known to be there? Synthetic
    bars (tier S, lpstgp.data.synthetic; no market data), E3's configuration, TA GP, the dates of
    G1 (6-year fit, 1-year validation). A world is a pool of 6 instruments whose noise (GARCH
    volatility, fat tails, correlation 0.5) carries the edge of one planted rule, written in the
    TA GP's own grammar, at a planted Sharpe ratio of 0.25, 0.5, 1 or 2 per instrument before
    costs; null worlds carry none. 3 rules x 4 levels + null = 13 conditions, 8 worlds each,
    10 runs per world. Each run's training-best rule is scored on a fresh 20-year sample of its
    condition, which no run saw: its *match* is the correlation between the signs of its
    positions and the planted rule's (1 = the planted rule, 0 = unrelated or constant).
    pass marks, fixed before any E5 run, per condition:
      recovery        the median over worlds of the world's median match is at least 0.5;
      evolution adds  E1's gain mark (a), over worlds (reported; not part of the verdict);
      null control    the E4 gate (training Sharpe against the expected maximum of N null
                      Sharpe ratios) lets through at most 5% of the null worlds' runs.
    The machinery is sound if the null control holds and the two one-condition rules are
    recovered at Sharpe 2. Each rule's detection threshold is the lowest level from which
    recovery holds at every level upwards.

Usage:  uv run python scripts/gp_dev.py e1|e1b|e2|e3|e4|e5 --mode plan|run|report [--workers 6]
        python scripts/gp_dev.py e5 --mode data      (on CERES: writes tier S; before --mode plan)
        uv run python scripts/gp_dev.py e5 --mode register   (the trial register, on rag-server)
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
from lpstgp.campaign.plan import REGISTER, Config, write_plan
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
E5 = "gpdev-e5"
E5_CONFIGS = ("e5-TA",)
E5_PERIOD = "G1"  # its dates only: 6-year fit, 1-year validation, no test stage
E5_START = "1994-01-03"  # first simulated bar: burn-in before the sandbox's first read
E5_LEVELS = (0.25, 0.5, 1.0, 2.0)  # planted Sharpe per instrument, before costs
E5_WORLDS, E5_POOL, E5_COST_BPS = 8, 6, 2.0  # the pool and cost of E4's larger equity cells
# The planted conditions, in the TA GP's grammar: long while true, short while false.
_UP = "Gt_v1(MaGap200_v1, MaGap50_v1)"  # SMA50 above SMA200
_DIP = "Lt_v1(Rsi14_v1, RollingPercentile_v1(Rsi14_v1, LongWindow_120, Quantile_0p5))"
E5_RULES = {"trend": _UP, "revert": _DIP, "combo": f"And_v1({_UP}, {_DIP})"}
E5_SIMPLE = ("trend", "revert")  # one condition each: they decide whether the machinery is sound
MATCH_MIN, FULL_MATCH, SOUND_LEVEL, NULL_GATE_MAX = 0.5, 0.9, 2.0, 0.05
E5_BURN_IN, E5_FRESH_BARS = 600, 5040  # the fresh sample: 20 years after a burn-in


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


# --- E5: planted-signal recovery (D-101) ------------------------------------------------------


def e5_worlds() -> list[dict]:
    """Every world: its condition (rule, planted Sharpe), index and instrument names."""
    conditions = [("null", 0.0)] + [(r, lv) for r in E5_RULES for lv in E5_LEVELS]
    out = []
    for rule, level in conditions:
        for w in range(1, E5_WORLDS + 1):
            stem = f"{rule}{round(100 * level):03d}w{w}"
            names = tuple(f"{stem}{chr(ord('a') + i)}" for i in range(E5_POOL))
            out.append({"world": stem, "rule": rule, "sharpe": level, "names": names})
    return out


def e5_oracle(rule: str) -> tuple[str, str]:
    """The planted rule as (entry, exit) trees: long while the condition holds, else short."""
    return E5_RULES[rule], f"Not_v1({E5_RULES[rule]})"


def e5_signal(rule: str):
    """(signal, lookback) for lpstgp.data.synthetic.simulate: the rule's condition at the last
    bar of a window, computed by the TA library's own operators."""
    from lpstgp.gp.evaluate import TreeEvaluator
    from lpstgp.gp.pset import build
    from lpstgp.libraries import resolve
    from lpstgp.runner import parse_tree

    lib = build(resolve("technical"))
    tree = parse_tree(E5_RULES[rule], lib)

    def signal(log_price, log_return):
        return float(TreeEvaluator(lib, log_price, log_return, 2**20)(tree)[-1])

    return signal, lib.lookback(tree) + 8  # a margin over the bars the tree needs


def e5_dates(settings) -> np.ndarray:
    """Weekdays from E5_START to the end of G1's validation year."""
    from lpstgp.splits import all_periods

    end = all_periods(settings)[E5_PERIOD].test_start
    days = np.arange(np.datetime64(E5_START), np.datetime64(end), dtype="datetime64[D]")
    return days[np.is_busday(days)]


def _e5_write(job) -> str:
    from lpstgp.data import synthetic

    world, tier_dir, dates = job
    signal, lookback = (None, 0) if world["rule"] == "null" else e5_signal(world["rule"])
    close, _planted = synthetic.simulate(
        len(dates), E5_POOL, synthetic.world_seed(world["world"]), world["sharpe"], signal,
        lookback, lag=2,
    )  # fmt: skip
    planted = {"world": world["world"], "rule": world["rule"], "sharpe": world["sharpe"]}
    if world["rule"] != "null":
        planted["entry"], planted["exit"] = e5_oracle(world["rule"])
    synthetic.write_world(tier_dir, world["names"], dates, close, planted, E5_COST_BPS)
    return world["world"]


def e5_data(paths, settings, workers: int) -> dict:
    """Write tier S: every world not yet complete on disk (worlds are deterministic)."""
    from concurrent.futures import ProcessPoolExecutor
    from multiprocessing import get_context

    from lpstgp.data import synthetic

    tier_dir = paths.tier_dir(synthetic.TIER)
    dates = e5_dates(settings)
    todo = [w for w in e5_worlds()
            if not all((tier_dir / "processed" / f"{n}.parquet").is_file() for n in w["names"])]  # fmt: skip
    jobs = [(w, tier_dir, dates) for w in todo]
    if workers <= 1:
        done = [_e5_write(job) for job in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as pool:
            done = list(pool.map(_e5_write, jobs))
    return {"worlds": len(e5_worlds()), "written": len(done), "bars": len(dates)}


def e5_config(settings) -> Config:
    return Config("e5-TA", "technical", gp=wp4.gp_arm("e5-TA", "technical", settings).gp,
                  fitness=dict(E3_FITNESS))  # fmt: skip


def e5_plan(paths, settings) -> Path:
    """The plan, written where the data are (CERES). It does not touch the configuration
    register, which lives in the repository: ``e5_register`` enters it on rag-server."""
    from lpstgp.data import synthetic

    cells = [(w["names"], E5_PERIOD) for w in e5_worlds()]
    return write_plan(E5, [e5_config(settings)], cells, E1_RUNS, paths, settings, register=None,
                      record_format="json.gz", tier=synthetic.TIER)  # fmt: skip


def e5_register(settings, register: Path = REGISTER) -> str:
    """Enter E5's configuration in the trial register (once); returns its digest."""
    from dataclasses import asdict

    from lpstgp.campaign.plan import register_configs

    config = e5_config(settings)
    entry = {**asdict(config), "digest": config.digest(settings)}
    register_configs(register, E5, {config.name: entry})
    return entry["digest"]


def match(rule_held: np.ndarray, planted_held: np.ndarray) -> float:
    """Agreement beyond chance between a rule and the planted rule: the correlation of the signs
    of their positions over the bars where the planted rule is in the market. 1 = the planted
    rule, 0 = unrelated, and 0 for any constant position, however lopsided the planted one."""
    known = planted_held != 0
    a, b = np.sign(rule_held[known]), np.sign(planted_held[known])
    if len(a) < 2 or a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def e5_fresh(rule: str, level: float):
    """A fresh sample of the condition's world, never seen by any run: E5_POOL instruments x
    E5_FRESH_BARS scored bars after a burn-in, as bars for ``_positions``, with the planted
    rule's own positions and net returns on each."""
    from types import SimpleNamespace

    from lpstgp.data import synthetic
    from lpstgp.gp.evaluate import TreeEvaluator
    from lpstgp.gp.pset import build
    from lpstgp.libraries import resolve
    from lpstgp.runner import parse_tree

    signal, lookback = e5_signal(rule)
    n = E5_BURN_IN + E5_FRESH_BARS
    seed = synthetic.world_seed(f"{rule}{round(100 * level):03d}fresh")
    close, _planted = synthetic.simulate(n, E5_POOL, seed, level, signal, lookback, lag=2)
    lib = build(resolve("technical"))
    entry, exit_ = (parse_tree(t, lib) for t in e5_oracle(rule))
    out = []
    for i in range(E5_POOL):
        log_price = np.log(close[:, i])
        log_return = np.diff(log_price, prepend=np.nan)
        bars = SimpleNamespace(log_price=log_price, log_return=log_return, calendar="business",
                               meta={"cost_bps": E5_COST_BPS})  # fmt: skip
        out.append((bars, TreeEvaluator(lib, log_price, log_return), entry, exit_))
    return lib, out


def e5_evaluate(plan_path: Path, paths, settings, configs=E5_CONFIGS) -> list[dict]:
    """One row per run, for its training-best rule: the Sharpe ratio on the world's fit and
    validation windows and the gate (means over instruments), as in E4; and, on a fresh sample
    of the same condition, its match with the planted rule and both rules' Sharpe ratios."""
    from lpstgp.campaign.plan import Config as _Config
    from lpstgp.data import synthetic
    from lpstgp.data.store import modelling_store
    from lpstgp.gp import fitness as fit
    from lpstgp.gp.evaluate import TreeEvaluator
    from lpstgp.gp.pset import build
    from lpstgp.libraries import resolve
    from lpstgp.runner import parse_tree
    from lpstgp.sandbox import Sandbox
    from lpstgp.splits import Stage, all_periods

    _gp, cfg = _Config("e", "technical", fitness=dict(E3_FITNESS)).resolved(settings)
    store = modelling_store(paths.tier_dir(synthetic.TIER), settings)
    lmax = settings["splits"]["lookback_max_bars"]
    lib = build(resolve("technical"))
    ppy = fit.PERIODS_PER_YEAR["business"]
    by_cell = collections.defaultdict(list)
    for r in e1_records(plan_path, settings, configs):
        by_cell[(tuple(r["instruments"]), r["period"]["id"])].append(r)
    rows, fresh = [], {}
    stages = (Stage.FIT, Stage.VALIDATE)
    lo_f, hi_f = E5_BURN_IN, E5_BURN_IN + E5_FRESH_BARS
    for (instruments, pid), recs in sorted(by_cell.items()):
        period = all_periods(settings)[pid]
        planted = dict(store.meta(instruments[0])["planted"])
        is_null = planted["rule"] == "null"
        rules = [
            tuple(lib.from_names(r["hall_of_fame"][0][k]) for k in ("entry", "exit")) for r in recs
        ]  # the training-best rule of each run, not validation's choice
        sharpes = {st: [[] for _ in recs] for st in stages}
        oracle = {st: [] for st in stages}
        fit_bars = 0
        for st in stages:
            box = Sandbox.open(store, period, st, instruments, lmax)
            for name in instruments:
                b = box[name]
                lo_d, hi_d = period.scored_window(st)
                lo = int(np.searchsorted(b.dates, np.datetime64(lo_d)))
                hi = int(np.searchsorted(b.dates, np.datetime64(hi_d)))
                fit_bars = hi - lo if st is Stage.FIT else fit_bars
                ev = TreeEvaluator(lib, b.log_price, b.log_return)
                if not is_null:
                    trees = [parse_tree(planted[k], lib) for k in ("entry", "exit")]
                    net = _positions(ev(trees[0]), ev(trees[1]), b, lo, hi, cfg)[1]
                    oracle[st].append(_sharpe(net, ppy))
                for k, (entry, exit_) in enumerate(rules):
                    net = _positions(ev(entry), ev(exit_), b, lo, hi, cfg)[1]
                    sharpes[st][k].append(_sharpe(net, ppy))
        key = (planted["rule"], planted["sharpe"])
        if not is_null and key not in fresh:
            fresh[key] = e5_fresh(*key)[1]
        for k, r in enumerate(recs):
            checkpoints = r["validation_checkpoints"]
            fit_sharpe = float(np.mean(sharpes[Stage.FIT][k]))
            bar = expected_max_sharpe(int(r["budget"]["unique_evaluations"]), fit_bars, ppy)
            row = {
                "rule": planted["rule"], "sharpe": planted["sharpe"], "world": planted["world"],
                "run": int(r["campaign"]["run"]), "fit_sharpe": fit_sharpe,
                "val_sharpe": float(np.mean(sharpes[Stage.VALIDATE][k])),
                "val_gen0": checkpoints[0]["validation_sharpe"],
                "val_last": checkpoints[-1]["validation_sharpe"],
                "gate_bar": bar, "gated": bool(fit_sharpe > bar),
            }  # fmt: skip
            if not is_null:
                matches, own, planted_sharpe = [], [], []
                for bars, ev, o_entry, o_exit in fresh[key]:
                    o_held, o_net = _positions(ev(o_entry), ev(o_exit), bars, lo_f, hi_f, cfg)
                    held, net = _positions(ev(rules[k][0]), ev(rules[k][1]), bars, lo_f, hi_f, cfg)
                    matches.append(match(held[lo_f:hi_f], o_held[lo_f:hi_f]))
                    own.append(_sharpe(net, ppy))
                    planted_sharpe.append(_sharpe(o_net, ppy))
                row |= {
                    "match": float(np.mean(matches)), "fresh_sharpe": float(np.mean(own)),
                    "oracle_fresh": float(np.mean(planted_sharpe)),
                    "oracle_fit": float(np.mean(oracle[Stage.FIT])),
                    "oracle_val": float(np.mean(oracle[Stage.VALIDATE])),
                }  # fmt: skip
            rows.append(row)
    return rows


def e5_summary(rows: list[dict]) -> dict:
    """Per condition, over worlds: the pass marks of D-101 and the figures behind them."""
    from scipy.stats import wilcoxon

    groups = collections.defaultdict(lambda: collections.defaultdict(list))
    for row in rows:
        groups[(row["rule"], row["sharpe"])][row["world"]].append(row)
    order = ["null", *E5_RULES]
    out = {}
    for (rule, level), worlds in sorted(
        groups.items(), key=lambda g: (order.index(g[0][0]), g[0][1])
    ):
        flat = [r for v in worlds.values() for r in v]

        def over_worlds(key, worlds=worlds):  # the median over worlds of each world's median
            return float(np.median([np.median([r[key] for r in v]) for v in worlds.values()]))

        gains = [float(np.median([r["val_last"] - r["val_gen0"] for r in v]))
                 for v in worlds.values()]  # fmt: skip
        p = float(wilcoxon(gains, alternative="greater").pvalue) if any(gains) else 1.0
        s = {
            "rule": rule, "sharpe": level, "worlds": len(worlds), "runs": len(flat),
            "fit_sharpe": over_worlds("fit_sharpe"), "val_sharpe": over_worlds("val_sharpe"),
            "median_gain": float(np.median(gains)), "gain_p": p,
            "pass_gain": float(np.median(gains)) >= GAIN_MIN and p < ALPHA,
            "gated": float(np.mean([r["gated"] for r in flat])),
        }  # fmt: skip
        if rule == "null":
            s["pass_null"] = s["gated"] <= NULL_GATE_MAX
        else:
            s |= {
                "oracle_fit": over_worlds("oracle_fit"), "oracle_val": over_worlds("oracle_val"),
                "oracle_fresh": over_worlds("oracle_fresh"),
                "fresh_sharpe": over_worlds("fresh_sharpe"), "match": over_worlds("match"),
                "full": float(np.mean([r["match"] >= FULL_MATCH for r in flat])),
            }  # fmt: skip
            s["pass_recovery"] = s["match"] >= MATCH_MIN
        out[f"{rule}/{level:g}"] = s
    return out


def e5_decision(summary: dict) -> dict:
    """D-101's verdict: is the machinery sound, and from which planted Sharpe is each rule
    recovered (at that level and every level above it)?"""
    null_ok = bool(summary.get("null/0", {}).get("pass_null", False))
    thresholds = {}
    for rule in E5_RULES:
        levels = sorted(s["sharpe"] for s in summary.values() if s["rule"] == rule)
        threshold = None
        for level in reversed(levels):
            if not summary[f"{rule}/{level:g}"]["pass_recovery"]:
                break
            threshold = level
        thresholds[rule] = threshold
    recovered = all(
        summary.get(f"{rule}/{SOUND_LEVEL:g}", {}).get("pass_recovery", False) for rule in E5_SIMPLE
    )
    return {"null_control": null_ok, "thresholds": thresholds, "sound": null_ok and recovered}


def e5_report(summary: dict, decision: dict) -> str:
    lines = [
        "# GP development E5: planted-signal recovery (synthetic data)", "",
        "TA GP, E3's configuration, on synthetic worlds of 6 instruments (tier S, no market "
        "data): 6-year fit, 1-year validation, 8 worlds per condition, 10 runs per world. "
        "Figures are medians over worlds of each world's median over runs, for each run's "
        "training-best rule. *Fresh* is a 20-year sample of the same condition that no run "
        "saw. *Match* is the correlation between the signs of the rule's and the planted "
        "rule's positions on it (1 = the planted rule, 0 = unrelated or constant). Pass marks "
        f"fixed before the runs (D-101): match >= {MATCH_MIN}; the gate lets through at most "
        f"{NULL_GATE_MAX:.0%} of the null runs.", "",
        "| planted rule | planted Sharpe | planted rule: fit / val / fresh | GP: fit / val / "
        f"fresh | match | runs with match >= {FULL_MATCH} | evolution gain (p) "
        "| runs through the gate | recovered |",
        "|---|---:|---|---|---:|---:|---|---:|---|",
    ]  # fmt: skip
    for s in summary.values():
        gain = f"{s['median_gain']:+.2f} ({s['gain_p']:.3f})"
        if s["rule"] == "null":
            lines.append(
                f"| none (null) | 0 | n/a | {s['fit_sharpe']:.2f} / {s['val_sharpe']:.2f} / n/a "
                f"| n/a | n/a | {gain} | {s['gated']:.0%} | n/a |"
            )
            continue
        lines.append(
            f"| {s['rule']} | {s['sharpe']:g} "
            f"| {s['oracle_fit']:.2f} / {s['oracle_val']:.2f} / {s['oracle_fresh']:.2f} "
            f"| {s['fit_sharpe']:.2f} / {s['val_sharpe']:.2f} / {s['fresh_sharpe']:.2f} "
            f"| {s['match']:.2f} | {s['full']:.0%} | {gain} | {s['gated']:.0%} "
            f"| {'yes' if s['pass_recovery'] else 'no'} |"
        )
    lines += ["", f"**Null control:** {'holds' if decision['null_control'] else 'fails'}.", ""]
    for rule, threshold in decision["thresholds"].items():
        found = f"recovered from planted Sharpe {threshold:g}" if threshold else "not recovered"
        lines.append(f"- **{rule}** (`{E5_RULES[rule]}`): {found}.")
    lines += ["", "**Verdict:** " + (
        "the machinery is sound: it finds a planted edge and passes the null control."
        if decision["sound"] else
        "the machinery is not sound: find the fault before any further run."
    )]  # fmt: skip
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
    parser.add_argument("experiment", choices=["e1", "e1b", "e2", "e3", "e4", "e5"])
    parser.add_argument("--mode", choices=["data", "plan", "register", "run", "report"],
                        required=True)  # fmt: skip
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    paths, settings = load_paths(), load_settings()
    name, configs = {"e1": (E1, RUN_CONFIGS), "e1b": (E1B, E1B_CONFIGS),
                     "e2": (E2, E2_CONFIGS), "e3": (E3, E3_CONFIGS),
                     "e4": (E4, E4_CONFIGS), "e5": (E5, E5_CONFIGS)}[args.experiment]  # fmt: skip
    plan_path = paths.results_dir / "campaigns" / name / "tasks.json"
    if args.mode == "data":
        if args.experiment != "e5":
            parser.error("--mode data is E5's (synthetic tier S)")
        print(e5_data(paths, settings, args.workers), flush=True)
    elif args.mode == "register":
        if args.experiment != "e5":
            parser.error("--mode register is E5's (the other plans register themselves)")
        print(f"e5-TA registered: {e5_register(settings)}")
    elif args.mode == "plan":
        plans = {"e1": e1_plan, "e1b": e1b_plan, "e2": e2_plan, "e3": e3_plan, "e4": e4_plan,
                 "e5": e5_plan}  # fmt: skip
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
    elif args.experiment == "e5":
        rows = e5_evaluate(plan_path, paths, settings)
        summary = e5_summary(rows)
        decision = e5_decision(summary)
        text = e5_report(summary, decision)
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "e5.json").write_text(
            json.dumps({"summary": summary, "decision": decision}, indent=2) + "\n"
        )
        (REPORTS / "e5.md").write_text(text)
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
