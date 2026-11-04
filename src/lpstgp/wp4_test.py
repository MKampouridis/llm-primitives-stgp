"""WP4's frozen-rule evaluation (protocol_wp4 §6; D-079, D-086).

``evaluate_period`` runs every frozen rule of one period's plan on a sandbox of that period:
the VALIDATE year for the rehearsal (and the validation–test gap of H3), the TEST year at the
single read. It returns every run's daily net returns per instrument, and also what the
secondary analyses of protocol_wp4 §7 need, so none of them needs a second read (D-060, D-087):

* each run's daily decisions over the window (int8), from which the held position at any lag,
  turnover, the no-trade share and the trade count follow;
* each instrument's daily simple returns and per-bar buy and sell cost rates over the window,
  at the configured cost multiplier, so the cost sweep, lag 1 and the random-entry null are
  recomputed from the saved arrays (``replay``) without reading the test years again.

``save`` writes all of it; ``replay`` reproduces the saved net returns exactly at the configured
lag and multiplier, which ``step_test`` checks before the results are used.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

from lpstgp import pilot
from lpstgp.analysis.portfolio import Series, average_runs, equal_weight
from lpstgp.backtest import engine
from lpstgp.backtest.costs import from_meta
from lpstgp.gp.fitness import FitnessConfig
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage

BUY_AND_HOLD = "BH"


def as_test(box: Sandbox) -> Sandbox:
    """A VALIDATE sandbox seen as a test window (its validation year), for the rehearsal."""
    if box.stage is not Stage.VALIDATE:
        raise ValueError("only a VALIDATE sandbox can stand in for the test window")
    return replace(box, period=replace(box.period, test_start=box.period.val_start))


def _subset(box: Sandbox, instruments: Sequence[str]) -> Sandbox:
    return replace(box, bars=MappingProxyType({k: box[k] for k in instruments}))


@dataclass
class Evaluation:
    """One period's frozen-rule evaluation: what ``save`` writes."""

    series: dict[tuple[str, str, int], Series] = field(default_factory=dict)  # net returns
    decisions: dict[tuple[str, str, int], np.ndarray] = field(default_factory=dict)  # 0/1
    market: dict[str, dict[str, np.ndarray]] = field(default_factory=dict)  # simple, buy, sell
    lag: int = 0
    cost_multiplier: float = 1.0


def _market(bars, start: int, cfg: FitnessConfig) -> dict[str, np.ndarray]:
    costs = from_meta(bars.meta)
    costs = costs.scaled(cfg.cost_multiplier * costs.multiplier)
    buy, sell = costs.rates(len(bars.dates))
    lr = bars.log_return
    simple = np.where(np.isnan(lr), 0.0, np.expm1(np.nan_to_num(lr)))
    return {"simple": simple[start:], "buy": buy[start:], "sell": sell[start:]}


def _decisions(entry, exit_, start: int) -> np.ndarray:
    e = np.asarray(entry, dtype=np.float64)
    x = np.asarray(exit_, dtype=np.float64)
    decided = engine.decide(e, x, start)
    if np.any(decided[:start]):
        raise AssertionError("a frozen rule held a position before its window")
    return decided[start:].astype(np.int8)


def evaluate_period(
    box: Sandbox, records: Sequence[Mapping[str, Any]], cfg: FitnessConfig, frozen=()
) -> Evaluation:
    """(config, instrument, run) -> daily net returns and decisions of the frozen rule;
    buy-and-hold under config ``BH`` with run 0; per instrument the window's market arrays."""
    out = Evaluation(lag=cfg.execution_lag, cost_multiplier=cfg.cost_multiplier)
    for record in records:
        meta = record["campaign"]
        config, run = meta["config"], int(meta["run"])
        sub = _subset(box, record["instruments"])
        for name, bars, start, entry, exit_ in pilot.rule_signals(record, sub, frozen):
            out.series[(config, name, run)] = pilot._net(entry, exit_, bars, start, cfg)
            out.decisions[(config, name, run)] = _decisions(entry, exit_, start)
    for name in box.instruments:
        bars = box[name]
        start = int(np.searchsorted(bars.dates, np.datetime64(box.period.test_start)))
        ones, zeros = np.ones(len(bars.dates)), np.zeros(len(bars.dates))
        out.series[(BUY_AND_HOLD, name, 0)] = pilot._net(ones, zeros, bars, start, cfg)
        out.decisions[(BUY_AND_HOLD, name, 0)] = _decisions(ones, zeros, start)
        out.market[name] = _market(bars, start, cfg)
    return out


