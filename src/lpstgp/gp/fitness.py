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

``objective = "sharpe_lcb"`` (GP development, D-090) scores the market part instead as a lower
confidence bound on the annualised net Sharpe ratio over the whole scored window,

    LCB = sqrt(P) * (SR - z * sqrt((1 - g3 * SR + (g4 - 1) / 4 * SR^2) / (n - 1)))

with SR, g3 and g4 the daily Sharpe ratio, skewness and (non-excess) kurtosis of the n daily net
returns and P bars a year (the standard error of Mertens 2002, as in the Probabilistic Sharpe
Ratio of Bailey and Lopez de Prado 2012). Few trades, few bars in the market and lumpy, lottery-
like returns all widen the margin, so a rule scores highly only when its profit is unlikely to be
luck. The no-trade and minimum-activity rules and the size penalty apply as before.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

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
    execution_lag: int = 2  # protocol §5 (lag 1 is the robustness check)
    cost_multiplier: float = 1.0
    # Minimum activity (D-041): fewer entries than ceil(rate x years of the scored window) scores
    # as no trade, so a fit cannot rest on one or two lucky trades. 0 disables the rule.
    min_entries_per_year: float = 2.0  # protocol §5 (D-041)
    # GP development (D-090): "composite" (above) or "sharpe_lcb"; z of the one-sided bound.
    objective: str = "composite"
    lcb_z: float = 1.645

    def __post_init__(self) -> None:
        if self.objective not in OBJECTIVES:
            raise ValueError(f"fitness objective {self.objective!r} is not one of {OBJECTIVES}")


OBJECTIVES = ("composite", "sharpe_lcb")
# Fields added after WP2: left out of configuration digests at their defaults (D-084, D-090).
DIGEST_DEFAULTS = {"objective": "composite", "lcb_z": 1.645}


def sharpe_lcb(net: np.ndarray, periods_per_year: int, z: float) -> float:
    """Annualised lower confidence bound of the Sharpe ratio of daily returns ``net``."""
    x = np.asarray(net, dtype=np.float64)
    n = len(x)
    sd = float(x.std())
    if n < 3 or sd == 0.0:
        return 0.0
    sr = float(x.mean()) / sd
    centred = (x - x.mean()) / sd
    skew, kurt = float(np.mean(centred**3)), float(np.mean(centred**4))
    var = max(1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr, 0.0) / (n - 1)
    return float(np.sqrt(periods_per_year) * (sr - z * np.sqrt(var)))


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
    entry: np.ndarray,
    exit_: np.ndarray,
    data: ScoredInstrument,
    cfg: FitnessConfig,
    positions: Any = None,
) -> tuple[float, dict]:
    """Market part of the fitness; ``positions``, if given, is fed the held-position vector of the
    scored window, so that rules which trade identically hash alike (hall of fame, D-029)."""
    costs = data.costs.scaled(cfg.cost_multiplier * data.costs.multiplier)
    res = engine.run(
        entry, exit_, data.log_return, costs, active_from=data.active_from, lag=cfg.execution_lag
    )
    held = res.held
    changes = np.abs(np.diff(held, prepend=0.0))
    window = slice(data.active_from, data.stop)
    if positions is not None:
        positions.update(np.ascontiguousarray(held[window], dtype=np.float64).tobytes())
    entries = int((np.diff(held, prepend=0.0)[window] > 0).sum())
    if entries == 0 and held[window].sum() == 0:  # never in the market
        return cfg.no_trade_value, {
            "trades": 0,
            "no_trade": True,
            "median_turnover": 0.0,
            "sharpe": 0.0,
            "exposure": 0.0,
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
    if not sharpes:  # every segment shorter than 2 bars: nothing to score
        return cfg.no_trade_value, {"trades": entries, "no_trade": True, "no_segments": True}
    median_sharpe = float(np.median(sharpes))
    median_dd = float(np.median(drawdowns))
    median_to = float(np.median(turnovers))
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
    years = (data.stop - data.active_from) / data.periods_per_year  # of bars with data
    required = math.floor(cfg.min_entries_per_year * years + 0.5)  # nearest: 2 years -> 4 at 2/year
    if entries < required:  # it trades, but too rarely: scored as no trade, measured as it is
        components |= {"no_trade": True, "below_min_activity": True, "required_trades": required}
        return cfg.no_trade_value, components
    if cfg.objective == "sharpe_lcb":
        value = sharpe_lcb(net, data.periods_per_year, cfg.lcb_z)
        components["sharpe_lcb"] = value
        return value, components
    value = median_sharpe - cfg.lambda_drawdown * median_dd - cfg.lambda_turnover * median_to
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
        value, c = market_part(entry, exit_, d, cfg, positions=digest)
        parts.append(value)
        comps[name] = c
    fitness = float(np.mean(parts)) - cfg.lambda_size * size_w
    return Score(fitness, {"size": size_w, "instruments": comps}, digest.hexdigest())


def mean_sharpe(score_: Score) -> float:
    values: Sequence[float] = [
        c.get("sharpe", 0.0) for c in score_.components["instruments"].values()
    ]
    return float(np.mean(values))
