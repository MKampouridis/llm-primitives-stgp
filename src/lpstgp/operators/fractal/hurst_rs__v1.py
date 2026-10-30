"""HurstRS: rescaled-range (R/S) Hurst exponent of the window's increments.

Blocks are aligned to the most recent bar (the oldest remainder is dropped), so the estimate always
uses the latest data.
"""

import numpy as np
from numba import njit

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.operators.fractal._scaling import ols_slope, scales_for
from lpstgp.types import LongWindow, Real, Series

MIN_BLOCKS = 2


@njit(cache=True)
def mean_rs(x: np.ndarray, n: int) -> float:
    """Average R/S over non-overlapping blocks of length n, aligned to the end of x."""
    m = len(x) // n
    start = len(x) - m * n
    total, used = 0.0, 0
    for b in range(m):
        seg = x[start + b * n : start + (b + 1) * n]
        mu = seg.mean()
        cum, lo, hi, ss = 0.0, 0.0, 0.0, 0.0
        for v in seg:
            cum += v - mu
            lo = min(lo, cum)
            hi = max(hi, cum)
            ss += (v - mu) * (v - mu)
        r = hi - lo
        s = np.sqrt(ss / n)
        if r > 0.0 and s > 0.0:
            total += r / s
            used += 1
    return total / used if used else np.nan


@njit(cache=True)
def _rolling(x: np.ndarray, window: int, scales: np.ndarray) -> np.ndarray:
    n = len(x)
    out = np.full(n, np.nan)
    k = len(scales)
    logn = np.log(scales.astype(np.float64))
    logrs = np.empty(k)
    for t in range(window - 1, n):
        seg = x[t - window + 1 : t + 1]
        if np.isnan(seg).any():
            continue
        ok = True
        for j in range(k):
            v = mean_rs(seg, scales[j])
            if not (v > 0.0):
                ok = False
                break
            logrs[j] = np.log(v)
        if ok:
            out[t] = ols_slope(logn, logrs)
    return out


def hurst_rs(x: np.ndarray, window: int) -> np.ndarray:
    return _rolling(x, window, scales_for(window, MIN_BLOCKS))


SPEC = OperatorSpec(
    name="hurst_rs",
    version=1,
    domain="fractal",
    summary="Slope of log mean R/S against log block size (blocks of 6-64 bars, at least 2 per scale).",
    inputs=(Series,),
    params=(ParamSpec("window", LongWindow),),
    output=Real,
    lookback=lambda window: window,
    missing=Missing.PROPAGATE,
    definition=(
        r"H = \mathrm{slope}(\log n, \log \overline{R/S}(n)), R = range of the cumulative mean-deviations, "
        r"S = population sd, averaged over non-overlapping blocks of length n"
    ),
    references=(
        "Hurst (1951), Transactions of the ASCE 116:770-799",
        "Mandelbrot & Wallis (1969), Water Resources Research 5(5):967-988",
    ),
    reference_test="nolds.hurst_rs(fit='poly', corrected=False, unbiased=False) on the reversed window",
    impl=hurst_rs,
    invariances=("scale",),
)
