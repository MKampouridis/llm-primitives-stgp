"""Shared helpers for scaling-exponent estimators."""

import numpy as np
from numba import njit

SCALES = (6, 8, 12, 16, 24, 32, 48, 64)


def scales_for(window: int, min_blocks: int) -> np.ndarray:
    """Block sizes with at least ``min_blocks`` non-overlapping blocks in the window."""
    return np.array([n for n in SCALES if n * min_blocks <= window], dtype=np.int64)


@njit(cache=True)
def ols_slope(x: np.ndarray, y: np.ndarray) -> float:
    mx, my = x.mean(), y.mean()
    num, den = 0.0, 0.0
    for k in range(len(x)):
        num += (x[k] - mx) * (y[k] - my)
        den += (x[k] - mx) * (x[k] - mx)
    return num / den
