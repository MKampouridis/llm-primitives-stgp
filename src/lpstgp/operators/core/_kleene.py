"""Kleene three-valued logic on float arrays: 1 = true, 0 = false, NaN = unknown.

``np.minimum``/``np.fmin`` are *not* Kleene AND (minimum(0, NaN) is NaN, fmin(1, NaN) is 1),
so the truth tables are written out explicitly.
"""

from __future__ import annotations

import numpy as np


def truth(condition: np.ndarray, known: np.ndarray) -> np.ndarray:
    """1/0 where ``known``, NaN elsewhere."""
    return np.where(known, condition.astype(np.float64), np.nan)


def k_and(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    out = np.full(a.shape, np.nan)
    out[(a == 1.0) & (b == 1.0)] = 1.0
    out[(a == 0.0) | (b == 0.0)] = 0.0
    return out


def k_or(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    out = np.full(a.shape, np.nan)
    out[(a == 0.0) & (b == 0.0)] = 0.0
    out[(a == 1.0) | (b == 1.0)] = 1.0
    return out


def k_not(a: np.ndarray) -> np.ndarray:
    return 1.0 - a


def greater(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    known = ~np.isnan(a) & ~np.isnan(b)
    with np.errstate(invalid="ignore"):
        return truth(a > b, known)
