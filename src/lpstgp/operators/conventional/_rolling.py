"""Finite-window kernels for the conventional indicators (exact window locality)."""

import numpy as np
from numba import njit

EMA_SPANS_PER_WINDOW = 6  # truncate EMA(span) after 6*span bars: weight left < e^-10
WILDER_PERIODS_PER_WINDOW = 8  # truncate Wilder(n) after 8*n bars (capped at 252)
MAX_TRUNCATION = 252


@njit(cache=True)
def rolling_mean(x: np.ndarray, window: int) -> np.ndarray:
    n = len(x)
    out = np.full(n, np.nan)
    for t in range(window - 1, n):
        seg = x[t - window + 1 : t + 1]
        if not np.isnan(seg).any():
            out[t] = seg.mean()
    return out


@njit(cache=True)
def rolling_std(x: np.ndarray, window: int, ddof: int) -> np.ndarray:
    n = len(x)
    out = np.full(n, np.nan)
    for t in range(window - 1, n):
        seg = x[t - window + 1 : t + 1]
        if not np.isnan(seg).any():
            m = seg.mean()
            out[t] = np.sqrt(((seg - m) ** 2).sum() / (window - ddof))
    return out


@njit(cache=True)
def rolling_extreme(x: np.ndarray, window: int, upper: bool) -> np.ndarray:
    n = len(x)
    out = np.full(n, np.nan)
    for t in range(window - 1, n):
        seg = x[t - window + 1 : t + 1]
        if not np.isnan(seg).any():
            out[t] = seg.max() if upper else seg.min()
    return out


@njit(cache=True)
def truncated_ema(x: np.ndarray, alpha: float, length: int) -> np.ndarray:
    """EMA with weights alpha(1-alpha)^j over the last `length` values, renormalised to sum 1."""
    n = len(x)
    out = np.full(n, np.nan)
    w = np.empty(length)
    for j in range(length):
        w[j] = (1.0 - alpha) ** j
    w /= w.sum()
    for t in range(length - 1, n):
        acc = 0.0
        ok = True
        for j in range(length):
            v = x[t - j]
            if np.isnan(v):
                ok = False
                break
            acc += w[j] * v
        if ok:
            out[t] = acc
    return out


def ema_length(span: int) -> int:
    return min(EMA_SPANS_PER_WINDOW * span, MAX_TRUNCATION)


def wilder_length(n: int) -> int:
    return min(WILDER_PERIODS_PER_WINDOW * n, MAX_TRUNCATION)
