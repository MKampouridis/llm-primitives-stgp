"""Expected-signature MMD regime filter (signature two-sample test with a witness direction).

The law of short path segments is described by its expected signature. A signature-kernel MMD
compares the law of the last few segments with the law over a trailing reference window; the
statistic is calibrated by ranking it against blocks taken from the reference window. The asset
is held unless the recent law is anomalous *and* the MMD witness points in the adverse
(level-1, drift) direction.
"""
from __future__ import annotations

import numpy as np

from strategy_api import LongWindow, Signal, Strategy, Window


def _sig3(incs):
    """Level 1..3 signature of piecewise-linear paths via Chen's identity.

    incs: list of (N, d) increment arrays, in path order, for N paths at once."""
    N, d = incs[0].shape
    s1 = np.zeros((N, d))
    s2 = np.zeros((N, d, d))
    s3 = np.zeros((N, d, d, d))
    for D in incs:
        DD = D[:, :, None] * D[:, None, :]
        DDD = DD[:, :, :, None] * D[:, None, None, :]
        s3 = (
            s3
            + s2[:, :, :, None] * D[:, None, None, :]
            + s1[:, :, None, None] * DD[:, None, :, :] / 2.0
            + DDD / 6.0
        )
        s2 = s2 + s1[:, :, None] * D[:, None, :] + DD / 2.0
        s1 = s1 + D
    return np.concatenate([s1.reshape(N, -1), s2.reshape(N, -1), s3.reshape(N, -1)], axis=1)


def _segment_signatures(r, window):
    """Row t: truncated (level 3) signature of the segment r[t-window+1..t] (NaN before),
    embedded as the time-augmented lead-lag path (t, X_lead, X_lag)."""
    T = len(r)
    x = 100.0 * r  # constant rescaling only (per-word standardisation follows)
    z = np.zeros(T)
    dt = np.full(T, 1.0 / window)
    incs = []
    for j in range(window):
        k = window - 1 - j
        xj = np.full(T, np.nan)
        xj[k:] = x[: T - k]
        incs.append(np.stack([z, xj, z], axis=1))  # lead coordinate moves
        incs.append(np.stack([dt, z, xj], axis=1))  # lag coordinate and time move
    S = _sig3(incs)
    keep = np.ones(S.shape[1], dtype=bool)  # drop the deterministic pure-time words
    keep[0] = False  # (t)
    keep[3 + 0] = False  # (t,t)
    keep[3 + 9 + 0] = False  # (t,t,t)
    return S[:, keep]


def _mmd(log_return, window, recent, reference):
    r = np.asarray(log_return, dtype=float)
    T = len(r)
    out = np.full(T, np.nan)
    wit = np.full(T, np.nan)
    if T < recent or reference - 2 * recent + 1 < 5:  # too few reference blocks
        return out, wit
    F = _segment_signatures(r, window)  # (T, 36)
    # block means of `recent` consecutive segment signatures (exact per window)
    B = np.full_like(F, np.nan)
    B[recent - 1 :] = np.lib.stride_tricks.sliding_window_view(F, recent, axis=0).mean(axis=2)
    for t in range(window + reference - 2, T):
        ref = F[t - reference + 1 : t - recent + 1]  # reference segments (disjoint from recent)
        blk = B[t - reference + recent : t - recent + 1]  # null blocks inside the reference
        cur = B[t]  # recent block: the last `recent` segments
        if not (np.all(np.isfinite(ref)) and np.all(np.isfinite(blk)) and np.all(np.isfinite(cur))):
            continue
        mu = ref.mean(axis=0)  # empirical expected signature of the reference law
        sc = ref.std(axis=0)
        sc = np.where(sc > 1e-12, sc, np.inf)
        dcur = np.mean(((cur - mu) / sc) ** 2)  # squared MMD, standardised linear sig. kernel
        dnull = np.mean(((blk - mu) / sc) ** 2, axis=1)
        out[t] = float(np.mean(dnull < dcur))  # calibrated rank in [0, 1]
        wit[t] = float((cur[0] - mu[0]) / sc[0])  # witness along the level-1 (lead) word
    return out, wit


def signature_mmd_rank(log_return, *, window=10, recent=10, reference=90):
    """Rank of the recent-vs-reference expected-signature MMD among in-reference blocks."""
    return _mmd(log_return, window, recent, reference)[0]


def signature_witness_drift(log_return, *, window=10, recent=10, reference=90):
    """Standardised level-1 component of the MMD witness (mean embedding difference)."""
    return _mmd(log_return, window, recent, reference)[1]


def _rule(s):
    q = s["signature_mmd_rank"]
    g = s["signature_witness_drift"]
    ok = np.isfinite(q) & np.isfinite(g)
    entry = np.where(ok, ((q < 0.7) | (g > 0)).astype(float), np.nan)
    exit_ = np.where(ok, ((q > 0.8) & (g < 0)).astype(float), np.nan)
    return entry, exit_


_PARAMS = {"window": Window(10), "recent": Window(10), "reference": LongWindow(90)}

SIG = Signal(
    name="signature_mmd_rank",
    fn=signature_mmd_rank,
    inputs=("log_return",),
    params=dict(_PARAMS),
    lookback=lambda window, recent, reference: reference + window - 1,
    description="Calibrated rank of the expected-signature MMD between the last `recent` "
    "lead-lag segment signatures and the trailing reference law.",
)

SIG2 = Signal(
    name="signature_witness_drift",
    fn=signature_witness_drift,
    inputs=("log_return",),
    params=dict(_PARAMS),
    lookback=lambda window, recent, reference: reference + window - 1,
    description="Level-1 (lead word) component of the standardised MMD witness: sign of the "
    "anomaly's drift direction.",
)

