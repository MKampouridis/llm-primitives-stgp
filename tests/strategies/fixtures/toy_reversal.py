"""Toy strategy for tests only (never used in experiments): buy dips below a rolling quantile.

Hypothesis: prices far below their recent range revert.
"""

import numpy as np
from strategy_api import LongWindow, Quantile, Signal, Strategy, rolling_quantile


def range_position(log_price, *, window, q):
    low = rolling_quantile(log_price, window, q)
    high = rolling_quantile(log_price, window, 1.0 - q)
    width = high - low
    out = np.full(len(log_price), np.nan)
    ok = np.isfinite(width) & (width > 0)
    out[ok] = (log_price[ok] - low[ok]) / width[ok]
    return out


def rule(s):
    x = s["range_position"]
    entry = np.where(x < 0.0, 1.0, 0.0)
    exit_ = np.where(x > 0.5, 1.0, 0.0)
    entry[~np.isfinite(x)] = np.nan
    exit_[~np.isfinite(x)] = np.nan
    return entry, exit_


STRATEGY = Strategy(
    name="toy_reversal",
    domain="spectral",
    hypothesis="Prices below their recent quantile band revert.",
    definition="(p - Q_q) / (Q_{1-q} - Q_q) over a trailing window of log prices",
    references=("none (test fixture)",),
    signals=(
        Signal(
            "range_position",
            range_position,
            ("log_price",),
            {"window": LongWindow(120), "q": Quantile(0.1)},
            lambda window, q: window,
        ),
    ),
    rule=rule,
    rule_lookback=0,
)
