"""Shared rough-path kernels: window normalisation, Levy area and truncated signatures (Chen)."""

import numpy as np
from numba import njit


@njit(cache=True)
def standardised_increments(p: np.ndarray, t: int, window: int) -> np.ndarray:
    """Increments of p over (t-window, t], divided by their sample sd; empty if undefined."""
    d = np.empty(window)
    for k in range(window):
        a, b = p[t - window + k], p[t - window + k + 1]
        if np.isnan(a) or np.isnan(b):
            return np.empty(0)
        d[k] = b - a
    m = d.mean()
    s = 0.0
    for v in d:
        s += (v - m) * (v - m)
    sd = np.sqrt(s / (window - 1))
    if sd <= 0.0:
        return np.empty(0)
    return d / sd


@njit(cache=True)
def levy_area(dx: np.ndarray, dy: np.ndarray) -> float:
    """Signed Levy area of the piecewise-linear path started at the origin with these increments."""
    x, y, area = 0.0, 0.0, 0.0
    for k in range(len(dx)):
        area += x * dy[k] - y * dx[k]
        x += dx[k]
        y += dy[k]
    return 0.5 * area


@njit(cache=True)
def signature3(dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
    """Levels 1-3 of the signature of a 2-d piecewise-linear path (14 terms, word order 1,2,11,12,...)."""
    s1 = np.zeros(2)
    s2 = np.zeros((2, 2))
    s3 = np.zeros((2, 2, 2))
    v = np.zeros(2)
    for k in range(len(dx)):
        v[0], v[1] = dx[k], dy[k]
        # Chen: S <- S (x) exp(v), truncated at level 3, using the old S on the right-hand side.
        for i in range(2):
            for j in range(2):
                for m in range(2):
                    s3[i, j, m] += (
                        s2[i, j] * v[m] + s1[i] * v[j] * v[m] / 2.0 + v[i] * v[j] * v[m] / 6.0
                    )
        for i in range(2):
            for j in range(2):
                s2[i, j] += s1[i] * v[j] + v[i] * v[j] / 2.0
        for i in range(2):
            s1[i] += v[i]
    out = np.empty(14)
    out[0:2] = s1
    out[2:6] = s2.ravel()
    out[6:14] = s3.ravel()
    return out
