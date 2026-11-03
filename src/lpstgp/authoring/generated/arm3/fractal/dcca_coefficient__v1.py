"""Detrended cross-correlation coefficient rho_DCCA(n) of two series over a trailing window."""

from __future__ import annotations

import numpy as np

from operator_api import LongWindow, Operator, Real, Series, param_kind

_MIN_VALID = 0.8

DccaBox = param_kind(
    "DccaBox", (5, 10, 20, 40), "DCCA box size n (bars): the time scale of the cross-correlation"
)


def _rho(a: np.ndarray, b: np.ndarray, n: int) -> float:
    N = len(a)
    if N < 2 * (n + 1):
        return np.nan
    r1 = np.concatenate(([0.0], np.cumsum(a - a.mean())))  # profiles, N+1 points
    r2 = np.concatenate(([0.0], np.cumsum(b - b.mean())))
    w1 = np.lib.stride_tricks.sliding_window_view(r1, n + 1)  # overlapping boxes of n+1 points
    w2 = np.lib.stride_tricks.sliding_window_view(r2, n + 1)
    i = np.arange(n + 1, dtype=np.float64)
    ic = i - i.mean()
    var_i = np.mean(ic * ic)
    c1 = w1 - w1.mean(axis=1, keepdims=True)
    c2 = w2 - w2.mean(axis=1, keepdims=True)
    s1 = (c1 * ic).mean(axis=1)
    s2 = (c2 * ic).mean(axis=1)
    f12 = np.sum((c1 * c2).mean(axis=1) - s1 * s2 / var_i)  # detrended covariance
    f11 = np.sum((c1 * c1).mean(axis=1) - s1 * s1 / var_i)
    f22 = np.sum((c2 * c2).mean(axis=1) - s2 * s2 / var_i)
    if not (f11 > 0.0 and f22 > 0.0):
        return np.nan
    return float(np.clip(f12 / np.sqrt(f11 * f22), -1.0, 1.0))


def _impl(a: np.ndarray, b: np.ndarray, window: int, box: int) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    T = len(a)
    out = np.full(T, np.nan)
    need = int(np.ceil(_MIN_VALID * window))
    for t in range(window - 1, T):
        wa = a[t - window + 1 : t + 1]
        wb = b[t - window + 1 : t + 1]
        ok = np.isfinite(wa) & np.isfinite(wb)
        if ok.sum() < need:
            continue
        out[t] = _rho(wa[ok], wb[ok], box)
    return out


OPERATOR = Operator(
    name="dcca_coefficient",
    summary=(
        "Detrended cross-correlation coefficient rho_DCCA at box scale n between two series "
        "over a trailing window (e.g. returns and absolute returns): +1 = their cumulative "
        "fluctuations co-move at that time scale, -1 = they move in opposition (e.g. falls "
        "accompanied by volatility build-ups), 0 = no scale-n cross-correlation."
    ),
    inputs=(Series, Series),
    params=(("window", LongWindow), ("box", DccaBox)),
    output=Real,
    lookback=lambda window, box: window,
    missing="min_valid",
    min_valid=_MIN_VALID,
    invariances=("scale",),
    definition=(
        "Let (x_i, y_i), i = 1..N, be the bars of the last `window` where both series are valid. "
        "Profiles R_k = sum_{i<=k} (x_i - mean x), S_k = sum_{i<=k} (y_i - mean y), k = 0..N. "
        "For each of the N-n+1 overlapping boxes of n+1 profile points, fit least-squares lines "
        "to R and S and let eps^R, eps^S be the residuals. Detrended covariances "
        "F^2_xy(n) = sum_boxes mean(eps^R eps^S), F^2_xx(n), F^2_yy(n) likewise. The output is "
        "rho_DCCA(n) = F^2_xy(n) / sqrt(F^2_xx(n) F^2_yy(n)) in [-1, 1]. It is the "
        "cross-correlation of the two series at time scale n after local trends are removed, "
        "the normalised counterpart of the DCCA fluctuation function F_xy(n) ~ n^{lambda} used "
        "to detect power-law cross-correlations in non-stationary series. Each series may be "
        "rescaled by a positive constant without changing the output."
    ),
    references=(
        "Podobnik, B., Stanley, H. E. (2008). Detrended cross-correlation analysis: a new method "
        "for analyzing two nonstationary time series. Physical Review Letters 100, 084102.",
        "Zebende, G. F. (2011). DCCA cross-correlation coefficient: quantifying level of "
        "cross-correlation. Physica A 390(4), 614-618.",
        "Kristoufek, L. (2014). Measuring correlations between non-stationary series with DCCA "
        "coefficient. Physica A 402, 291-298.",
    ),
    impl=_impl,
)