STRATEGY = Strategy(
    name="signature_mmd_regime_filter",
    domain="rough_paths",
    hypothesis=(
        "The expected signature of short path segments characterises the law of the price "
        "process at that scale (increments, quadratic variation, ordering of moves, higher "
        "iterated integrals). A maximum mean discrepancy built on the signature feature map "
        "is therefore a model-free two-sample test for 'has the law of recent paths moved away "
        "from the law of the trailing reference?'. Most of the time markets are in a "
        "locally stationary regime and the long-only holder earns the asset's drift. When the "
        "recent path law is anomalous AND the MMD witness points in the adverse direction "
        "(the recent mean level-1 signature is below the reference: a sell-off-type change of "
        "law, typically with altered quadratic variation and ordering), the subsequent "
        "returns are poor and drawdowns deep, so stepping aside until the law returns to "
        "normal, or the witness turns favourable, should improve Sharpe and drawdown per unit "
        "volatility versus staying long through regime breaks, in any liquid market."
    ),
    definition=(
        "Returns r_t. For each bar s, the segment of the last w=10 returns is embedded as the "
        "time-augmented lead-lag path Z = (t, X^lead, X^lag) in R^3 (2w linear pieces: lead step "
        "(0, r, 0), then lag+time step (1/w, 0, r)). S(Z)_s is its signature truncated at level 3, "
        "computed exactly by Chen's identity: S1+=D, S2+=S1(x)D + D(x)D/2, "
        "S3+=S2(x)D + S1(x)D(x)D/2 + D(x)D(x)D/6; the three pure-time words are dropped, "
        "leaving k=36 words (level 2 contains the Levy areas and the quadratic variation "
        "[X] via the lead-lag area). Reference set at bar t: R_t = {S_s : t-L+1 <= s <= t-m}, "
        "L=90, m=10; mu_t = mean(R_t) (empirical expected signature), sigma_t = std(R_t) per word. "
        "Recent block C_t = mean{S_s : t-m+1 <= s <= t}. Squared MMD with the standardised "
        "linear signature kernel k(a,b)=<a/sigma, b/sigma>: D(C) = (1/k) sum_i ((C_i - mu_i)/sigma_i)^2. "
        "Calibration: q_t = fraction of in-reference blocks B_u = mean{S_s: u-m+1<=s<=u}, "
        "u in [t-L+m, t-m], with D(B_u) < D(C_t) (rank of the current discrepancy against the "
        "reference's own block-to-mean variability). Witness direction: "
        "g_t = (C_t - mu_t)_lead / sigma_t,lead, the level-1 component of the MMD witness "
        "function (mean-embedding difference). Rule: exit when q_t > 0.8 and g_t < 0 "
        "(adverse anomaly); enter when q_t < 0.7 (law back to normal) or g_t > 0 (witness "
        "favourable). Lookback L+w-1 = 99 bars."
    ),
    references=(
        "Lyons, T. (1998). Differential equations driven by rough signals. Revista Matematica "
        "Iberoamericana 14(2), 215-310.",
        "Chevyrev, I. & Oberhauser, H. (2022). Signature moments to characterize laws of "
        "stochastic processes. Journal of Machine Learning Research 23(176), 1-42.",
        "Kiraly, F. J. & Oberhauser, H. (2019). Kernels for sequentially ordered data. Journal "
        "of Machine Learning Research 20(31), 1-45.",
        "Gretton, A., Borgwardt, K. M., Rasch, M. J., Schoelkopf, B. & Smola, A. (2012). A kernel "
        "two-sample test. Journal of Machine Learning Research 13, 723-773.",
        "Horvath, B., Issa, Z. & Muguruza, A. (2024). Non-parametric online market regime "
        "detection and regime clustering for multidimensional and path-dependent data "
        "structures. arXiv:2306.15835.",
        "Chevyrev, I. & Kormilitzin, A. (2016). A primer on the signature method in machine "
        "learning. arXiv:1603.03788.",
        "Flint, G., Hambly, B. & Lyons, T. (2016). Discretely sampled signals and the rough Hoff "
        "process. Stochastic Processes and their Applications 126(9), 2593-2614 (lead-lag "
        "transform).",
    ),
    signals=(SIG, SIG2),
    rule=_rule,
    rule_lookback=0,
    novelty=(
        "Unlike the earlier strategies, which threshold a single level-2 signature term "
        "(Levy area of (X,[X]) or of (t,X)) or a p-variation imbalance, this strategy uses the "
        "whole truncated signature as a characterisation of the law of path segments and "
        "performs an online, self-calibrated signature-MMD two-sample test between recent and "
        "reference path distributions (distributional regime detection), with the exit "
        "direction taken from the MMD witness function rather than from any single "
        "hand-picked iterated integral."
    ),
    limitations=(
        "Truncation at level 3 and a standardised linear kernel only approximate a "
        "characteristic signature kernel; the calibration uses overlapping in-reference blocks, "
        "so the rank is not an exact p-value and the recent (out-of-reference) block tends to "
        "rank high, which lowers exposure (about 70-80% in testing). Short reference windows "
        "(90 bars) make the reference law noisy, and the filter cannot tell a V-shaped "
        "rebound from a regime break until the witness turns positive. On assets with no drift "
        "(currencies) it mostly cuts exposure rather than adding return. On development data "
        "the objective was very sensitive to parameters (neighbouring settings of the "
        "reference length and thresholds ranged from about -0.05 to +0.08), and it was only "
        "marginally above a near-buy-and-hold baseline (+0.015), so out-of-sample performance "
        "should be expected to be close to buy-and-hold with somewhat lower exposure. Trade "
        "frequency on calm FX series is about 3 entries per year, not far above the minimum "
        "of 2."
    ),
)
