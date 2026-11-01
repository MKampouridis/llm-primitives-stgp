"""Lower-tail quantile-transport reversal.

A long-only daily rule built on one-dimensional optimal transport: the empirical quantile
function of the last 10 daily returns is compared with that of a disjoint, preceding reference
window. In 1-D the optimal (monotone) transport map between the two measures is the quantile
rearrangement, so the displacement Q_ref(u) - Q_recent(u) at each mass level u is exactly how
far the optimal plan moves that piece of mass. The signal is the average leftward displacement
of the loss half of the distribution (u < 1/2), scaled by the reference mean absolute return.
The rule buys after an unusually large leftward transport of the loss side and holds until the
displacement falls back to its typical level.
"""

import numpy as np

from strategy_api import LongWindow, Quantile, Signal, Strategy, Window, trailing_windows

# quantile levels at which the empirical quantile functions are evaluated (midpoint rule)
_U = (np.arange(40) + 0.5) / 40.0
# window of the rolling quantiles used by the rule
_RULE_WINDOW = 126
_ENTRY_Q = 0.6
_EXIT_Q = 0.5


def _quantile_functions(x: np.ndarray, n: int) -> np.ndarray:
    """Row t = empirical quantile function of x[t-n+1 .. t] at the levels _U (NaN if incomplete)."""
    rows = trailing_windows(x, n)
    out = np.full((len(x), len(_U)), np.nan)
    ok = np.all(np.isfinite(rows), axis=1)
    if ok.any():
        out[ok] = np.quantile(rows[ok], _U, axis=1).T
    return out


