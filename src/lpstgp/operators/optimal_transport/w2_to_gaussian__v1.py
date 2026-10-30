"""W2ToGaussian: Wasserstein-2 distance from the standardised window distribution to N(0, 1).

Exact for an empirical measure against the normal law: on each atom's quantile interval
[(i-1)/n, i/n] the integrals of Phi^{-1} and (Phi^{-1})^2 have closed forms.
"""

import numpy as np
from scipy.special import ndtr, ndtri

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import LongWindow, Real, Series


def _interval_terms(n: int) -> tuple[np.ndarray, np.ndarray]:
    """For atom i (1..n): integral of Phi^{-1} and of (Phi^{-1})^2 over [(i-1)/n, i/n]."""
    q = ndtri(np.arange(n + 1) / n)  # q_0 = -inf, q_n = +inf
    phi = np.exp(-0.5 * q**2) / np.sqrt(2.0 * np.pi)
    phi[[0, -1]] = 0.0
    second = ndtr(q) - np.where(np.isfinite(q), q * phi, 0.0)  # G(q) = Phi(q) - q phi(q)
    first_moment = phi[:-1] - phi[1:]
    second_moment = second[1:] - second[:-1]
    return first_moment, second_moment


def w2_to_gaussian(x: np.ndarray, window: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) < window:
        return out
    windows = np.lib.stride_tricks.sliding_window_view(x, window)
    z = np.sort(windows, axis=1)
    mean = z.mean(axis=1, keepdims=True)
    sd = z.std(axis=1, ddof=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (z - mean) / sd
    m1, m2 = _interval_terms(window)
    w2sq = (z**2).sum(axis=1) / window - 2.0 * (z * m1).sum(axis=1) + m2.sum()
    value = np.sqrt(np.maximum(w2sq, 0.0))
    bad = np.isnan(windows).any(axis=1) | ~(sd[:, 0] > 0)
    value[bad] = np.nan
    out[window - 1 :] = value
    return out


SPEC = OperatorSpec(
    name="w2_to_gaussian",
    version=1,
    domain="optimal_transport",
    summary="W2 distance between the z-scored window and the standard normal: a transport non-Gaussianity.",
    inputs=(Series,),
    params=(ParamSpec("window", LongWindow),),
    output=Real,
    lookback=lambda window: window,
    missing=Missing.PROPAGATE,
    definition=r"W_2(\hat\mu_t, N(0,1)) = \left(\int_0^1 (F_n^{-1}(u) - \Phi^{-1}(u))^2 du\right)^{1/2}, \hat\mu_t of z-scores",
    references=(
        "del Barrio, Cuesta-Albertos, Matran & Rodriguez-Rodriguez (1999), Annals of Statistics 27(4):1230-1239",
        "Villani (2009), Optimal Transport: Old and New, Springer, ch. 6",
    ),
    reference_test="numerical quadrature of the quantile-function integral (scipy.integrate.quad)",
    impl=w2_to_gaussian,
    invariances=("scale",),
)
