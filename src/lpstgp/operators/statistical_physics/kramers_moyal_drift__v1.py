"""KramersMoyalDrift: first Kramers-Moyal coefficient (drift) at the current state of the path.

Within the window the path is z-scored; the drift D1(z) = E[dz | z] is estimated by Nadaraya-Watson
kernel regression of the one-bar increments on the state, and evaluated at the latest state.
Negative values at high states indicate mean reversion, positive ones momentum.
"""

import numpy as np
from numba import njit

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import LongWindow, Path, Real


@njit(cache=True)
def drift_at_last(seg: np.ndarray) -> float:
    n = len(seg)
    mu = seg.mean()
    sd = np.sqrt(((seg - mu) ** 2).sum() / (n - 1))
    if sd <= 0.0:
        return np.nan
    z = (seg - mu) / sd
    h = 1.06 * (n - 1) ** (-0.2)  # Silverman's rule for unit-variance states
    num, den = 0.0, 0.0
    for s in range(n - 1):
        u = (z[s] - z[n - 1]) / h
        k = np.exp(-0.5 * u * u)
        num += k * (z[s + 1] - z[s])
        den += k
    if den <= 0.0:  # current state far from every past state: all kernel weights underflow
        return np.nan
    return num / den


@njit(cache=True)
def _rolling(p: np.ndarray, window: int) -> np.ndarray:
    n = len(p)
    out = np.full(n, np.nan)
    for t in range(window - 1, n):
        seg = p[t - window + 1 : t + 1]
        if np.isnan(seg).any():
            continue
        out[t] = drift_at_last(seg)
    return out


def kramers_moyal_drift(p: np.ndarray, window: int) -> np.ndarray:
    return _rolling(p, window)


SPEC = OperatorSpec(
    name="kramers_moyal_drift",
    version=1,
    domain="statistical_physics",
    summary="Kernel estimate of E[dz | z = z_t] for the z-scored path in the window (Gaussian kernel).",
    inputs=(Path,),
    params=(ParamSpec("window", LongWindow),),
    output=Real,
    lookback=lambda window: window,
    missing=Missing.PROPAGATE,
    definition=(
        r"D^{(1)}(z_t) = \frac{\sum_s K_h(z_s - z_t)(z_{s+1} - z_s)}{\sum_s K_h(z_s - z_t)}, z = window z-scores, "
        r"K_h Gaussian, h = 1.06 (w-1)^{-1/5}"
    ),
    references=(
        "Siegert, Friedrich & Peinke (1998), Physics Letters A 243(5-6):275-280",
        "Friedrich, Peinke, Sahimi & Tabar (2011), Physics Reports 506(5):87-162",
    ),
    reference_test="statsmodels KernelReg (local constant, Gaussian, fixed bandwidth)",
    impl=kramers_moyal_drift,
    invariances=("shift", "scale"),
)
