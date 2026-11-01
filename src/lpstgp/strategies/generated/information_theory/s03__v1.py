"""context_tree_rank_prediction

Universal sequential prediction (context-tree weighting, CTW) of the rank of the next 10-day
block return, after a maximum-entropy (equiprobable) quantisation of block returns. The strategy
is long while the universal coder's predictive distribution puts the next block above the
middle rank.
"""
from __future__ import annotations

import numpy as np
from scipy.special import gammaln

from strategy_api import LongWindow, Lag, Levels, Order, Signal, Strategy, Window

_LOG_HALF = np.log(0.5)


# --------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------


def _rolling_sum(x: np.ndarray, w: int) -> np.ndarray:
    """Trailing sum over w bars (NaN for the first w-1 bars); exact window, no cumsum."""
    out = np.full(len(x), np.nan)
    if len(x) >= w:
        out[w - 1:] = np.lib.stride_tricks.sliding_window_view(x, w).sum(axis=1)
    return out


def _log_kt(counts: np.ndarray, m: int) -> np.ndarray:
    """log of the Krichevsky-Trofimov (Dirichlet(1/2,...,1/2)) block probability of counts
    (last axis = the m symbols)."""
    return (gammaln(counts + 0.5).sum(axis=-1) - gammaln(counts.sum(axis=-1) + m / 2.0)
            + gammaln(m / 2.0) - m * gammaln(0.5))


def _maxent_symbols(blk: np.ndarray, m: int, qwin: int) -> np.ndarray:
    """Code blk[s] by its cell among the m equiprobable cells of the trailing qwin block
    returns (maximum-entropy quantiser).  -1 where undefined."""
    T = len(blk)
    x = np.full(T, -1, dtype=np.int64)
    qs = np.arange(1, m) / m
    for s in range(qwin - 1, T):
        w = blk[s - qwin + 1: s + 1]
        if np.all(np.isfinite(w)):
            x[s] = int(np.searchsorted(np.quantile(w, qs), blk[s], side="right"))
    return x


# --------------------------------------------------------------------------------------------
# signal
# --------------------------------------------------------------------------------------------


