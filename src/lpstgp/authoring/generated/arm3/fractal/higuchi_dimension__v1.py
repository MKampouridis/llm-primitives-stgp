"""Higuchi fractal dimension of the price path over a trailing window."""

from __future__ import annotations

import numpy as np

from operator_api import Operator, Path, Real, Window

_MIN_VALID = 0.8
_K_CAP = 10


def _higuchi(x: np.ndarray) -> float:
    n = len(x)
    kmax = max(3, min(_K_CAP, n // 5))
    if n < 2 * kmax + 1:
        return np.nan
    log_k, log_l = [], []
    for k in range(1, kmax + 1):
        d = np.abs(x[k:] - x[:-k])  # |X(i+k) - X(i)|, i = 0..n-k-1
        m = np.arange(n - k) % k  # starting offset of each curve
        sums = np.bincount(m, weights=d, minlength=k)
        counts = np.bincount(m, minlength=k)
        lm = sums * (n - 1) / (counts * k) / k  # normalised curve length L_m(k)
        lk = lm.mean()
        if not np.isfinite(lk) or lk <= 0.0:
            return np.nan
        log_k.append(np.log(k))
        log_l.append(np.log(lk))
    log_k = np.asarray(log_k)
    log_l = np.asarray(log_l)
    lk_c = log_k - log_k.mean()
    return float(-np.sum(lk_c * (log_l - log_l.mean())) / np.sum(lk_c * lk_c))


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
        out[t] = _higuchi(v)
    return out


OPERATOR = Operator(
    name="higuchi_dimension",
    summary=(
        "Higuchi fractal dimension of the log-price curve over a trailing window: near 1 = a "
        "smooth, directional path, near 1.5 = a Brownian-like path, near 2 = a rough, "
        "space-filling, choppy path."
    ),
    inputs=(Path,),
    params=(("window", Window),),
    output=Real,
    lookback=lambda window: window,
    missing="min_valid",
    min_valid=_MIN_VALID,
    invariances=("shift", "scale"),
    definition=(
        "Let X_1..X_N be the valid path values in the last `window` bars (missing bars dropped). "
        "For lags k = 1..kmax with kmax = max(3, min(10, floor(N/5))) and offsets m = 1..k, the "
        "normalised length of the subsampled curve X_m, X_{m+k}, X_{m+2k}, ... is "
        "L_m(k) = [ sum_{i=1}^{n_m} |X_{m+ik} - X_{m+(i-1)k}| ] * (N-1) / (n_m k) / k, with "
        "n_m = floor((N-m)/k). With L(k) = mean_m L_m(k), the curve length scales as "
        "L(k) ~ k^{-D}; the output is D = -(OLS slope of log L(k) on log k). D is the fractal "
        "(box/curve-length) dimension of the graph: 1 for a smooth trend, 1.5 for Brownian "
        "motion, 2 - H for fractional Brownian motion of Hurst index H, toward 2 for a jagged, "
        "oscillating path. Only differences enter (shift-invariant) and a scale factor c "
        "multiplies every L(k) by c (scale-invariant)."
    ),
    references=(
        "Higuchi, T. (1988). Approach to an irregular time series on the basis of the fractal "
        "theory. Physica D 31(2), 277-283.",
        "Mandelbrot, B. B. (1982). The Fractal Geometry of Nature. W. H. Freeman, New York.",
        "Gneiting, T., Schlather, M. (2004). Stochastic models that separate fractal dimension "
        "and the Hurst effect. SIAM Review 46(2), 269-282.",
    ),
    impl=_impl,
)
