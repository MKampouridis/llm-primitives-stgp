"""Toy strategy for tests only (never used in experiments): trend filter with a volatility cap.

Hypothesis: positive average returns persist while volatility is not unusually high.
"""

import numpy as np
from strategy_api import (
    LongWindow,
    Signal,
    Strategy,
    Window,
    rolling_mean,
    rolling_quantile,
    rolling_std,
)


def trend(log_return, *, window):
    return rolling_mean(log_return, window)


def volatility(abs_return, *, window):
    return rolling_std(abs_return, window)


def gap(log_price, *, window):
    return log_price - rolling_mean(log_price, window)


def rule(s):
    high_vol = s["volatility"] > rolling_quantile(s["volatility"], 120, 0.8)
    entry = np.where((s["trend"] > 0) & ~high_vol & (s["gap"] > 0), 1.0, 0.0)
    exit_ = np.where((s["trend"] < 0) | high_vol, 1.0, 0.0)
    unknown = ~np.isfinite(s["trend"] + s["volatility"] + s["gap"])
    entry[unknown] = np.nan
    exit_[unknown] = np.nan
    return entry, exit_


STRATEGY = Strategy(
    name="toy_trend",
    domain="statistical_physics",
    hypothesis="Positive drift persists in calm regimes.",
    definition="mean of the last w returns; sd of |r|; log price minus its moving average",
    references=("none (test fixture)",),
    signals=(
        Signal("trend", trend, ("log_return",), {"window": Window(20)}, lambda window: window),
        Signal(
            "volatility",
            volatility,
            ("abs_return",),
            {"window": LongWindow(60)},
            lambda window: window,
        ),
        Signal("gap", gap, ("log_price",), {"window": Window(40)}, lambda window: window),
    ),
    rule=rule,
    rule_lookback=119,
)
