"""ordinal_efficiency_regime: hold the asset while its return process is ordinally random.

Information-theoretic idea: the Bandt-Pompe permutation entropy of daily returns measures how
close the rank-order dynamics of the market are to an i.i.d. (informationally efficient) process.
The long position is held in high-entropy (diffusive, efficient) regimes and abandoned when ordinal
structure emerges (entropy falls into the low tail of its own one-year distribution).
"""
from __future__ import annotations

import math

import numpy as np

from strategy_api import Order, Signal, Strategy, Window, rolling_quantile

# --- signal -----------------------------------------------------------------------------------


def _ordinal_codes(x: np.ndarray, m: int) -> np.ndarray:
    """Integer code of the ordinal pattern of (x[t-m+1], ..., x[t]) at index t; -1 if unavailable.

    The code is the base-m encoding of the rank vector, which is a bijection on the m! permutations.
    """
    n = len(x)
    codes = np.full(n, -1, dtype=np.int64)
    if n < m:
        return codes
    w = np.lib.stride_tricks.sliding_window_view(x, m)
    ok = np.all(np.isfinite(w), axis=1)
    ranks = np.argsort(np.argsort(w, axis=1, kind="stable"), axis=1, kind="stable")
    c = np.zeros(len(w), dtype=np.int64)
    for j in range(m):
        c = c * m + ranks[:, j]
    c[~ok] = -1
    codes[m - 1 :] = c
    return codes


def perm_entropy(log_return, *, order, window):
    """Normalised permutation entropy H_m(t) in [0, 1] of the last `window` ordinal patterns."""
    x = np.asarray(log_return, dtype=np.float64)
    n = len(x)
    out = np.full(n, np.nan)
    codes = _ordinal_codes(x, order)
    valid = codes >= 0
    base = order**order
    norm = math.log(math.factorial(order))
    vcs = np.concatenate([[0], np.cumsum(valid)])
    for t in range(window - 1, n):
        if vcs[t + 1] - vcs[t + 1 - window] < window:
            continue
        cnt = np.bincount(codes[t + 1 - window : t + 1], minlength=base).astype(float)
        p = cnt[cnt > 0] / window
        out[t] = float(-np.sum(p * np.log(p)) / norm)
    return out


PERM_ENTROPY = Signal(
    name="perm_entropy",
    fn=perm_entropy,
    inputs=("log_return",),
    params={"order": Order(4), "window": Window(40)},
    lookback=lambda order, window: order + window,
    description="Normalised Bandt-Pompe permutation entropy of daily log returns "
    "(embedding dimension `order`, delay 1) over the last `window` patterns.",
)

# --- rule -------------------------------------------------------------------------------------

REF_WINDOW = 252  # one year of the entropy's own history
ENTRY_Q = 0.5  # re-enter when ordinal entropy is above its one-year median
EXIT_Q = 0.2  # step aside when ordinal entropy is in its lowest quintile


def rule(signals):
    h = signals["perm_entropy"]
    hi = rolling_quantile(h, REF_WINDOW, ENTRY_Q)
    lo = rolling_quantile(h, REF_WINDOW, EXIT_Q)
    known = np.isfinite(hi) & np.isfinite(lo) & np.isfinite(h)
    entry = np.where(known, (h > hi).astype(float), np.nan)
    exit_ = np.where(known, (h < lo).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="ordinal_efficiency_regime",
    domain="information_theory",
    hypothesis=(
        "Risk premia are earned with shallow drawdowns while the return process is "
        "informationally efficient, i.e. while the rank-order (ordinal) dynamics of consecutive "
        "returns are close to those of an i.i.d. process and the permutation entropy is high. "
        "When ordinal structure emerges - a few rank patterns of consecutive returns become "
        "over-represented, so the permutation entropy drops into the low tail of its own recent "
        "history - the market is in a structured, less efficient state (herding, forced flows, "
        "crisis dynamics) in which drawdown risk is concentrated. A long position is therefore "
        "held through high-entropy regimes, closed when ordinal entropy collapses, and re-opened "
        "once the entropy has recovered above its one-year median."
    ),
    definition=(
        "Let r_t be the daily log return. For embedding dimension m=4 (delay 1) map each vector "
        "(r_{t-3}, r_{t-2}, r_{t-1}, r_t) to its ordinal pattern pi_t in S_4 (the permutation that "
        "sorts it; ties broken by order of occurrence). Over the last N=40 patterns form the "
        "empirical distribution p_t(pi) = #{s in (t-N, t] : pi_s = pi} / N and the normalised "
        "permutation entropy H_t = -sum_pi p_t(pi) ln p_t(pi) / ln(m!), with H_t in [0,1] and "
        "H_t -> 1 for an i.i.d. continuous process (all m! = 24 patterns equiprobable). Let "
        "Q_t(q) be the q-quantile of {H_s : s in (t-252, t]}. Entry condition at t: "
        "H_t > Q_t(0.5). Exit condition at t: H_t < Q_t(0.2). The harness holds a long position "
        "from an entry to the next exit (flat otherwise) with its own one-bar execution delay. "
        "Total lookback: 44 + 252 bars."
    ),
    references=(
        "Bandt, C. and Pompe, B. (2002). Permutation entropy: a natural complexity measure for "
        "time series. Physical Review Letters 88(17), 174102.",
        "Zunino, L., Zanin, M., Tabak, B. M., Perez, D. G. and Rosso, O. A. (2009). Forbidden "
        "patterns, permutation entropy and stock market inefficiency. Physica A 388(14), "
        "2854-2864.",
        "Zanin, M., Zunino, L., Rosso, O. A. and Papo, D. (2012). Permutation entropy and its "
        "main biomedical and econophysics applications: a review. Entropy 14(8), 1553-1577.",
        "Shannon, C. E. (1948). A mathematical theory of communication. Bell System Technical "
        "Journal 27, 379-423 and 623-656.",
    ),
    signals=(PERM_ENTROPY,),
    rule=rule,
    rule_lookback=REF_WINDOW,
    novelty=(
        "Unlike run_information_reversion (binary entropy of up/down strings, entropy of the "
        "distribution of squared-return energy across days, and a zero-drift information test), "
        "this strategy rests on the Bandt-Pompe ordinal symbolisation: it measures the Shannon "
        "entropy of the distribution of rank-order permutations of consecutive returns. This "
        "statistic is invariant to scale and to any monotone transformation of returns, so it is "
        "not a volatility, energy-concentration or drift measure; it captures the dependence "
        "structure (efficiency) of the return process. It is used as a regime filter relative "
        "to its own one-year distribution, with no reversal entries and no drift test."
    ),
    limitations=(
        "The edge found in development is small and noisy: the objective was 0.156, against about "
        "-0.04 for a near buy-and-hold reference, and was sensitive to the entropy window (a "
        "60-bar window scored about -0.19, partly because of too few trades). Because thresholds "
        "are relative quantiles, the strategy is always out about 35-45% of the time even in "
        "markets that never become structured, which costs drift in strong bull markets. As a "
        "long-only rule it cannot profit in assets without a risk premium (most currency pairs "
        "scored about -0.2 to -0.35, largely from drawdowns while invested). Equity indices with "
        "persistent declines are not protected, because ordinal entropy is direction-blind. With "
        "40 bars and 24 patterns, the entropy estimate is biased downwards and noisy; only the "
        "relative quantile makes it usable. Trade frequency is about 3-4 entries a year, close "
        "to the 2-per-year minimum on short or quiet series."
    ),
)
