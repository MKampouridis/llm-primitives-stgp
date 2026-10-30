"""DFA: detrended fluctuation analysis exponent (DFA-1) of the window's increments."""

import numpy as np
from numba import njit

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.operators.fractal._scaling import ols_slope, scales_for
from lpstgp.types import LongWindow, Real, Series

MIN_BLOCKS = 4


@njit(cache=True)
def fluctuation(profile: np.ndarray, n: int) -> float:
    """RMS residual around per-box least-squares lines over all end-aligned boxes (Peng et al.)."""
    m = len(profile) // n
    start = len(profile) - m * n
    xs = np.arange(n).astype(np.float64)
    mx = xs.mean()
    sxx = ((xs - mx) ** 2).sum()
    total = 0.0
    for b in range(m):
        seg = profile[start + b * n : start + (b + 1) * n]
        my = seg.mean()
        slope = ((xs - mx) * (seg - my)).sum() / sxx
        resid = seg - (my + slope * (xs - mx))
        total += (resid * resid).sum() / n
    return np.sqrt(total / m)


@njit(cache=True)
def _rolling(x: np.ndarray, window: int, scales: np.ndarray) -> np.ndarray:
    n = len(x)
    out = np.full(n, np.nan)
    k = len(scales)
    logn = np.log(scales.astype(np.float64))
    logf = np.empty(k)
    for t in range(window - 1, n):
        seg = x[t - window + 1 : t + 1]
        if np.isnan(seg).any():
            continue
        profile = np.cumsum(seg - seg.mean())
        ok = True
        for j in range(k):
            f = fluctuation(profile, scales[j])
            if not (f > 0.0):
                ok = False
                break
            logf[j] = np.log(f)
        if ok:
            out[t] = ols_slope(logn, logf)
    return out


def dfa(x: np.ndarray, window: int) -> np.ndarray:
    return _rolling(x, window, scales_for(window, MIN_BLOCKS))


SPEC = OperatorSpec(
    name="dfa",
    version=1,
    domain="fractal",
    summary="DFA-1 scaling exponent: slope of log F(n) on log n (boxes of 6-64 bars, at least 4 per scale).",
    inputs=(Series,),
    params=(ParamSpec("window", LongWindow),),
    output=Real,
    lookback=lambda window: window,
    missing=Missing.PROPAGATE,
    definition=(
        r"\alpha = \mathrm{slope}(\log n, \log F(n)), F(n) = RMS over all boxes of the residual of the "
        r"profile Y_k = \sum_{j\le k}(x_j - \bar x) around a per-box linear fit"
    ),
    references=(
        "Peng, Buldyrev, Havlin, Simons, Stanley & Goldberger (1994), Physical Review E 49(2):1685-1689",
    ),
    reference_test="nolds.dfa(overlap=False, order=1, fit_exp='poly') on windows divisible by every scale",
    impl=dfa,
    invariances=("scale",),
)
