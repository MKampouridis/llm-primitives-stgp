"""LaggedMutualInfo: mutual information between x_s and x_{s-lag} within the window."""

import numpy as np
from numba import njit

from lpstgp.operators._kernels import min_count, quantile_sorted
from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import Lag, LongWindow, Real, Series

MIN_VALID = 0.9
N_SYMBOLS = 4


@njit(cache=True)
def _lagged_mi(x: np.ndarray, window: int, lag: int, bins: int, min_valid: float) -> np.ndarray:
    n = len(x)
    out = np.full(n, np.nan)
    pairs = window - lag
    need = max(min_count(pairs, min_valid), 8)
    thresholds = np.empty(bins - 1)
    values = np.empty(window)
    for t in range(window - 1, n):
        k = 0
        for i in range(t - window + 1, t + 1):
            if not np.isnan(x[i]):
                values[k] = x[i]
                k += 1
        if k < 2:
            continue
        ordered = np.sort(values[:k])
        for b in range(1, bins):
            thresholds[b - 1] = quantile_sorted(ordered, b / bins)
        joint = np.zeros((bins, bins))
        count = 0
        for s in range(t - window + 1 + lag, t + 1):
            a, c = x[s], x[s - lag]
            if np.isnan(a) or np.isnan(c):
                continue
            ia = int(np.searchsorted(thresholds, a, side="right"))
            ic = int(np.searchsorted(thresholds, c, side="right"))
            joint[ia, ic] += 1.0
            count += 1
        if count < need:
            continue
        joint /= count
        pa = joint.sum(axis=1)
        pc = joint.sum(axis=0)
        mi = 0.0
        for i in range(bins):
            for j in range(bins):
                if joint[i, j] > 0:
                    mi += joint[i, j] * np.log(joint[i, j] / (pa[i] * pc[j]))
        out[t] = mi / np.log(bins)
    return out


def lagged_mutual_info(x: np.ndarray, window: int, lag: int) -> np.ndarray:
    return _lagged_mi(x, window, lag, N_SYMBOLS, MIN_VALID)


SPEC = OperatorSpec(
    name="lagged_mutual_info",
    version=1,
    domain="information_theory",
    summary="Mutual information of (x_s, x_{s-lag}) pairs in the window, on 4 equal-frequency bins, / log 4.",
    inputs=(Series,),
    params=(ParamSpec("window", LongWindow), ParamSpec("lag", Lag)),
    output=Real,
    lookback=lambda window, lag: window,
    missing=Missing.MIN_VALID,
    min_valid=MIN_VALID,
    definition=(
        r"I = \sum_{a,b} p(a,b)\log\frac{p(a,b)}{p(a)p(b)} / \log 4, over symbol pairs "
        r"(q(x_s), q(x_{s-\ell})), s, s-\ell in the window, q = within-window quartile bin"
    ),
    references=(
        "Fraser & Swinney (1986), Physical Review A 33(2):1134-1140",
        "Cover & Thomas (2006), Elements of Information Theory, 2nd ed., Wiley, ch. 2",
    ),
    reference_test="sklearn.metrics.mutual_info_score on the window's symbol pairs",
    impl=lagged_mutual_info,
    invariances=("scale",),
)
