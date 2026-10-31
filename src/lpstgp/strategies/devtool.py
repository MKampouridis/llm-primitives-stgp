"""Development-window evaluation of candidate strategies (host side of ``./backtest``, ``./check``).

The generation agent never touches data: it submits a file and gets metrics back. Data come from
the DEV period through the capped modelling store (D-036): FIT = dev-fit (the only window the
agent's backtests see), VALIDATE = dev-holdout (scored once per final strategy, never shown).
Instruments are anonymised (``I01``…, with asset class); no dates are reported.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from lpstgp.backtest.costs import from_meta
from lpstgp.config import Paths
from lpstgp.data.store import modelling_store
from lpstgp.gp.fitness import FitnessConfig, ScoredInstrument, market_part, prepare
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage, development_period
from lpstgp.strategies import execute

MIN_SCORED_BARS = {Stage.FIT: 750, Stage.VALIDATE: 450}  # ~3 of 8 years; ~90% of 2 years


@dataclass(frozen=True)
class DevData:
    stage: Stage
    inputs_path: Path  # npz: lp::<id>, lr::<id>, start::<id> (first scored bar)
    instruments: Mapping[str, str]  # anonymous id -> instrument
    asset_class: Mapping[str, str]  # anonymous id -> asset class
    scored: Mapping[str, ScoredInstrument]


def build(paths: Paths, settings: Mapping[str, Any], stage: Stage, out_dir: Path) -> DevData:
    """Sandbox the DEV window for ``stage`` and write the anonymised worker inputs."""
    period = development_period(settings)
    lmax = settings["splits"]["lookback_max_bars"]
    store = modelling_store(paths.tier_dir("A"), settings)
    lo, hi = period.scored_window(stage)
    candidates = []
    for name in store.instruments():
        meta = store.meta(name)
        if meta.get("tier") != "A" or meta.get("role", "primary") != "primary":
            continue
        candidates.append(name)
    box = Sandbox.open(store, period, stage, candidates, lmax)
    del store
    eligible = []
    for name in candidates:
        bars = box[name]
        inside = (bars.dates >= np.datetime64(lo)) & (bars.dates < np.datetime64(hi))
        if np.count_nonzero(inside & np.isfinite(bars.close)) >= MIN_SCORED_BARS[stage]:
            eligible.append(name)
    order = sorted(eligible)
    random.Random(f"dev-anonymisation-{stage.value}").shuffle(order)
    ids = {f"I{k + 1:02d}": name for k, name in enumerate(order)}
    arrays, scored, classes = {}, {}, {}
    seg = settings["fitness"]["segment_months"]
    for anon, name in ids.items():
        bars = box[name]
        data = prepare(
            bars.dates, bars.log_return, bars.calendar, (lo, hi), from_meta(bars.meta), seg
        )
        scored[anon] = data
        classes[anon] = bars.meta.get("asset_class", "")
        arrays[f"lp::{anon}"] = np.asarray(bars.log_price)
        arrays[f"lr::{anon}"] = np.asarray(bars.log_return)
        arrays[f"start::{anon}"] = np.int64(np.searchsorted(bars.dates, np.datetime64(lo)))
    out_dir.mkdir(parents=True, exist_ok=True)
    inputs = out_dir / f"dev_{stage.value}.npz"
    np.savez(inputs, **arrays)
    return DevData(stage, inputs, ids, classes, scored)


def _round(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, list):
        return [_round(v) for v in value]
    return value


def score_arrays(arrays: Mapping[str, np.ndarray], dev: DevData, cfg: FitnessConfig) -> dict:
    per, values = {}, []
    for anon in dev.instruments:
        value, parts = market_part(
            arrays[f"entry::{anon}"], arrays[f"exit::{anon}"], dev.scored[anon], cfg
        )
        values.append(value)
        per[anon] = {"asset_class": dev.asset_class[anon], "F": round(value, 4)}
        per[anon].update({k: _round(v) for k, v in parts.items()})
    values_arr = np.asarray(values)
    return {
        "objective": round(float(np.median(values_arr)), 4),
        "mean_F": round(float(values_arr.mean()), 4),
        "share_F_positive": round(float((values_arr > 0).mean()), 3),
        "no_trade_instruments": int(sum(p.get("no_trade", False) for p in per.values())),
        "instruments": per,
    }


def backtest(strategy_path: Path, job_dir: Path, dev: DevData, cfg: FitnessConfig) -> dict:
    result = execute.run("evaluate", strategy_path, job_dir, inputs_path=dev.inputs_path)
    if not result.get("ok"):
        return {
            "ok": False,
            **{k: result[k] for k in ("stage", "error", "traceback") if k in result},
        }
    return {"ok": True, **score_arrays(result["arrays"], dev, cfg)}


def check(strategy_path: Path, job_dir: Path, dev: DevData) -> dict:
    """Admission gates (no performance figures): policy, contract, behaviour, development data."""
    report = execute.run("gates", strategy_path, job_dir, inputs_path=dev.inputs_path)
    if not report.get("ok"):
        return report
    failures = [r for r in report["results"] if not r["passed"]]
    return {
        "ok": True,
        "passed": report["passed"],
        "checks": len(report["results"]),
        "failures": failures,
    }
