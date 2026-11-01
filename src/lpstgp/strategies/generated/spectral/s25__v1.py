"""SSA residual reversion.

Singular-spectrum analysis (SSA) splits a trailing window of log prices into its leading
eigentriple (the slow, low-frequency "trend" component) and the remaining higher-frequency
components (the residual). The strategy buys when the current price sits well below its SSA
trend (a negative high-frequency excursion) and sells once the price has overshot above it.
"""

from __future__ import annotations

import numpy as np

from strategy_api import Signal, Strategy, Window


def _ssa_residual_z(log_price, *, window):
    """Standardised SSA residual at the last bar of each trailing window.

    For each t: s = x[t-L+1..t] - mean, embedding M = L//2, trajectory matrix X (K x M, K=L-M+1),
    leading eigenvector v of X^T X, principal component y = X v, rank-1 reconstruction by
    diagonal averaging rec = conv(y, v) / conv(1_K, 1_M), residual e = s - rec,
    z_t = e[L-1] / std(e).
    """
    x = np.asarray(log_price, dtype=np.float64)
    L = int(window)
    n = len(x)
    z = np.full(n, np.nan)
    if n < L:
        return z
    M = max(4, L // 2)
    K = L - M + 1
    segs = np.lib.stride_tricks.sliding_window_view(x, L)  # (n-L+1, L)
    ok = np.all(np.isfinite(segs), axis=1)
    idx = np.nonzero(ok)[0]
    if idx.size == 0:
        return z
    S = segs[idx] - segs[idx].mean(axis=1, keepdims=True)
    X = np.lib.stride_tricks.sliding_window_view(S, M, axis=1)  # (N, K, M) trajectory matrices
    C = np.matmul(np.transpose(X, (0, 2, 1)), X)  # (N, M, M) lag-covariance matrices
    _, V = np.linalg.eigh(C)
    v = V[:, :, -1]  # leading eigenvector
    y = np.einsum("nkm,nm->nk", X, v)  # leading principal component
    cnt = np.convolve(np.ones(K), np.ones(M))
    rec = np.empty_like(S)
    for i in range(S.shape[0]):
        rec[i] = np.convolve(y[i], v[i]) / cnt  # Hankelisation (diagonal averaging) of y v^T
    res = S - rec
    sd = np.std(res, axis=1)
    good = sd > 0
    z[idx[good] + L - 1] = res[good, -1] / sd[good]
    return z


SSA_RESID = Signal(
    name="ssa_resid",
    fn=_ssa_residual_z,
    inputs=("log_price",),
    params={"window": Window(60)},
    lookback=lambda window: window,
    description="standardised residual of log price from its rank-1 SSA reconstruction "
    "(window L, embedding L/2)",
)

K_ENTRY = -1.0  # enter when price is 1 residual-sd below the SSA trend
K_EXIT = 1.0  # exit when price is 1 residual-sd above the SSA trend


def _rule(sig):
    z = sig["ssa_resid"]
    f = np.isfinite(z)
    entry = np.where(f, (z < K_ENTRY).astype(float), np.nan)
    exit_ = np.where(f, (z > K_EXIT).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="ssa_residual_reversion",
    domain="spectral",
    hypothesis=(
        "Daily log prices are well described over a ~3-month window by a slow component, the "
        "leading eigentriple of the SSA (singular-spectrum) decomposition, plus higher-frequency "
        "components. Excursions carried by the high-frequency part are transient: when the "
        "price falls well below its leading SSA component, it tends to come back to it and "
        "overshoot. A long-only position bought on negative residual excursions and held until "
        "a positive overshoot captures this reversion and, in assets with positive drift, the "
        "drift as well, while spending roughly half the time out of the market."
    ),
    definition=(
        "For each bar t take the trailing window x_{t-L+1..t} of log prices (L = 60), "
        "centre it, s_i = x_i - mean(x). Embed with M = L/2: trajectory (Hankel) matrix "
        "X in R^{K x M}, X_{k,j} = s_{k+j}, K = L - M + 1. Compute the leading eigenpair "
        "(lambda_1, v) of the lag-covariance matrix X^T X and the principal component "
        "y = X v. The rank-1 reconstruction is the Hankelisation (diagonal averaging) of "
        "y v^T: r_i = (sum_{k+j=i} y_k v_j) / #{(k,j): k+j=i}. Residual e = s - r; signal "
        "z_t = e_{L-1} / std(e_0..e_{L-1}). Rule: entry when z_t < -1; exit when z_t > +1 "
        "(position held from entry until exit; harness applies the one-bar delay)."
    ),
    references=(
        "Golyandina, N., Nekrutkin, V., Zhigljavsky, A. (2001). Analysis of Time Series "
        "Structure: SSA and Related Techniques. Chapman & Hall/CRC.",
        "Vautard, R., Yiou, P., Ghil, M. (1992). Singular-spectrum analysis: A toolkit for "
        "short, noisy chaotic signals. Physica D 58, 95-126.",
        "Broomhead, D. S., King, G. P. (1986). Extracting qualitative dynamics from "
        "experimental data. Physica D 20, 217-236.",
        "Hassani, H. (2007). Singular Spectrum Analysis: Methodology and Comparison. Journal "
        "of Data Science 5, 239-257.",
    ),
    signals=(SSA_RESID,),
    rule=_rule,
    rule_lookback=0,
    novelty=(
        "Uses the singular-spectrum (eigen-) decomposition of the lagged price trajectory "
        "matrix, rather than a moving average, to define the adaptive 'fair' path: the trend "
        "is the data-driven leading eigentriple, so its effective frequency response adapts "
        "to each window. Trading is on the standardised high-frequency residual of that "
        "decomposition, with an asymmetric hold (enter at -1 sd, exit only on a +1 sd "
        "overshoot) instead of a symmetric return-to-mean exit."
    ),
    limitations=(
        "Rank-1 SSA endpoint estimates suffer from the usual end effect (the last "
        "reconstructed point uses a single trajectory-matrix element), so the residual at the "
        "last bar is noisy. In persistent bear markets the strategy repeatedly buys dips that "
        "keep falling (several equity segments in the development data); there is no stop. "
        "Results were sensitive to the window length (60 clearly better than 40, 90 or 120 in "
        "development) and to the exit level, and per-instrument results vary a lot between "
        "neighbouring settings, so out-of-sample performance may be noticeably lower. Some FX "
        "pairs without mean reversion at this horizon lose money."
    ),
)
