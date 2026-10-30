"""HiguchiFD: Higuchi fractal dimension of the path (curve) over the window."""

import numpy as np
from numba import njit

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.operators.fractal._scaling import ols_slope
from lpstgp.types import Kmax, LongWindow, Path, Real


@njit(cache=True)
def higuchi(x: np.ndarray, kmax: int) -> float:
    """Higuchi (1988): L(k) averaged over the k offsets; FD = -slope of log L(k) on log k."""
    n = len(x)
    logk = np.empty(kmax)
    logl = np.empty(kmax)
    for k in range(1, kmax + 1):
        total = 0.0
        for m in range(k):
            steps = (n - 1 - m) // k
            if steps < 1:
                return np.nan
            length = 0.0
            for i in range(1, steps + 1):
                length += abs(x[m + i * k] - x[m + (i - 1) * k])
            total += length * (n - 1) / (steps * k) / k
        mean_length = total / k
        if not (mean_length > 0.0):
            return np.nan
        logk[k - 1] = np.log(k)
        logl[k - 1] = np.log(mean_length)
    return -ols_slope(logk, logl)


@njit(cache=True)
def _rolling(p: np.ndarray, window: int, kmax: int) -> np.ndarray:
    n = len(p)
    out = np.full(n, np.nan)
    for t in range(window - 1, n):
        seg = p[t - window + 1 : t + 1]
        if np.isnan(seg).any():
            continue
        out[t] = higuchi(seg, kmax)
    return out


def higuchi_fd(p: np.ndarray, window: int, kmax: int) -> np.ndarray:
    return _rolling(p, window, kmax)


SPEC = OperatorSpec(
    name="higuchi_fd",
    version=1,
    domain="fractal",
    summary="Higuchi fractal dimension of the window's path, scales k = 1..kmax (1 smooth, 2 very rough).",
    inputs=(Path,),
    params=(ParamSpec("window", LongWindow), ParamSpec("kmax", Kmax)),
    output=Real,
    lookback=lambda window, kmax: window,
    missing=Missing.PROPAGATE,
    definition=(
        r"L_m(k) = \frac{N-1}{\lfloor\frac{N-1-m}{k}\rfloor k^2}\sum_{i=1}^{\lfloor (N-1-m)/k\rfloor}"
        r"|X_{m+ik} - X_{m+(i-1)k}|, L(k) = \overline{L_m(k)}, D = -\mathrm{slope}(\log k, \log L(k))"
    ),
    references=("Higuchi (1988), Physica D 31(2):277-283",),
    reference_test="textbook implementation; antropy.higuchi_fd within tolerance; Brownian motion ~ 1.5",
    impl=higuchi_fd,
    invariances=("shift", "scale"),
)
