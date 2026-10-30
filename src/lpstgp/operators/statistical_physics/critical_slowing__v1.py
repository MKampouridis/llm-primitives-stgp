"""CriticalSlowing: lag-1 autocorrelation of linearly detrended volatility (|x|) in the window.

Rising autocorrelation of fluctuations ("critical slowing down") is a generic early-warning sign
of an approaching transition in dynamical systems.
"""

import numpy as np
from numba import njit

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import LongWindow, Real, Series


@njit(cache=True)
def ac1_detrended(y: np.ndarray) -> float:
    n = len(y)
    t = np.arange(n).astype(np.float64)
    mt, my = t.mean(), y.mean()
    slope = ((t - mt) * (y - my)).sum() / ((t - mt) ** 2).sum()
    r = y - (my + slope * (t - mt))
    r = r - r.mean()
    den = (r * r).sum()
    if den <= 0.0:
        return np.nan
    return (r[1:] * r[:-1]).sum() / den


@njit(cache=True)
def _rolling(x: np.ndarray, window: int) -> np.ndarray:
    n = len(x)
    out = np.full(n, np.nan)
    for t in range(window - 1, n):
        seg = x[t - window + 1 : t + 1]
        if np.isnan(seg).any():
            continue
        out[t] = ac1_detrended(np.abs(seg))
    return out


def critical_slowing(x: np.ndarray, window: int) -> np.ndarray:
    return _rolling(x, window)


SPEC = OperatorSpec(
    name="critical_slowing",
    version=1,
    domain="statistical_physics",
    summary="Lag-1 autocorrelation of |x| after removing a linear trend within the window.",
    inputs=(Series,),
    params=(ParamSpec("window", LongWindow),),
    output=Real,
    lookback=lambda window: window,
    missing=Missing.PROPAGATE,
    definition=(
        r"\rho_1 = \sum_{s} r_s r_{s-1} / \sum_s r_s^2, r = residuals of |x_s| on a linear time trend "
        r"(demeaned), s in the window"
    ),
    references=(
        "Scheffer, Bascompte, Brock, Brovkin, Carpenter, Dakos, Held, van Nes, Rietkerk & Sugihara (2009), "
        "Nature 461:53-59",
        "Dakos et al. (2012), PLoS ONE 7(7):e41010",
    ),
    reference_test="statsmodels.tsa.stattools.acf on the detrended window",
    impl=critical_slowing,
    invariances=("scale",),
)
