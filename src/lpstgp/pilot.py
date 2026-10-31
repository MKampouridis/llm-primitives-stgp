"""Pilot test evaluation (WP2-M4): frozen rules on the PL1/PL2 test years, once.

1. ``manifest_rules`` hashes the final rule of every task of the go/no-go campaign(s);
   ``lpstgp.freeze.write_manifest`` writes them, and the manifest must be committed to git.
2. ``evaluate_on_test`` re-evaluates one frozen rule on a TEST sandbox of a pilot period
   (``Sandbox.open_pilot_test``), starting flat at the test start, with the protocol's costs
   and execution lag, and returns the daily net returns of the test window per instrument.
3. ``go_no_go`` builds equal-weight portfolios (all runs averaged per instrument) and applies the
   pre-registered rule of protocol §8.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from lpstgp.analysis.inference import paired_bootstrap
from lpstgp.analysis.portfolio import Series, average_runs, equal_weight
from lpstgp.backtest import engine
from lpstgp.backtest.costs import from_meta
from lpstgp.backtest.metrics import sharpe
from lpstgp.gp.evaluate import TreeEvaluator
from lpstgp.gp.fitness import FitnessConfig
from lpstgp.gp.pset import build
from lpstgp.libraries import resolve
from lpstgp.sandbox import Sandbox
from lpstgp.strategies.adapters import Frozen

GO_MARGIN = 0.2  # protocol §8: GO if Sharpe(2c) - Sharpe(arm 1), pooled, >= -0.2


def rule_of(record: Mapping[str, Any]) -> dict[str, Any]:
    """What is frozen for a task: the selected GP rule, or arm 1's selected strategy."""
    if record.get("kind") == "select":
        return {
            "kind": "select",
            "strategies_lock": record["library"]["strategies_lock"],
            "selected": {k: v["selected"] for k, v in sorted(record["selection"].items())},
        }
    best = record["hall_of_fame"][record["selected"]]
    return {
        "kind": "gp",
        "library": record["library"]["name"],
        "entry": best["entry"],
        "exit": best["exit"],
    }


def rule_hash(record: Mapping[str, Any]) -> str:
    text = json.dumps(rule_of(record), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def manifest_rules(records: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    return {r["campaign"]["task_id"]: rule_hash(r) for r in records}


def _net(entry, exit_, bars, start: int, cfg: FitnessConfig) -> Series:
    costs = from_meta(bars.meta)
    costs = costs.scaled(cfg.cost_multiplier * costs.multiplier)
    res = engine.run(entry, exit_, bars.log_return, costs, active_from=start, lag=cfg.execution_lag)
    return bars.dates[start:], res.net[start:]


def evaluate_on_test(
    record: Mapping[str, Any],
    box: Sandbox,
    cfg: FitnessConfig,
    frozen: Sequence[Frozen] = (),
) -> dict[str, Series]:
    """Daily net returns of one frozen rule on the test window of ``box`` (a TEST sandbox)."""
    rule = rule_of(record)
    out: dict[str, Series] = {}
    by_sid = {f.sid: f for f in frozen}
    if rule["kind"] == "gp":
        lib = build(resolve(rule["library"], frozen or None))
        entry, exit_ = lib.from_names(rule["entry"]), lib.from_names(rule["exit"])
    for name in box.instruments:
        bars = box[name]
        start = int(np.searchsorted(bars.dates, np.datetime64(box.period.test_start)))
        if rule["kind"] == "gp":
            ev = TreeEvaluator(lib, bars.log_price, bars.log_return)
            signals = (ev(entry), ev(exit_))
        else:
            signals = by_sid[rule["selected"][name]].strategy.run(bars.log_price, bars.log_return)
        out[name] = _net(*signals, bars, start, cfg)
    return out


def buy_and_hold(box: Sandbox, cfg: FitnessConfig) -> dict[str, Series]:
    out = {}
    for name in box.instruments:
        bars = box[name]
        start = int(np.searchsorted(bars.dates, np.datetime64(box.period.test_start)))
        ones, zeros = np.ones(len(bars.dates)), np.zeros(len(bars.dates))
        out[name] = _net(ones, zeros, bars, start, cfg)
    return out


def portfolio(runs_by_instrument: Mapping[str, Sequence[Series]]) -> Series:
    """Average all runs per instrument, then weight instruments equally (protocol §8)."""
    return equal_weight({name: average_runs(runs) for name, runs in runs_by_instrument.items()})


def _aligned(a: Series, b: Series) -> tuple[np.ndarray, np.ndarray]:
    dates = np.intersect1d(a[0], b[0])
    return a[1][np.isin(a[0], dates)], b[1][np.isin(b[0], dates)]


def go_no_go(
    pooled: Mapping[str, Series],
    yearly: Mapping[str, Mapping[str, Series]],
    reference: str = "1",
    candidate: str = "2c",
    resamples: int = 10_000,
) -> dict[str, Any]:
    """``pooled[arm]`` spans both pilot test years; ``yearly[period][arm]`` one year each."""
    sharpes = {arm: float(sharpe(s[1], 252)) for arm, s in pooled.items()}
    per_year = {
        p: {arm: float(sharpe(s[1], 252)) for arm, s in arms.items()} for p, arms in yearly.items()
    }
    comparisons = {}
    for arm in sorted(pooled):
        if arm == reference:
            continue
        a, b = _aligned(pooled[arm], pooled[reference])
        result = paired_bootstrap(a, b, resamples=resamples, seed=0)
        comparisons[f"{arm} - {reference}"] = vars(result)
    difference = sharpes[candidate] - sharpes[reference]
    return {
        "rule": f"GO if Sharpe({candidate}) - Sharpe({reference}), pooled, >= -{GO_MARGIN}",
        "difference": difference,
        "decision": "GO" if difference >= -GO_MARGIN else "NO-GO",
        "pooled_sharpe": sharpes,
        "yearly_sharpe": per_year,
        "comparisons": comparisons,
    }
