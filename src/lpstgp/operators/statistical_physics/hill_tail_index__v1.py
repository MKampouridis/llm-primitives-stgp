"""HillTailIndex: Hill estimator of the power-law tail exponent of |x| in the window."""

import numpy as np
from numba import njit

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import LongWindow, Real, Series

TAIL_FRACTION = 0.1
MIN_TAIL = 5


@njit(cache=True)
def hill(abs_values: np.ndarray, tail_fraction: float, min_tail: int) -> float:
    a = np.sort(abs_values)[::-1]
    k = max(min_tail, int(np.floor(tail_fraction * len(a))))
    if k + 1 > len(a) or a[k] <= 0.0:
        return np.nan
    s = 0.0
    for i in range(k):
        s += np.log(a[i]) - np.log(a[k])
    return k / s if s > 0.0 else np.nan


@njit(cache=True)
def _rolling(x: np.ndarray, window: int, tail_fraction: float, min_tail: int) -> np.ndarray:
    n = len(x)
    out = np.full(n, np.nan)
    for t in range(window - 1, n):
        seg = x[t - window + 1 : t + 1]
        if np.isnan(seg).any():
            continue
        out[t] = hill(np.abs(seg), tail_fraction, min_tail)
    return out


def hill_tail_index(x: np.ndarray, window: int) -> np.ndarray:
    return _rolling(x, window, TAIL_FRACTION, MIN_TAIL)


SPEC = OperatorSpec(
    name="hill_tail_index",
    version=1,
    domain="statistical_physics",
    summary="Hill tail exponent of |x| from the top max(5, 10%) order statistics (smaller = heavier tail).",
    inputs=(Series,),
    params=(ParamSpec("window", LongWindow),),
    output=Real,
    lookback=lambda window: window,
    missing=Missing.PROPAGATE,
    definition=(
        r"\hat\alpha = k / \sum_{i=1}^{k}(\log a_{(i)} - \log a_{(k+1)}), a_{(1)}\ge a_{(2)}\ge\dots the "
        r"ordered |x_s|, k = \max(5, \lfloor 0.1 w\rfloor)"
    ),
    references=(
        "Hill (1975), Annals of Statistics 3(5):1163-1174",
        "Gopikrishnan, Plerou, Amaral, Meyer & Stanley (1999), Physical Review E 60(5):5305-5316",
    ),
    reference_test="independent numpy implementation; Pareto recovery",
    impl=hill_tail_index,
    invariances=("scale",),
)
