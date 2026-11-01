"""gain_loss_transport_asymmetry: long-only timing by the signed optimal-transport asymmetry
between the law of recent gains and the law of recent loss magnitudes."""
import numpy as np
from strategy_api import Signal, Strategy, Window, trailing_windows

# quantile levels at which the monotone (optimal) transport map is evaluated
U = (np.arange(10) + 0.5) / 10.0
MIN_SIDE = 5  # minimum number of gains and of losses needed in the window


def _gain_loss_asymmetry(log_return, *, window):
    """A_t = int (Q_G - Q_L) du / int |Q_G - Q_L| du over the trailing window."""
    x = np.asarray(log_return, dtype=np.float64)
    n = len(x)
    out = np.full(n, np.nan)
    rows = trailing_windows(x, window)
    for t in range(window - 1, n):
        r = rows[t]
        if not np.all(np.isfinite(r)):
            continue
        gains = r[r > 0]
        losses = -r[r < 0]
        if len(gains) < MIN_SIDE or len(losses) < MIN_SIDE:
            continue
        disp = np.quantile(gains, U) - np.quantile(losses, U)  # Monge displacement
        cost = np.abs(disp).mean()  # W1(mu_G, mu_L)
        out[t] = disp.mean() / cost if cost > 0 else 0.0
    return out


gain_loss = Signal(
    name="gain_loss_asymmetry",
    fn=_gain_loss_asymmetry,
    inputs=("log_return",),
    params={"window": Window(30)},
    lookback=lambda window: window,
    description="Signed W1 transport asymmetry between the gain law and the loss-magnitude law",
)

ENTRY_LEVEL = -0.3
EXIT_LEVEL = 0.3


def rule(s):
    a = s["gain_loss_asymmetry"]
    ok = np.isfinite(a)
    entry = np.where(ok, (a < ENTRY_LEVEL).astype(float), np.nan)
    exit_ = np.where(ok, (a > EXIT_LEVEL).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="gain_loss_transport_asymmetry",
    domain="optimal_transport",
    hypothesis=(
        "Within a recent window, split daily returns into the law of gains and the law of loss "
        "magnitudes and optimally transport one onto the other. When the transport moves mass "
        "predominantly downward (losses are larger than gains at every matched quantile level, "
        "independently of how often each occurs), the market carries a negative-asymmetry, "
        "crash-risk profile. Investors dislike such negative skewness and require compensation "
        "for bearing it (skewness preference), and these episodes often follow forced selling, "
        "so holding the asset while the loss law dominates the gain law earns a premium. When "
        "the transport moves mass predominantly upward (gains larger than losses: lottery-like, "
        "short-covering or bubble-like behaviour), expected returns are lower and the strategy "
        "is flat. Because the measure compares the two halves of the same window with each other, "
        "and is normalised by the transport cost, it does not depend on the drift relative to an "
        "earlier period, on the volatility level, or on the frequency of up versus down days."
    ),
    definition=(
        "Let r_{t-W+1..t} be the last W=30 daily log returns. Gain law mu_G = empirical law of "
        "{r_i : r_i > 0}; loss law mu_L = empirical law of {-r_i : r_i < 0} (both on R_+, "
        "at least 5 points each, else NaN). In one dimension the optimal transport map from mu_G "
        "to mu_L for any convex cost is the monotone rearrangement T = Q_L o F_G, so the "
        "displacement at quantile level u is delta(u) = Q_G(u) - Q_L(u), evaluated at "
        "u_k = (k - 0.5)/10, k = 1..10 (linear-interpolation empirical quantiles). "
        "W1(mu_G, mu_L) = int_0^1 |delta(u)| du ~ mean_k |delta(u_k)|. The signed transport "
        "asymmetry is A_t = int delta(u) du / int |delta(u)| du in [-1, 1]: the net share of the "
        "transport cost that moves mass up (A=1: gain law first-order stochastically dominates "
        "the loss law; A=-1: loss law dominates). Rule: entry when A_t < -0.3, exit when "
        "A_t > 0.3 (hysteresis band; the harness holds the long position in between)."
    ),
    references=(
        "Villani, C. (2009). Optimal Transport: Old and New. Grundlehren der mathematischen "
        "Wissenschaften 338, Springer.",
        "Peyre, G. and Cuturi, M. (2019). Computational Optimal Transport. Foundations and "
        "Trends in Machine Learning 11(5-6), 355-607.",
        "Rachev, S. T. and Rueschendorf, L. (1998). Mass Transportation Problems, Vol. I. "
        "Springer.",
        "Kraus, A. and Litzenberger, R. H. (1976). Skewness preference and the valuation of risky "
        "assets. Journal of Finance 31(4), 1085-1100.",
        "Harvey, C. R. and Siddique, A. (2000). Conditional skewness in asset pricing tests. "
        "Journal of Finance 55(3), 1263-1295.",
        "Amaya, D., Christoffersen, P., Jacobs, K. and Vasquez, A. (2015). Does realized skewness "
        "predict the cross-section of equity returns? Journal of Financial Economics 118(1), "
        "135-167.",
    ),
    signals=(gain_loss,),
    rule=rule,
    rule_lookback=0,
    novelty=(
        "The earlier strategies transport a recent return distribution onto an earlier one "
        "(across time): loss-half displacement for reversal, and centred shape cost for regime "
        "stability. This strategy transports within a single window, between the conditional law "
        "of gains and the reflected conditional law of losses, which is an OT test of reflection "
        "symmetry rather than of temporal change. The statistic is the net direction of the "
        "monotone transport plan normalised by its W1 cost (a quantile-wise stochastic-dominance "
        "share), not a moment-based skewness: it is invariant to scale, ignores the up/down "
        "frequency and so is neither a momentum nor a mean-return signal. On the development data "
        "the opposite sign (long when gains dominate) scored clearly worse (median F -0.06 vs "
        "0.46, mean F -0.19 vs 0.14)."
    ),
    limitations=(
        "Only 30 returns are split into about 15 gains and 15 losses, so the quantile estimates "
        "are noisy and the signal flips fairly often (about 3-6 entries per year, turnover about "
        "8-13 per year). The development objective is sensitive to window and thresholds (window "
        "20/40 or thresholds +/-0.2/0.4 gave 0.08-0.31 instead of 0.46), so the true edge is "
        "likely smaller than the best figure. Results were weakest on several currency pairs, "
        "whose return laws are close to symmetric, and on a few equity indices during prolonged "
        "declines, when negative asymmetry persists as prices fall. A long-only rule cannot "
        "profit from the flat (positive-asymmetry) state."
    ),
)
