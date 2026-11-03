"""Multifractality degree H(1) - H(2) from generalized Hurst exponents of the path."""

from __future__ import annotations

import numpy as np

from operator_api import LongWindow, Operator, Path, Real

_MIN_VALID = 0.8
_TAUS = np.array([1, 2, 3, 5, 8, 12])


def _spread(x: np.ndarray) -> float:
    n = len(x)
    taus = _TAUS[_TAUS <= n // 4]
    if len(taus) < 4:
        return np.nan
    l1, l2 = [], []
    for tau in taus:
        d = np.abs(x[tau:] - x[:-tau])
        k1 = d.mean()
        k2 = np.mean(d * d)
        if not (k1 > 0.0 and k2 > 0.0):
            return np.nan
        l1.append(np.log(k1))
        l2.append(np.log(k2))
    lt = np.log(taus.astype(np.float64))
    lt = lt - lt.mean()
    l1 = np.asarray(l1)
    l2 = np.asarray(l2)
    denom = np.sum(lt * lt)
    h1 = np.sum(lt * (l1 - l1.mean())) / denom  # slope = 1 * H(1)
    h2 = np.sum(lt * (l2 - l2.mean())) / denom / 2.0  # slope = 2 * H(2)
    return float(h1 - h2)


def _impl(p: np.ndarray, window: int) -> np.ndarray:
    p = np.asarray(p, dtype=np.float64)
    T = len(p)
    out = np.full(T, np.nan)
    need = int(np.ceil(_MIN_VALID * window))
    for t in range(window - 1, T):
        w = p[t - window + 1 : t + 1]
        v = w[np.isfinite(w)]
        if len(v) < need:
            continue
        out[t] = _spread(v)
    return out


OPERATOR = Operator(
    name="generalized_hurst_spread",
    summary=(
        "Degree of multifractality H(1) - H(2) of the log-price path over a trailing window, from "
        "the generalized Hurst exponents of its first and second absolute moments: 0 = uniform "
        "(monofractal) scaling, positive = large moves scale more slowly than typical ones "
        "(intermittent, volatility-clustered dynamics)."
    ),
    inputs=(Path,),
    params=(("window", LongWindow),),
    output=Real,
    lookback=lambda window: window,
    missing="min_valid",
    min_valid=_MIN_VALID,
    invariances=("shift", "scale"),
    definition=(
        "Let X_1..X_N be the valid path values in the last `window` bars (missing bars dropped). "
        "For lags tau in {1, 2, 3, 5, 8, 12} (those <= N/4), the q-th order structure function "
        "is K_q(tau) = mean_t |X_{t+tau} - X_t|^q over all overlapping pairs in the window. "
        "Under scaling K_q(tau) ~ tau^{q H(q)}, so the generalized Hurst exponent H(q) is the "
        "OLS slope of log K_q(tau) on log tau divided by q. The output is "
        "Delta H = H(1) - H(2). A monofractal process (e.g. fractional Brownian motion) has "
        "H(q) constant and Delta H = 0; multiscaling (multifractal) dynamics, where the largest "
        "fluctuations scale differently from the typical ones (volatility clustering, "
        "intermittent bursts, slow aggregational convergence of fat tails), give Delta H > 0. "
        "Di Matteo et al. relate Delta H to market development: it is larger in less mature, "
        "more turbulent markets. Only increments enter (shift-invariant) and the log moments "
        "shift by constants under scaling (scale-invariant)."
    ),
    references=(
        "Di Matteo, T., Aste, T., Dacorogna, M. M. (2005). Long-term memories of developed and "
        "emerging markets: using the scaling analysis to characterize their stage of development. "
        "Journal of Banking & Finance 29(4), 827-851.",
        "Di Matteo, T. (2007). Multi-scaling in finance. Quantitative Finance 7(1), 21-36.",
        "Barabasi, A.-L., Vicsek, T. (1991). Multifractality of self-affine fractals. Physical "
        "Review A 44(4), 2730-2733.",
    ),
    impl=_impl,
)