def replay(
    decisions: np.ndarray,
    market: Mapping[str, np.ndarray],
    lag: int,
    cost_multiplier: float = 1.0,
    base_multiplier: float = 1.0,
) -> np.ndarray:
    """Daily net returns over the window from saved decisions and market arrays, at any lag and
    cost multiplier: the backtest engine's arithmetic, starting flat at the window (D-087).
    ``base_multiplier`` is the multiplier the saved cost rates already include."""
    d = np.asarray(decisions, dtype=np.float64)
    position = engine.held(d, lag)
    change = np.diff(position, prepend=0.0)
    scale = cost_multiplier / base_multiplier
    buy, sell = market["buy"] * scale, market["sell"] * scale
    cost = np.where(change > 0, change * buy, -change * sell)
    return position * market["simple"] - cost


def check_replay(evaluation: Evaluation, atol: float = 1e-12) -> None:
    """The saved arrays reproduce every net series: nothing the analyses need is missing. Exact
    in memory; a loaded evaluation holds float32 net returns, so pass ``atol=1e-7`` for it."""
    for (config, name, run), (_dates, net) in evaluation.series.items():
        again = replay(evaluation.decisions[(config, name, run)], evaluation.market[name],
                       evaluation.lag)  # fmt: skip
        if len(again) != len(net) or not np.allclose(again, net, rtol=0, atol=atol):
            worst = float(np.max(np.abs(again - net))) if len(again) == len(net) else None
            raise AssertionError(
                f"{config} {name} run {run}: replay differs from the backtest (by {worst}; "
                f"{len(again)} vs {len(net)} bars)"
            )


def portfolios(series: Evaluation | Mapping[tuple[str, str, int], Series]) -> dict[str, Series]:
    """Per config: average all runs per instrument, then weight instruments equally."""
    if isinstance(series, Evaluation):
        series = series.series
    by_config: dict[str, dict[str, list[Series]]] = defaultdict(lambda: defaultdict(list))
    for (config, name, _run), s in series.items():
        by_config[config][name].append(s)
    return {
        c: equal_weight({n: average_runs(runs) for n, runs in by_inst.items()})
        for c, by_inst in by_config.items()
    }


def save(path: Path, evaluation: Evaluation) -> None:
    """Everything of ``evaluation``: float32 net returns and int8 decisions per (config,
    instrument, run); per instrument the dates and float64 market arrays; the lag and multiplier."""
    arrays: dict[str, np.ndarray] = {
        "lag": np.int64(evaluation.lag),
        "cost_multiplier": np.float64(evaluation.cost_multiplier),
    }
    for (config, name, run), (dates, values) in evaluation.series.items():
        key = f"dates|{name}"
        d = np.asarray(dates, dtype="datetime64[D]").astype(np.int64)
        if key in arrays and not np.array_equal(arrays[key], d):
            raise ValueError(f"{name}: series of one instrument must share their dates")
        arrays[key] = d
        arrays[f"r|{config}|{name}|{run}"] = np.asarray(values, dtype=np.float32)
        arrays[f"d|{config}|{name}|{run}"] = evaluation.decisions[(config, name, run)]
    for name, m in evaluation.market.items():
        for k, v in m.items():
            arrays[f"m|{k}|{name}"] = np.asarray(v, dtype=np.float64)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)


def load(path: Path) -> Evaluation:
    with np.load(path, allow_pickle=False) as npz:
        out = Evaluation(lag=int(npz["lag"]), cost_multiplier=float(npz["cost_multiplier"]))
        dates = {k.split("|", 1)[1]: npz[k].astype("datetime64[D]") for k in npz.files
                 if k.startswith("dates|")}  # fmt: skip
        for k in npz.files:
            kind, *rest = k.split("|")
            if kind == "r":
                config, name, run = rest
                out.series[(config, name, int(run))] = (dates[name], npz[k].astype(np.float64))
            elif kind == "d":
                config, name, run = rest
                out.decisions[(config, name, int(run))] = npz[k]
            elif kind == "m":
                field_, name = rest
                out.market.setdefault(name, {})[field_] = npz[k]
    return out
