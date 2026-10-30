"""GeneralizedHurst: generalised Hurst exponent H(q) from q-th order structure functions."""

import numpy as np
from numba import njit

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.operators.fractal._scaling import ols_slope
from lpstgp.types import LongWindow, Moment, Path, Real

TAU_MAX = 10


@njit(cache=True)
def ghe(x: np.ndarray, q: float, tau_max: int) -> float:
    logt = np.empty(tau_max)
    logk = np.empty(tau_max)
    n = len(x)
    for tau in range(1, tau_max + 1):
        total = 0.0
        for s in range(n - tau):
            total += abs(x[s + tau] - x[s]) ** q
        k = total / (n - tau)
        if not (k > 0.0):
            return np.nan
        logt[tau - 1] = np.log(tau)
        logk[tau - 1] = np.log(k)
    return ols_slope(logt, logk) / q


@njit(cache=True)
def _rolling(p: np.ndarray, window: int, q: float, tau_max: int) -> np.ndarray:
    n = len(p)
    out = np.full(n, np.nan)
    for t in range(window - 1, n):
        seg = p[t - window + 1 : t + 1]
        if np.isnan(seg).any():
            continue
        out[t] = ghe(seg, q, tau_max)
    return out


def generalized_hurst(p: np.ndarray, window: int, q: float) -> np.ndarray:
    return _rolling(p, window, q, TAU_MAX)


SPEC = OperatorSpec(
    name="generalized_hurst",
    version=1,
    domain="fractal",
    summary="H(q): slope of log E|X(s+tau)-X(s)|^q on log tau (tau = 1..10) divided by q.",
    inputs=(Path,),
    params=(ParamSpec("window", LongWindow), ParamSpec("q", Moment)),
    output=Real,
    lookback=lambda window, q: window,
    missing=Missing.PROPAGATE,
    definition=(
        r"K_q(\tau) = \langle|X_{s+\tau} - X_s|^q\rangle_s \propto \tau^{qH(q)}, "
        r"H(q) = \mathrm{slope}(\log\tau, \log K_q(\tau))/q, \tau = 1..10"
    ),
    references=(
        "Barabasi & Vicsek (1991), Physical Review A 44(4):2730-2733",
        "Di Matteo, Aste & Dacorogna (2003), Physica A 324(1-2):183-188",
    ),
    reference_test="independent numpy implementation; fractional Brownian motion recovery",
    impl=generalized_hurst,
    invariances=("shift", "scale"),
)
