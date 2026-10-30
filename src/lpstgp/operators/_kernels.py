"""Shared numba kernels for rolling-window operators.

Every statistic is computed from the window's own values (never from running sums), so the
output at bar t depends on exactly the bars t-w+1..t: appending bars cannot change it (prefix
invariance) and bars before the window cannot change it (window locality), both bit for bit.
No ``fastmath`` (it may drop NaN checks) and no ``parallel`` (order-dependent reductions).
"""

from __future__ import annotations

import numpy as np
from numba import njit

from lpstgp.types import BIN_EDGES, N_BINS

SCALE_WINDOW = 252  # robust scale used by histogram constructors (bars)
MAD_TO_SD = 1.4826


@njit(cache=True)
def min_count(window: int, min_valid: float) -> int:
    need = int(np.ceil(min_valid * window - 1e-9))
    return max(need, 1)


@njit(cache=True)
def window_values(x: np.ndarray, end: int, window: int) -> np.ndarray:
    """Valid values of x[end-window+1 .. end] in order."""
    out = np.empty(window)
    n = 0
    for i in range(end - window + 1, end + 1):
        v = x[i]
        if not np.isnan(v):
            out[n] = v
            n += 1
    return out[:n]


@njit(cache=True)
def quantile_sorted(values: np.ndarray, q: float) -> float:
    """Linear-interpolation quantile (numpy's default method) of an already sorted array."""
    n = len(values)
    pos = q * (n - 1)
    lo = int(np.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return values[lo] + (values[hi] - values[lo]) * frac


@njit(cache=True)
def rolling_quantile(x: np.ndarray, window: int, q: float, min_valid: float) -> np.ndarray:
    n = len(x)
    out = np.full(n, np.nan)
    need = min_count(window, min_valid)
    for t in range(window - 1, n):
        vals = window_values(x, t, window)
        if len(vals) >= need:
            out[t] = quantile_sorted(np.sort(vals), q)
    return out


@njit(cache=True)
def rolling_mean_sd(x: np.ndarray, window: int, min_valid: float) -> tuple[np.ndarray, np.ndarray]:
    """Rolling mean and sample sd (ddof=1), two-pass per window."""
    n = len(x)
    mean = np.full(n, np.nan)
    sd = np.full(n, np.nan)
    need = max(min_count(window, min_valid), 2)
    for t in range(window - 1, n):
        vals = window_values(x, t, window)
        k = len(vals)
        if k >= need:
            m = 0.0
            for v in vals:
                m += v
            m /= k
            s = 0.0
            for v in vals:
                s += (v - m) * (v - m)
            mean[t] = m
            sd[t] = np.sqrt(s / (k - 1))
    return mean, sd


@njit(cache=True)
def robust_center_scale(
    x: np.ndarray, window: int, min_valid: float
) -> tuple[np.ndarray, np.ndarray]:
    """Rolling median and MAD-based sd (1.4826 * median absolute deviation)."""
    n = len(x)
    center = np.full(n, np.nan)
    scale = np.full(n, np.nan)
    need = max(min_count(window, min_valid), 2)
    for t in range(window - 1, n):
        vals = window_values(x, t, window)
        if len(vals) >= need:
            s = np.sort(vals)
            med = quantile_sorted(s, 0.5)
            dev = np.sort(np.abs(s - med))
            center[t] = med
            scale[t] = MAD_TO_SD * quantile_sorted(dev, 0.5)
    return center, scale


@njit(cache=True)
def histogram_rows(
    x: np.ndarray, window: int, offset: int, center: np.ndarray, scale: np.ndarray, min_valid: float
) -> np.ndarray:
    """Row t: distribution of x[t-offset-window+1 .. t-offset] standardised by (center[t], scale[t]).

    Fixed bins on [-4, 4] (outer bins absorb the tails) with Jeffreys smoothing (+1/2 per bin).
    """
    n = len(x)
    out = np.full((n, N_BINS), np.nan)
    need = min_count(window, min_valid)
    first = window - 1 + offset
    for t in range(first, n):
        c = center[t]
        s = scale[t]
        if np.isnan(c) or np.isnan(s) or s <= 0.0:
            continue
        counts = np.full(N_BINS, 0.5)
        k = 0
        for i in range(t - offset - window + 1, t - offset + 1):
            v = x[i]
            if np.isnan(v):
                continue
            z = (v - c) / s
            b = int(np.searchsorted(BIN_EDGES, z, side="right")) - 1
            if b < 0:
                b = 0
            elif b >= N_BINS:
                b = N_BINS - 1
            counts[b] += 1.0
            k += 1
        if k >= need:
            total = 0.0
            for b in range(N_BINS):
                total += counts[b]
            for b in range(N_BINS):
                out[t, b] = counts[b] / total
    return out


@njit(cache=True)
def rows_valid(h: np.ndarray) -> np.ndarray:
    """True where a Hist row is defined."""
    n = h.shape[0]
    ok = np.zeros(n, dtype=np.bool_)
    for t in range(n):
        ok[t] = not np.isnan(h[t, 0])
    return ok