def ctw_rank_forecast(log_return, *, window, depth, horizon, levels, quant_window):
    """Expected (centred) rank of the next h-day block return under the CTW predictive
    distribution, contexts = ranks of the preceding `depth` non-overlapping h-day blocks."""
    r = np.asarray(log_return, dtype=np.float64)
    T = len(r)
    D, h, M = depth, horizon, levels
    out = np.full(T, np.nan)
    need = window + D * h + h + quant_window
    if T < need:
        return out
    finite = np.isfinite(r)
    blk = _rolling_sum(np.where(finite, r, 0.0), h)           # h-day block log return
    x = _maxent_symbols(blk, M, quant_window)
    x = np.where(x >= 0, x, M // 2)
    bad = _rolling_sum((~finite).astype(float), need)          # any NaN inside the lookback
    idx = np.arange(T)

    def shift(a, k):
        o = np.full(T, M // 2, dtype=np.int64)
        if k < T:
            o[k:] = a[: T - k]
        return o

    # context of the symbol at s: (x[s-h], x[s-2h], ..., x[s-dh]); context for the forecast
    # made at t (target block t+1..t+h): (x[t], x[t-h], ...)
    codes = [np.zeros(T, dtype=np.int64)]
    nxt = [np.zeros(T, dtype=np.int64)]
    for d in range(1, D + 1):
        codes.append(codes[-1] + shift(x, d * h) * M ** (d - 1))
        nxt.append(nxt[-1] + shift(x, (d - 1) * h) * M ** (d - 1))

    # symbol counts per context node over the trailing training window
    cnt = []
    for d in range(D + 1):
        arr = np.zeros((T, M ** d, M))
        for c in range(M ** d):
            in_ctx = codes[d] == c
            for a in range(M):
                arr[:, c, a] = np.nan_to_num(
                    _rolling_sum((in_ctx & (x == a)).astype(float), window))
        cnt.append(arr)

    # CTW weighted probabilities: P_w = 1/2 P_KT + 1/2 prod_children P_w (leaves: P_KT)
    lpw = [None] * (D + 1)
    for d in range(D, -1, -1):
        lpe = _log_kt(cnt[d], M)
        if d == D:
            lpw[d] = lpe
        else:
            n = M ** d
            kids = sum(lpw[d + 1][:, j * n:(j + 1) * n] for j in range(M))
            lpw[d] = np.logaddexp(_LOG_HALF + lpe, _LOG_HALF + kids)

    # sequential predictive probability P(next = a) = P_w(seq, a) / P_w(seq): only the nodes on
    # the current context path change when symbol a is appended
    logp = []
    for a in range(M):
        mod = None
        for d in range(D, -1, -1):
            c = nxt[d]
            cc = cnt[d][idx, c, :].copy()
            cc[:, a] += 1.0
            lpe = _log_kt(cc, M)
            if d == D:
                mod = lpe
            else:
                n = M ** d
                digit = (nxt[d + 1] // n) % M
                kids = mod.copy()
                for j in range(M):
                    kids = kids + np.where(digit == j, 0.0, lpw[d + 1][idx, c + j * n])
                mod = np.logaddexp(_LOG_HALF + lpe, _LOG_HALF + kids)
        logp.append(mod)
    logp = np.array(logp)
    logp -= logp.max(axis=0, keepdims=True)
    pr = np.exp(logp)
    pr /= pr.sum(axis=0, keepdims=True)

    centred_rank = (np.arange(M) - (M - 1) / 2.0)[:, None]
    val = (centred_rank * pr).sum(axis=0)
    ok = (idx >= need - 1) & (np.nan_to_num(bad, nan=1.0) == 0) & np.isfinite(val)
    out[ok] = val[ok]
    return out


# --------------------------------------------------------------------------------------------
# rule
# --------------------------------------------------------------------------------------------

AVG = 5  # forecasts averaged over the last 5 days (half of the 10-day bet horizon)


def rule(signals):
    v = np.asarray(signals["ctw_rank_forecast"], dtype=np.float64)
    f = np.full(len(v), np.nan)
    if len(v) >= AVG:
        f[AVG - 1:] = np.lib.stride_tricks.sliding_window_view(v, AVG).mean(axis=1)
    known = np.isfinite(f)
    entry = np.where(known, (f > 0.0).astype(float), np.nan)
    exit_ = np.where(known, (f < 0.0).astype(float), np.nan)
    return entry, exit_


# --------------------------------------------------------------------------------------------
# strategy
# --------------------------------------------------------------------------------------------

STRATEGY = Strategy(
    name="context_tree_rank_prediction",
    domain="information_theory",
    hypothesis=(
        "Medium-horizon return paths carry sequential information - momentum in some markets, "
        "reversal in others, patterns that change over time - that no fixed model captures for "
        "every market. A universal source coder learns this information without choosing a "
        "model order: the context-tree-weighting (CTW) mixture over all variable-order Markov "
        "models up to depth D is, in code length, within O(k log n) bits of the best "
        "context-tree model in hindsight, and its coding distribution is therefore a "
        "minimax-optimal sequential predictor (prediction = compression). The strategy codes "
        "10-day block returns with a maximum-entropy quantiser (equiprobable rank cells "
        "relative to the recent distribution). This removes the level of drift and volatility, "
        "so the coder can only exploit predictive (mutual) information between past and future "
        "block ranks. It holds a long position while the coder's predictive distribution "
        "expects the next block to rank above the middle. Where block ranks are unpredictable, "
        "the coder's forecasts hover around the middle rank and the position switches "
        "frequently but is held only about 30-50% of the time; where they are predictable, the "
        "predictor's regret vanishes and the bets follow the learned structure."
    ),
    definition=(
        "Let r_t be daily log returns, h = 10 (horizon), B_t = sum_{i=0}^{h-1} r_{t-i} the h-day "
        "block return. Maximum-entropy quantisation: with q_j(s) the j/M quantiles (j=1..M-1, "
        "M = 4) of {B_{s-Q+1},...,B_s} (Q = 60), the symbol is x_s = #{j : B_s >= q_j(s)} in "
        "{0,..,M-1}, i.e. the equiprobable cell of B_s. Context of symbol x_s: "
        "c_s = (x_{s-h}, x_{s-2h}, ..., x_{s-Dh}), D = 3 (non-overlapping preceding blocks). "
        "Training set at t: pairs (x_s, c_s) for s in (t-W, t], W = 252. For every node u of the "
        "M-ary context tree of depth <= D, n_u(a) counts symbol a after context suffix u. "
        "Krichevsky-Trofimov estimate: P_KT(n) = Gamma(M/2) prod_a Gamma(n(a)+1/2) / "
        "(Gamma(1/2)^M Gamma(N+M/2)). CTW: P_w(u) = P_KT(n_u) at depth D, otherwise "
        "P_w(u) = 1/2 P_KT(n_u) + 1/2 prod_{b} P_w(bu). Sequential predictive distribution for "
        "the next block (t+1..t+h), whose context is c* = (x_t, x_{t-h}, ..., x_{t-(D-1)h}): "
        "p_t(a) = P_w^{root}(counts + a on path c*) / P_w^{root}(counts), normalised over a. "
        "Signal: centred expected rank S_t = sum_a (a - (M-1)/2) p_t(a). Rule: F_t = mean(S_{t-4}, "
        "..., S_t) (overlapping bets on the 10-day horizon); entry when F_t > 0, exit when "
        "F_t < 0. Lookback = W + D h + h + Q + 4 = 356 bars."
    ),
    references=(
        "Willems, F. M. J., Shtarkov, Y. M., Tjalkens, T. J. (1995). The context-tree weighting "
        "method: basic properties. IEEE Transactions on Information Theory 41(3), 653-664.",
        "Krichevsky, R. E., Trofimov, V. K. (1981). The performance of universal encoding. IEEE "
        "Transactions on Information Theory 27(2), 199-207.",
        "Rissanen, J. (1984). Universal coding, information, prediction, and estimation. IEEE "
        "Transactions on Information Theory 30(4), 629-636.",
        "Feder, M., Merhav, N., Gutman, M. (1992). Universal prediction of individual sequences. "
        "IEEE Transactions on Information Theory 38(4), 1258-1270.",
        "Merhav, N., Feder, M. (1998). Universal prediction. IEEE Transactions on Information "
        "Theory 44(6), 2124-2147.",
        "Cover, T. M., Thomas, J. A. (2006). Elements of Information Theory, 2nd ed. Wiley "
        "(ch. 10 rate distortion / quantisation, ch. 13 universal source coding).",
        "Jegadeesh, N., Titman, S. (1993). Returns to buying winners and selling losers. Journal "
        "of Finance 48(1), 65-91 (overlapping-horizon portfolio construction).",
    ),
    signals=(
        Signal(
            "ctw_rank_forecast",
            ctw_rank_forecast,
            ("log_return",),
            {
                "window": LongWindow(252),
                "depth": Order(3),
                "horizon": Lag(10),
                "levels": Levels(4),
                "quant_window": Window(60),
            },
            lambda window, depth, horizon, levels, quant_window:
                window + depth * horizon + horizon + quant_window,
            description="CTW expected centred rank of the next h-day block return",
        ),
    ),
    rule=rule,
    rule_lookback=AVG - 1,
    novelty=(
        "Earlier strategies from this field used entropy *levels* as regime filters: binary "
        "entropy of a short up/down string plus energy entropy (run_information_reversion), and "
        "permutation entropy relative to its own history (ordinal_efficiency_regime). This "
        "strategy uses no entropy level or regime threshold. It applies universal source coding "
        "as a predictor: the Bayesian context-tree-weighting mixture over all variable-order "
        "Markov models, with Krichevsky-Trofimov estimators, on a maximum-entropy quantisation "
        "of multi-day block returns. It trades the coder's sequential predictive distribution "
        "(the probability it would use to compress the next symbol). Each market learns its own "
        "dependency structure (momentum, reversal, or none) with no assumed model order."
    ),
    limitations=(
        "Long warm-up (356 bars) before the first decision. Overlapping block symbols make the "
        "KT counts over-confident (the effective sample is roughly W/h rather than W). The "
        "equiprobable quantiser deliberately discards the drift, so in steady bull markets "
        "exposure stays around 35-45% and much of the equity risk premium is forgone. Several "
        "markets have little sequential information at a 10-day horizon (most FX pairs here, "
        "weak equity indices), where results are about zero or negative. Turnover is moderate "
        "(roughly 5-14 entries per year), so very high-cost markets are penalised. On the "
        "development data the median objective was sensitive to discrete choices (number of "
        "levels, quantisation window, averaging span), with roughly ±0.1 swings, so "
        "out-of-sample performance should be expected to be noticeably lower than the best "
        "development value."
    ),
)
