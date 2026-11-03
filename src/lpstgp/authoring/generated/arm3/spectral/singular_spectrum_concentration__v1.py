"""Singular spectrum analysis: share of the leading eigentriple of the price trajectory."""

import numpy as np

from operator_api import Operator, Path, Real, Window


def _impl(p, window):
    p = np.asarray(p, dtype=np.float64)
    T = len(p)
    out = np.full(T, np.nan)
    if T < window:
        return out
    m = max(2, window // 3)
    W = np.lib.stride_tricks.sliding_window_view(p, window)
    ok = np.all(np.isfinite(W), axis=1)
    Wc = np.where(ok[:, None], W, 0.0)
    Wc = Wc - Wc.mean(axis=1, keepdims=True)
    X = np.lib.stride_tricks.sliding_window_view(Wc, m, axis=1)  # (M, K, m)
    C = np.einsum("tki,tkj->tij", X, X)
    ev = np.linalg.eigvalsh(C)
    tr = ev.sum(axis=1)
    good = ok & (tr > 0)
    share = ev[:, -1] / np.where(good, tr, 1.0)
    out[window - 1 :] = np.where(good, share, np.nan)
    return out


OPERATOR = Operator(
    name="singular_spectrum_concentration",
    summary=(
        "Singular spectrum analysis of the log-price path over a trailing window: the share of "
        "the trajectory-matrix energy carried by the leading eigentriple. Near 1 = the window is "
        "dominated by a single smooth mode (a clean trend or one slow swing); lower = energy "
        "spread over many modes (choppy, noise-like or multi-cycle path). A Brownian path gives "
        "intermediate values."
    ),
    inputs=(Path,),
    params=(("window", Window),),
    output=Real,
    lookback=lambda window: int(window),
    missing="propagate",
    definition=(
        "Let y_1..y_N be the last N = window values of the path minus their mean. Embedding "
        "dimension m = max(2, floor(N/3)), K = N - m + 1. Trajectory (Hankel) matrix "
        "X_{k,i} = y_{k+i-1}, k = 1..K, i = 1..m; lag-covariance matrix C = X^T X with "
        "eigenvalues lambda_1 >= ... >= lambda_m >= 0 (the singular spectrum, squared). "
        "Output: lambda_1 / sum_i lambda_i in [1/m, 1], the fraction of the path's energy in "
        "the leading SSA component (the discrete Karhunen-Loeve expansion of the window). "
        "Invariant to adding a constant and to positive rescaling of the path; NaN if any "
        "value in the window is missing."
    ),
    references=(
        "Broomhead, D. S. and King, G. P. (1986). Extracting qualitative dynamics from "
        "experimental data. Physica D 20(2-3), 217-236.",
        "Vautard, R., Yiou, P. and Ghil, M. (1992). Singular-spectrum analysis: a toolkit for "
        "short, noisy chaotic signals. Physica D 58(1-4), 95-126.",
        "Golyandina, N., Nekrutkin, V. and Zhigljavsky, A. (2001). Analysis of Time Series "
        "Structure: SSA and Related Techniques. Chapman & Hall/CRC.",
        "Ghil, M. et al. (2002). Advanced spectral methods for climatic time series. Reviews of "
        "Geophysics 40(1), 1003.",
    ),
    impl=_impl,
    invariances=("shift", "scale"),
)
