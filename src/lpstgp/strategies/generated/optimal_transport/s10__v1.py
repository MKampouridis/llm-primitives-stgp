"""Wasserstein shape-stability regime filter (optimal transport).

Long while the *shape* of the recent return distribution (location removed) can be transported
cheaply onto the shape of the preceding reference distribution; flat while the distribution is
being reshaped (scale, tails, asymmetry), measured by the centred 2-Wasserstein distance.
"""

import numpy as np

from strategy_api import LongWindow, Signal, Strategy, Window, rolling_quantile, trailing_windows

# quantile grid for the 1-D monotone (optimal) transport plan
_M = 40
_U = (np.arange(_M) + 0.5) / _M

# rule constants (thresholds are relative to the signal's own recent history)
_CAL = 120  # bars of signal history used to calibrate thresholds
_Q_ENTRY = 0.6  # enter when the transport cost is below its 60% rolling quantile
_Q_EXIT = 0.85  # exit when it is above its 85% rolling quantile


def _quantile_functions(rows: np.ndarray) -> np.ndarray:
    """Empirical quantile function of each row evaluated on the grid _U (NaN rows stay NaN)."""
    out = np.full((rows.shape[0], _M), np.nan)
    ok = np.all(np.isfinite(rows), axis=1)
    if ok.any():
        out[ok] = np.quantile(rows[ok], _U, axis=1).T
    return out


def shape_w2(log_return, *, short, ref):
    """Centred 2-Wasserstein distance between the last `short` returns and the `ref` returns that
    immediately precede them, in units of the reference dispersion.

    In one dimension the optimal plan is monotone (quantile coupling), so
    W2^2(mu, nu) = int_0^1 (F_mu^{-1}(u) - F_nu^{-1}(u))^2 du. Both quantile functions are
    centred (their means removed), which removes the location/drift part of the transport and
    keeps only the cost of reshaping the distribution (scale, tails, skew)."""
    x = np.asarray(log_return, dtype=np.float64)
    n = len(x)
    recent = trailing_windows(x, short)
    reference = np.full((n, ref), np.nan)
    rows_ref = trailing_windows(x, ref)
    if n > short:
        reference[short:] = rows_ref[:-short]  # window ending `short` bars before t
    qs = _quantile_functions(recent)
    qr = _quantile_functions(reference)
    qs = qs - qs.mean(axis=1, keepdims=True)
    qr = qr - qr.mean(axis=1, keepdims=True)
    scale = np.sqrt(np.mean(qr**2, axis=1))
    w2 = np.sqrt(np.mean((qs - qr) ** 2, axis=1))
    return w2 / np.where(scale > 0, scale, np.nan)


SHAPE_W2 = Signal(
    name="shape_w2",
    fn=shape_w2,
    inputs=("log_return",),
    params={"short": Window(30), "ref": LongWindow(90)},
    lookback=lambda short, ref: short + ref,
    description="centred W2 transport cost (recent vs preceding return distribution) / ref scale",
)