def lower_tail_transport(log_return, *, window, ref, tail):
    """X_t = (mean over u<tail of [Q_ref(u) - Q_recent(u)]) / mean_u |Q_ref(u)|.

    Q_recent: quantile function of r[t-window+1 .. t];
    Q_ref:    quantile function of r[t-window-ref+1 .. t-window] (disjoint, immediately before).
    Positive values mean the optimal transport plan moves the loss half of the reference
    distribution to the left (recent losses are larger than usual at matched mass levels).
    """
    n = int(window)
    q_recent = _quantile_functions(log_return, n)
    q_ref_end = _quantile_functions(log_return, int(ref))
    q_ref = np.full_like(q_ref_end, np.nan)
    if len(q_ref) > n:
        q_ref[n:] = q_ref_end[:-n]
    low = _U < tail
    displacement = q_ref[:, low] - q_recent[:, low]
    scale = np.mean(np.abs(q_ref), axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.mean(displacement, axis=1) / np.where(scale > 0, scale, np.nan)
    return out


def rule(signals):
    x = signals["lower_tail_transport"]
    rows = trailing_windows(x, _RULE_WINDOW)
    ok = np.all(np.isfinite(rows), axis=1)
    q_hi = np.full(len(x), np.nan)
    q_lo = np.full(len(x), np.nan)
    if ok.any():
        q_hi[ok] = np.quantile(rows[ok], _ENTRY_Q, axis=1)
        q_lo[ok] = np.quantile(rows[ok], _EXIT_Q, axis=1)
    valid = np.isfinite(q_hi) & np.isfinite(x)
    entry = np.where(valid, ((x > q_hi) & (x > 0.0)).astype(float), np.nan)
    exit_ = np.where(valid, (x < q_lo).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="lower_tail_transport_reversal",
    domain="optimal_transport",
    hypothesis=(
        "When the optimal transport plan from an instrument's recent reference return "
        "distribution to its last two weeks of returns moves the loss half of the mass "
        "unusually far to the left, the market has just gone through a downside distributional "
        "shock (larger and/or more frequent losses at matched quantile levels). Such shocks are "
        "partly overreaction and forced selling, so subsequent returns tend to mean-revert: "
        "liquidity providers who buy after the shock earn a premium until the loss-side "
        "displacement has dissipated. Restricting the transport to the loss half separates "
        "downside stress from symmetric volatility changes and from upside moves. On the "
        "development data, the same rule using the displacement of the whole distribution "
        "(which reduces to a plain short-term mean-reversal signal) scored far lower."
    ),
    definition=(
        "Let r_t be daily log returns, n = window = 10, m = ref = 180, tau = tail = 0.5. "
        "Recent measure S_t = empirical law of {r_{t-n+1},...,r_t}; reference measure "
        "R_t = empirical law of {r_{t-n-m+1},...,r_{t-n}} (disjoint, immediately preceding). "
        "With quantile functions Q_S, Q_R, the 1-D optimal transport map is T = Q_S o F_R and "
        "W_1(S,R) = int_0^1 |Q_S(u) - Q_R(u)| du. Define the signed partial (loss-half) "
        "transport displacement D_t = (1/tau) int_0^tau (Q_R(u) - Q_S(u)) du and the scale "
        "s_t = int_0^1 |Q_R(u)| du (reference mean absolute return); the signal is "
        "X_t = D_t / s_t. Integrals use the midpoint rule on u_k = (k - 1/2)/40, k = 1..40, "
        "with linearly interpolated empirical quantiles. Rule: let q_p(t) be the p-quantile of "
        "{X_{t-125},...,X_t}. Entry when X_t > q_0.6(t) and X_t > 0 (the loss half has "
        "actually been transported left); exit when X_t < q_0.5(t). Long or flat. Lookback "
        "= n + m + 126 = 316 bars."
    ),
    references=(
        "Villani, C. (2009). Optimal Transport: Old and New. Grundlehren der mathematischen "
        "Wissenschaften 338, Springer.",
        "Peyre, G. and Cuturi, M. (2019). Computational Optimal Transport. Foundations and "
        "Trends in Machine Learning 11(5-6), 355-607.",
        "Panaretos, V. M. and Zemel, Y. (2019). Statistical aspects of Wasserstein distances. "
        "Annual Review of Statistics and Its Application 6, 405-431.",
        "Horvath, B., Issa, Z. and Muguruza, A. (2021). Clustering market regimes using the "
        "Wasserstein distance. arXiv:2110.11848.",
        "Leshno, M. and Levy, H. (2002). Preferred by 'all' and preferred by 'most' decision "
        "makers: almost stochastic dominance. Management Science 48(8), 1074-1085.",
        "Lehmann, B. N. (1990). Fads, martingales, and market efficiency. Quarterly Journal of "
        "Economics 105(1), 1-28.",
        "Nagel, S. (2012). Evaporating liquidity. Review of Financial Studies 25(7), 2005-2039.",
    ),
    signals=(
        Signal(
            name="lower_tail_transport",
            fn=lower_tail_transport,
            inputs=("log_return",),
            params={"window": Window(10), "ref": LongWindow(180), "tail": Quantile(0.5)},
            lookback=lambda window, ref, tail: int(window) + int(ref),
            description=(
                "Signed leftward displacement of the loss half of the quantile function "
                "(1-D optimal transport) from a preceding reference window to the last "
                "`window` returns, in units of the reference mean absolute return."
            ),
        ),
    ),
    rule=rule,
    rule_lookback=_RULE_WINDOW,
    novelty=(
        "Uses a partial, signed 1-D optimal-transport displacement, restricted to the loss half "
        "of the mass, between two disjoint empirical return distributions as a contrarian "
        "trigger. Wasserstein methods in finance are usually used to cluster regimes or detect "
        "change points. Here the direction and location of the transport (which part of the "
        "mass moves, and which way) is the signal. It responds to tail expansion and to "
        "downward drift of the loss side, but not to upside moves. It is not a mean or "
        "z-score reversal: on the development data, the whole-distribution version (equal to "
        "a mean-shift reversal) scored much worse. A one-sided W1 / almost-stochastic-dominance "
        "violation variant scored similarly (0.09 vs 0.12 under the earlier rule without the "
        "X > 0 condition). Thresholds come from the signal's own rolling quantiles plus an "
        "absolute zero level, so the rule needs no per-market calibration."
    ),
    limitations=(
        "A contrarian rule: it buys into downside shocks, so persistent sell-offs and bear "
        "markets cause losses and drawdowns (several equity indices were negative on the "
        "development data). Most currency pairs scored negative, and trending assets such as "
        "cryptocurrencies may not mean-revert after shocks. Performance is sensitive to the "
        "recent window: 10 bars worked and 15 or 20 bars were clearly worse. The empirical "
        "quantile function of 10 returns is coarse. Turnover is about 10-20 round trips per "
        "year, so high-cost markets suffer. Thresholds (0.6/0.5 rolling quantiles, the zero "
        "level) and windows were chosen on the development data, so out-of-sample results "
        "should be expected to be weaker. Warm-up is 316 bars."
    ),
)
