"""DFA-1 scaling exponent (Peng et al.) of a series over a trailing window."""

from __future__ import annotations

import numpy as np

from operator_api import LongWindow, Operator, Real, Series

_MIN_VALID = 0.8
_S_MIN = 4


def _dfa_alpha(x: np.ndarray) -> float:
    n = len(x)
    s_max = n // 4
    if s_max < _S_MIN + 2:
        return np.nan
    scales = np.unique(np.round(np.geomspace(_S_MIN, s_max, 7)).astype(int))
    y = np.cumsum(x - x.mean())  # profile
    log_s, log_f = [], []
    for s in scales:
        seg = np.lib.stride_tricks.sliding_window_view(y, s)  # all overlapping boxes
        i = np.arange(s, dtype=np.float64)
        ic = i - i.mean()
        var_i = np.mean(ic * ic)
        yc = seg - seg.mean(axis=1, keepdims=True)
        cov = (yc * ic).mean(axis=1)
        res = (yc * yc).mean(axis=1) - cov * cov / var_i  # residual variance of linear fit
        f2 = np.mean(np.maximum(res, 0.0))
        if not np.isfinite(f2) or f2 <= 0.0:
            return np.nan
        log_s.append(np.log(s))
        log_f.append(0.5 * np.log(f2))
    log_s = np.asarray(log_s)
    log_f = np.asarray(log_f)
    ls = log_s - log_s.mean()
    return float(np.sum(ls * (log_f - log_f.mean())) / np.sum(ls * ls))


def _impl(x: np.ndarray, window: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    T = len(x)
    out = np.full(T, np.nan)
    need = int(np.ceil(_MIN_VALID * window))
    for t in range(window - 1, T):
        w = x[t - window + 1 : t + 1]
        v = w[np.isfinite(w)]
        if len(v) < need:
            continue
        out[t] = _dfa_alpha(v)
    return out


OPERATOR = Operator(
    name="dfa_exponent",
    summary=(
        "Detrended fluctuation analysis (DFA-1) scaling exponent of the series over a trailing "
        "window: 0.5 = no memory, >0.5 = persistent (long-memory, trending) fluctuations, "
        "<0.5 = anti-persistent (mean-reverting) fluctuations."
    ),
    inputs=(Series,),
    params=(("window", LongWindow),),
    output=Real,
    lookback=lambda window: window,
    missing="min_valid",
    min_valid=_MIN_VALID,
    invariances=("scale",),
    definition=(
        "Let x_1..x_N be the valid values in the last `window` bars (missing bars dropped). "
        "Profile Y_k = sum_{i<=k} (x_i - mean(x)). For box sizes s on a log-spaced grid of up to "
        "7 values in [4, N/4], take all N-s+1 overlapping (gliding) boxes of s consecutive points "
        "of Y, fit a least-squares line in each box and let F(s)^2 be the mean squared residual "
        "over all boxes. The output is the DFA exponent "
        "alpha = OLS slope of log F(s) on log s. For fractional Gaussian noise alpha = H (Hurst "
        "exponent); alpha = 0.5 for uncorrelated increments, alpha > 0.5 long-range persistence, "
        "alpha < 0.5 anti-persistence; on absolute returns it measures long memory of volatility. "
        "Linear detrending removes the local mean and drift, and F scales linearly with x, so "
        "alpha is scale-free."
    ),
    references=(
        "Peng, C.-K., Buldyrev, S. V., Havlin, S., Simons, M., Stanley, H. E., Goldberger, A. L. "
        "(1994). Mosaic organization of DNA nucleotides. Physical Review E 49(2), 1685-1689.",
        "Kantelhardt, J. W., Koscielny-Bunde, E., Rego, H. H. A., Havlin, S., Bunde, A. (2001). "
        "Detecting long-range correlations with detrended fluctuation analysis. Physica A 295, "
        "441-454.",
        "Liu, Y., Gopikrishnan, P., Cizeau, P., Meyer, M., Peng, C.-K., Stanley, H. E. (1999). "
        "Statistical properties of the volatility of price fluctuations. Physical Review E 60(2), "
        "1390-1400.",
    ),
    impl=_impl,
)