def rule(signals):
    d = signals["shape_w2"]
    lo = rolling_quantile(d, _CAL, _Q_ENTRY)
    hi = rolling_quantile(d, _CAL, _Q_EXIT)
    entry = np.where(np.isfinite(lo) & np.isfinite(d), (d < lo).astype(float), np.nan)
    exit_ = np.where(np.isfinite(hi) & np.isfinite(d), (d > hi).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="wasserstein_shape_stability",
    domain="optimal_transport",
    hypothesis=(
        "Long-only risk premia (equity, commodity, currency carry) are earned mainly while the "
        "return-generating distribution is stable, and drawdowns cluster in transitions in which "
        "the distribution's shape is being reshaped: volatility expanding or collapsing, tails "
        "fattening, asymmetry flipping. Such changes are shared across asset classes and "
        "are measured directly by the cost of optimally transporting the shape of the recent "
        "return distribution onto the shape of the preceding one. When this centred transport "
        "cost is low relative to its own recent history the market is in a stable regime and the "
        "strategy is long; when it becomes unusually high the regime is in transition and the "
        "strategy steps aside until the cost falls back. Removing the location part of the "
        "transport makes the signal independent of recent drift, so it is neither a momentum nor "
        "a reversal rule: it times exposure by distributional stability alone."
    ),
    definition=(
        "Let r_t be daily log returns. Recent measure mu_t = empirical law of "
        "{r_{t-s+1},...,r_t} (s = short = 30); reference measure nu_t = empirical law of "
        "{r_{t-s-R+1},...,r_{t-s}} (R = ref = 90), the window immediately preceding it. "
        "In 1-D the optimal transport plan for a convex cost is the monotone (quantile) coupling, "
        "so W2^2(mu,nu) = int_0^1 (F_mu^{-1}(u) - F_nu^{-1}(u))^2 du. With empirical quantile "
        "functions on the grid u_k = (k-1/2)/40, k=1..40, centred as "
        "Q~(u_k) = Q(u_k) - mean_j Q(u_j), the signal is the scale-free centred transport cost "
        "D_t = sqrt(mean_k (Q~_mu(u_k) - Q~_nu(u_k))^2) / sqrt(mean_k Q~_nu(u_k)^2). "
        "Since W2^2 = (m_mu - m_nu)^2 + W2^2(centred), D_t is the location-free part of the "
        "transport (scale change plus change of shape/tails). Rule: with L_t and H_t the 60% and "
        "85% quantiles of {D_{t-119},...,D_t}, entry when D_t < L_t, exit when D_t > H_t "
        "(hysteresis band; position held between). Lookback 120 + 120 = 240 bars."
    ),
    references=(
        "Villani, C. (2009). Optimal Transport: Old and New. Grundlehren der mathematischen "
        "Wissenschaften 338, Springer.",
        "Peyre, G. and Cuturi, M. (2019). Computational Optimal Transport. Foundations and Trends "
        "in Machine Learning 11(5-6), 355-607.",
        "Bobkov, S. and Ledoux, M. (2019). One-dimensional empirical measures, order statistics, "
        "and Kantorovich transport distances. Memoirs of the American Mathematical Society "
        "261(1259).",
        "del Barrio, E., Gine, E. and Matran, C. (1999). Central limit theorems for the "
        "Wasserstein distance between the empirical and the true distributions. Annals of "
        "Probability 27(2), 1009-1071.",
        "Horvath, B., Issa, Z. and Muguruza, A. (2021). Clustering market regimes using the "
        "Wasserstein distance. arXiv:2110.11848.",
        "Kritzman, M. and Li, Y. (2010). Skulls, financial turbulence, and risk management. "
        "Financial Analysts Journal 66(5), 30-41.",
        "Moreira, A. and Muir, T. (2017). Volatility-managed portfolios. Journal of Finance "
        "72(4), 1611-1644.",
    ),
    signals=(SHAPE_W2,),
    rule=rule,
    rule_lookback=_CAL,
    novelty=(
        "Earlier strategy lower_tail_transport_reversal uses the signed displacement of the loss "
        "half of the transport plan as a contrarian entry trigger after downside shocks. This "
        "strategy uses a different object and a different direction: the unsigned, centred "
        "(location-removed) 2-Wasserstein cost over the whole distribution, used as a "
        "regime-stability filter that keeps the strategy long while the distribution is stable "
        "and takes it flat during reshaping. It therefore holds through calm drifts and steps "
        "aside after shocks, the opposite of a post-shock reversal entry. Controls on the "
        "development data with the same rule: the scale-only part of the transport "
        "(|sigma_recent - sigma_ref|/sigma_ref, a vol-ratio filter) scored 0.13 vs 0.25 for the "
        "full centred W2 (60/80 band); the non-centred W2 (location included) and a signed "
        "'outward displacement' version scored negative, and W1 instead of W2 was also worse, "
        "so the tail-sensitive shape part of the quadratic transport cost is what carries the "
        "signal."
    ),
    limitations=(
        "The edge is modest and parameter-sensitive on the development data: the 90-bar reference "
        "window worked clearly better than 60 or 120 bars, and a 40-bar recent window was weaker "
        "than 30. The objective moves by roughly +/-0.15 between neighbouring settings, so the "
        "development score likely overstates out-of-sample performance. The strategy is long "
        "about 55-80% of the time, so it inherits most of the asset's drift; it adds little on "
        "driftless currency pairs and cannot avoid slow, low-volatility bear markets because "
        "it only reacts to shape changes, not to direction. The 240-bar warm-up leaves the first "
        "year flat. Entries are only about 2-4 per year, so slow-moving instruments may fall "
        "near the minimum-trade requirement. With 30 observations the empirical extreme "
        "quantiles are noisy, so a single outlier day can trigger an exit."
    ),
)
