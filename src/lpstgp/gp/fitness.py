"""Robustness-composite fitness (training data only).

For each instrument the rule is backtested continuously over the scored window, starting flat, and
the window is cut into calendar segments (half-years by default):

    F = median_k S_k - l_dd * median_k (MDD_k / sigma) - l_to * median_k TO_k - l_size * size_w

S_k is the net-of-cost Sharpe of segment k, set to 0 if the rule held a position on fewer than
``min_exposure_bars`` bars there (a handful of lucky bars must not score); MDD_k / sigma is the
segment drawdown in units of the instrument's annualised volatility over the window (scale-free
across asset classes); TO_k is annualised one-way turnover; size_w is the weighted size of both
trees (parameters, data terminals and type constructors weigh 0). A rule that never trades scores
``no_trade_value``. With several instruments (pooled fitness) the market part is averaged.
The weights are placeholders, to be set on a named pilot period in WP2 and then frozen.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np

from lpstgp.backtest import engine
from lpstgp.backtest.costs import CostModel
from lpstgp.backtest.metrics import PERIODS_PER_YEAR, max_drawdown, sharpe


@dataclass(frozen=True)
class FitnessConfig:
    lambda_drawdown: float = 0.5
    lambda_turnover: float = 0.005
    lambda_size: float = 0.01
    min_exposure_bars: int = 10
    no_trade_value: float = -1.0
    segment_months: int = 6
    execution_lag: int = 1
    cost_multiplier: float = 1.0
    # Minimum activity (D-041): fewer entries than ceil(rate x years of the scored window) scores
    # as no trade, so a fit cannot rest on one or two lucky trades. 0 disables the rule.
    min_entries_per_year: float = 0.0


def add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    return day.replace(year=day.year + month // 12, month=month % 12 + 1)


def segment_bounds(start: date, end: date, months: int) -> list[tuple[date, date]]:
    bounds, lo = [], start
    while lo < end:
        hi = min(add_months(lo, months), end)
        bounds.append((lo, hi))
        lo = hi
    return bounds


@dataclass(frozen=True)
class ScoredInstrument:
    """One instrument's arrays (sandbox-aligned) and the bars of the scored window."""

    log_return: np.ndarray
    active_from: int  # index of the first scored bar: the rule starts flat here
    stop: int  # index after the last scored bar
    segments: tuple[tuple[int, int], ...]
    periods_per_year: int
    sigma: float  # annualised volatility of the instrument over the scored window
    costs: CostModel


def prepare(
    dates: np.ndarray,
    log_return: np.ndarray,
    calendar: str,
    window: tuple[date, date],
    costs: CostModel,
    segment_months: int,
) -> ScoredInstrument:
    lo, hi = window
    d = np.asarray(dates, dtype="datetime64[D]")
    start = int(np.searchsorted(d, np.datetime64(lo)))
    stop = int(np.searchsorted(d, np.datetime64(hi)))
    segments = tuple(
        (int(np.searchsorted(d, np.datetime64(a))), int(np.searchsorted(d, np.datetime64(b))))
        for a, b in segment_bounds(lo, hi, segment_months)
    )
    ppy = PERIODS_PER_YEAR[calendar]
    simple = np.expm1(np.nan_to_num(np.asarray(log_return)[start:stop]))
    sigma = float(simple.std(ddof=1) * np.sqrt(ppy)) if stop - start > 2 else float("nan")
    return ScoredInstrument(np.asarray(log_return), start, stop, segments, ppy, sigma, costs)


@dataclass(frozen=True)
class Score:
    fitness: float
    components: dict
    signal_hash: str


def signal_hash(entry: np.ndarray, exit_: np.ndarray, lo: int, hi: int) -> str:
    digest = hashlib.sha1()
    digest.update(np.ascontiguousarray(entry[lo:hi]).tobytes())
    digest.update(np.ascontiguousarray(exit_[lo:hi]).tobytes())
    return digest.hexdigest()


def market_part(
    entry: np.ndarray, exit_: np.ndarray, data: ScoredInstrument, cfg: FitnessConfig
) -> tuple[float, dict]:
    costs = data.costs.scaled(cfg.cost_multiplier * data.costs.multiplier)
    res = engine.run(
        entry, exit_, data.log_return, costs, active_from=data.active_from, lag=cfg.execution_lag
    )
    held = res.held
    changes = np.abs(np.diff(held, prepend=0.0))
    window = slice(data.active_from, data.stop)
    entries = int((np.diff(held, prepend=0.0)[window] > 0).sum())
    if entries == 0 and held[window].sum() == 0:
        return cfg.no_trade_value, {"trades": 0, "no_trade": True}
    years = (data.stop - data.active_from) / data.periods_per_year  # of bars with data
    required = math.floor(cfg.min_entries_per_year * years + 0.5)  # nearest: 2 years -> 4 at 2/year
    if entries < required:
        return cfg.no_trade_value, {
            "trades": entries,
            "no_trade": True,
            "required_trades": required,
        }
    sharpes, drawdowns, turnovers = [], [], []
    for lo, hi in data.segments:
        if hi - lo < 2:
            continue
        net = res.net[lo:hi]
        exposed = held[lo:hi].sum()
        sharpes.append(
            float(sharpe(net, data.periods_per_year)) if exposed >= cfg.min_exposure_bars else 0.0
        )
        drawdowns.append(float(max_drawdown(net)) / data.sigma if data.sigma > 0 else 0.0)
        turnovers.append(float(changes[lo:hi].sum() * data.periods_per_year / (hi - lo)))
    median_sharpe = float(np.median(sharpes))
    median_dd = float(np.median(drawdowns))
    median_to = float(np.median(turnovers))
    value = median_sharpe - cfg.lambda_drawdown * median_dd - cfg.lambda_turnover * median_to
    net = res.net[window]
    components = {
        "median_sharpe": median_sharpe,
        "median_dd_sigma": median_dd,
        "median_turnover": median_to,
        "segment_sharpes": sharpes,
        "sharpe": float(sharpe(net, data.periods_per_year)),
        "max_drawdown": float(max_drawdown(net)),
        "total_return": float(np.prod(1.0 + net) - 1.0),
        "trades": entries,
        "exposure": float(held[window].mean()),
        "no_trade": False,
    }
    return value, components


def score(
    signals: Mapping[str, tuple[np.ndarray, np.ndarray]],
    data: Mapping[str, ScoredInstrument],
    size_w: int,
    cfg: FitnessConfig,
) -> Score:
    """Fitness of one rule given its entry/exit signals on every instrument."""
    parts, comps, digest = [], {}, hashlib.sha1()
    for name in sorted(signals):
        entry, exit_ = signals[name]
        d = data[name]
        value, c = market_part(entry, exit_, d, cfg)
        parts.append(value)
        comps[name] = c
        digest.update(signal_hash(entry, exit_, d.active_from, d.stop).encode())
    fitness = float(np.mean(parts)) - cfg.lambda_size * size_w
    return Score(fitness, {"size": size_w, "instruments": comps}, digest.hexdigest())


def mean_sharpe(score_: Score) -> float:
    values: Sequence[float] = [
        c.get("sharpe", 0.0) for c in score_.components["instruments"].values()
    ]
    return float(np.mean(values))
