"""simplex_fisher_rao_stationarity: long while the return law is quasi-stationary on the
multinomial (rank-histogram) statistical manifold, flat while it is travelling fast."""

from __future__ import annotations

import numpy as np
from scipy.stats import chi2

from strategy_api import Levels, Signal, Strategy, Window, trailing_windows


def fr_speed(log_return, *, window=Window(30), levels=Levels(4)):
    """Fisher-Rao speed of the return law between two adjacent windows.

    Over the last 2w returns, pooled ranks define `levels` equiprobable categories. pa, pb are
    the categorical (multinomial) laws of the older and the newer w returns. Their Fisher-Rao
    distance on the probability simplex is d = 2 arccos(sum_k sqrt(pa_k pb_k)). Under a
    stationary law (w/2) d^2 ~ chi2(levels-1); the signal is that chi2 CDF (0..1), so it is
    scale-free and identical in meaning for every asset.
    """
    w = window
    rows = trailing_windows(log_return, 2 * w)
    out = np.full(len(log_return), np.nan)
    ok = np.all(np.isfinite(rows), axis=1)
    if not ok.any():
        return out
    r = rows[ok]
    ranks = np.argsort(np.argsort(r, axis=1, kind="stable"), axis=1, kind="stable")
    bins = (ranks * levels) // (2 * w)
    a = bins[:, :w]
    b = bins[:, w:]
    pa = np.stack([(a == k).mean(axis=1) for k in range(levels)], axis=1)
    pb = np.stack([(b == k).mean(axis=1) for k in range(levels)], axis=1)
    bc = np.clip(np.sum(np.sqrt(pa * pb), axis=1), 0.0, 1.0)
    d = 2.0 * np.arccos(bc)
    stat = 0.5 * w * d * d
    out[ok] = chi2.cdf(stat, levels - 1)
    return out


SIG = Signal(
    name="fr_speed",
    fn=fr_speed,
    inputs=("log_return",),
    params={"window": Window(30), "levels": Levels(4)},
    lookback=lambda window, levels: 2 * window,
    description="chi2-calibrated Fisher-Rao distance between rank histograms of two adjacent "
    "windows (multinomial simplex)",
)

ENTRY_P = 0.5  # re-enter once the law looks stationary again (below the null median)
EXIT_P = 0.9  # leave when the law has moved significantly (10% tail of the null)


def rule(s):
    x = s["fr_speed"]
    f = np.isfinite(x)
    entry = np.where(f, (x < ENTRY_P).astype(float), np.nan)
    exit_ = np.where(f, (x > EXIT_P).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="simplex_fisher_rao_stationarity",
    domain="information_geometry",
    hypothesis=(
        "Risk premia are earned smoothly while the return-generating law is quasi-stationary; "
        "losses and drawdowns concentrate when the law itself is moving (regime transition, "
        "liquidity or volatility break). The speed at which the empirical law travels across "
        "the statistical manifold, measured by the Fisher-Rao distance between the laws of two "
        "adjacent windows, is a model-free, scale-free gauge of that motion. Holding the asset "
        "only while the law is statistically stationary, and stepping aside when it moves "
        "significantly, keeps most of the premium while trimming exposure to transition "
        "periods; the chi-square calibration makes the thresholds identical across assets."
    ),
    definition=(
        "Let r_{t-2w+1..t} be the last 2w log returns (w=30). Rank them jointly and map rank "
        "rho in {0..2w-1} to category k = floor(rho*L/(2w)), L=4 equiprobable categories. Let "
        "pa (older w returns) and pb (newer w returns) be the category frequencies, points of "
        "the probability simplex Delta_{L-1} with Fisher metric ds^2 = sum_k dp_k^2/p_k. The "
        "map p -> 2 sqrt(p) is an isometry onto a sphere of radius 2, so the Fisher-Rao "
        "geodesic distance is d = 2 arccos( sum_k sqrt(pa_k pb_k) ) (twice the Bhattacharyya "
        "angle). For two independent samples of size w from the same law, (w/2) d^2 -> "
        "chi2_{L-1} (local equivalence of FR distance and Pearson chi2). Signal "
        "v_t = F_{chi2(L-1)}((w/2) d_t^2) in [0,1]. Rule: enter long when v_t < 0.5 (law "
        "consistent with stationarity), exit when v_t > 0.9 (significant motion on the "
        "manifold); otherwise keep the current state (hysteresis)."
    ),
    references=(
        "Amari, S. (2016). Information Geometry and Its Applications. Springer, Applied "
        "Mathematical Sciences 194.",
        "Amari, S., Nagaoka, H. (2000). Methods of Information Geometry. AMS / Oxford "
        "University Press, Translations of Mathematical Monographs 191.",
        "Rao, C. R. (1945). Information and the accuracy attainable in the estimation of "
        "statistical parameters. Bulletin of the Calcutta Mathematical Society 37, 81-91.",
        "Bhattacharyya, A. (1943). On a measure of divergence between two statistical "
        "populations defined by their probability distributions. Bulletin of the Calcutta "
        "Mathematical Society 35, 99-109.",
        "Kass, R. E., Vos, P. W. (1997). Geometrical Foundations of Asymptotic Inference. "
        "Wiley.",
    ),
    signals=(SIG,),
    rule=rule,
    rule_lookback=0,
    novelty=(
        "Earlier strategies measure excursions of a short-horizon Gaussian model from a "
        "long-run anchor on the hyperbolic (mu, sigma) half-plane and trade reversal/relaxation "
        "of that excursion. This strategy uses a different manifold and a different quantity: "
        "the nonparametric multinomial simplex of rank histograms (spherical Fisher geometry, "
        "no Gaussian assumption, invariant to any monotone transform of returns), and the "
        "local speed of the law between two adjacent windows (a two-sample Fisher-Rao test), "
        "not a distance to a long-run anchor. It is a stationarity filter, not a reversal bet: "
        "it is long by default and flat when the law is moving in any direction."
    ),
    limitations=(
        "The edge is modest and the development objective was noisy across nearby parameter "
        "choices (window 20/30/40, 3 vs 4 categories), so much of the measured performance may "
        "be sampling luck. The filter is direction-blind: it also steps aside during rebounds "
        "and calm rallies that change the law, and stays long through slow, stationary "
        "declines. With only 30 returns per half and 4 categories the test has low power, so "
        "many exits are false alarms that cost turnover. Long-only exposure in assets with no "
        "drift (e.g. many currency pairs) earns little, and the drawdown penalty dominates "
        "there."
    ),
)
