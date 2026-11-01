"""Negative-bubble finite-time singularity: buy accelerating sell-offs that approach a critical
time, in the spirit of Johansen-Ledoit-Sornette critical-point models of bubbles and crashes."""

import numpy as np
from strategy_api import Signal, Strategy, Window, trailing_windows

# exponents of the power-law singularity and distances (bars) of the critical time beyond t
_M = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
_D = (1, 2, 3, 4, 5)
_Q_WINDOW = 120   # reference history for the score's own quantiles (bars)
_Q_MIN = 40       # minimum number of past scores before trading
_Q_LOW = 0.2      # trigger: score in its lowest 20 %
_Q_HIGH = 0.8     # overshoot: score in its highest 20 %
_HOLD = 10        # stay long while the trigger fired within the last _HOLD bars


def _basis(w):
    """Centred, unit-norm singular profiles (tc - tau)^m on tau = 0..w-1 and the linear profile."""
    tau = np.arange(w, dtype=float)
    cols = []
    for d in _D:
        tc = (w - 1) + d
        for m in _M:
            cols.append((tc - tau) ** m)
    X = np.array(cols)
    X = X - X.mean(axis=1, keepdims=True)
    X = X / np.linalg.norm(X, axis=1, keepdims=True)
    L = tau - tau.mean()
    L = L / np.linalg.norm(L)
    return X, L


def _score(log_price, window):
    """Signed excess fit of the singular model over a linear (constant-drift) model on one window.
    Negative = negative bubble (B > 0: decline accelerating towards tc); positive = positive bubble."""
    lp = np.asarray(log_price, float)
    rows = trailing_windows(lp, window)
    ok = np.all(np.isfinite(rows), axis=1)
    out = np.full(len(lp), np.nan)
    if not ok.any():
        return out
    Y = rows[ok]
    Y = Y - Y.mean(axis=1, keepdims=True)
    ny = np.linalg.norm(Y, axis=1)
    ny[ny == 0] = np.nan
    X, L = _basis(window)
    c = (Y @ X.T) / ny[:, None]       # correlation with each singular profile
    cl = (Y @ L) / ny                 # correlation with the linear profile
    r2 = c * c
    k = np.argmax(r2, axis=1)
    idx = np.arange(len(k))
    r2b = r2[idx, k]
    cb = c[idx, k]
    r2l = cl * cl
    imp = (r2b - r2l) / np.maximum(1 - r2l, 1e-12)
    out[ok] = np.where(cb > 0, -imp, imp)
    return out


def singularity_score(log_price, *, window):
    """Average of the signed singular-fit score over five nested windows (W/2 ... 2W)."""
    ws = (window // 2, (3 * window) // 4, window, (3 * window) // 2, 2 * window)
    acc = np.zeros(len(log_price))
    for w in ws:
        acc = acc + _score(log_price, w)
    return acc / len(ws)


def _causal_quantile(x, w, min_n, q):
    """q-quantile of the finite values among the last w bars (needs >= min_n of them)."""
    x = np.asarray(x, float)
    out = np.full(len(x), np.nan)
    for t in range(len(x)):
        v = x[max(0, t - w + 1): t + 1]
        v = v[np.isfinite(v)]
        if len(v) >= min_n and np.isfinite(x[t]):
            out[t] = np.quantile(v, q)
    return out


def rule(s):
    x = s["singularity_score"]
    lo = _causal_quantile(x, _Q_WINDOW, _Q_MIN, _Q_LOW)
    f = ((x < lo) & (x < 0)).astype(float)
    f[~np.isfinite(lo)] = np.nan
    rows = trailing_windows(f, _HOLD)
    nan = ~np.all(np.isfinite(rows), axis=1)
    fire = rows > 0.5
    entry = fire[:, -1].astype(float)
    hi = _causal_quantile(x, _Q_WINDOW, _Q_MIN, _Q_HIGH)
    overshoot = (x > hi) & (x > 0)
    exit_ = ((~np.any(fire, axis=1)) | overshoot).astype(float)
    entry[nan] = np.nan
    exit_[nan] = np.nan
    return entry, exit_


STRATEGY = Strategy(
    name="negative_bubble_singularity",
    domain="statistical_physics",
    hypothesis=(
        "Herding (positive feedback between price changes and the propensity to sell) makes a "
        "sell-off self-accelerating, so the log price follows a finite-time power-law "
        "singularity log p = A + B (tc - t)^m with 0 < m < 1, the hallmark of an approach to a "
        "critical point (Johansen-Ledoit-Sornette; 'negative bubbles' of Yan, Woodard and "
        "Sornette). Such a singular, critical-point decline is unsustainable: it ends near the "
        "critical time tc with a rebound, as the panic-driven over-reaction relaxes. When the "
        "recent path of an instrument is much better described by an imminent singularity "
        "(tc within one to five bars) with accelerating decline than by a constant drift, "
        "being long for the following two weeks collects the rebound. The signal uses only "
        "the shape of the path (scale-free, R^2 based) and each instrument's own score "
        "distribution, so it transfers across asset classes and volatility levels."
    ),
    definition=(
        "Signal. For a window of w bars ending at t, tau = 0..w-1 and y_tau = log price. For "
        "every critical time tc = (w-1)+d, d in {1,..,5}, and exponent m in {0.1,..,0.9} the "
        "power-law-singularity model y = A + B (tc - tau)^m is linear in (A, B); its fit "
        "quality is R2(d,m) = corr(y, (tc-tau)^m)^2. Take the best (d*, m*) and compare with "
        "the constant-drift model y = A + v tau (R2_lin): improvement "
        "I_w = (R2(d*,m*) - R2_lin) / (1 - R2_lin) in [0,1], i.e. the share of non-linear "
        "variance explained by the singularity. Sign: B > 0 (corr with (tc-tau)^m > 0) is a "
        "negative bubble (decline accelerating toward tc) and gets S_w = -I_w; B < 0 (positive "
        "bubble) gets S_w = +I_w. The signal is the average of S_w over the nested windows "
        "w in {W/2, 3W/4, W, 3W/2, 2W}, W = 60 (30..120 bars). "
        "Rule. Let q20_t and q80_t be the 20 % and 80 % quantiles of the signal over its last "
        "120 values (at least 40 needed). Trigger_t = S_t < q20_t and S_t < 0 (an unusually "
        "strong negative bubble for this instrument). Entry when the trigger fires. Exit when "
        "the trigger has not fired in the last 10 bars (the critical time has passed and the "
        "rebound had time to develop) or when the score shows an unusually strong positive "
        "bubble (S_t > q80_t and S_t > 0: the rebound itself has become super-exponential, "
        "take profit). Lookback 2W + 130 = 250 bars."
    ),
    references=(
        "Johansen, A., Ledoit, O., Sornette, D. (2000). Crashes as critical points. "
        "International Journal of Theoretical and Applied Finance 3(2), 219-255.",
        "Sornette, D. (2003). Why Stock Markets Crash: Critical Events in Complex Financial "
        "Systems. Princeton University Press.",
        "Yan, W., Woodard, R., Sornette, D. (2012). Diagnosis and prediction of rebounds in "
        "financial markets. Physica A 391(4), 1361-1380.",
        "Johansen, A., Sornette, D. (1999). Financial 'anti-bubbles': log-periodicity in gold "
        "and Nikkei collapses. International Journal of Modern Physics C 10(4), 563-575.",
        "Filimonov, V., Sornette, D. (2013). A stable and robust calibration scheme of the "
        "log-periodic power law model. Physica A 392(17), 3698-3707.",
    ),
    signals=(
        Signal(
            "singularity_score",
            singularity_score,
            ("log_price",),
            {"window": Window(60)},
            lambda window: 2 * window,
            "signed excess fit of a finite-time power-law singularity over a linear drift, "
            "averaged over nested windows (negative = accelerating decline / negative bubble)",
        ),
    ),
    rule=rule,
    rule_lookback=130,
    novelty=(
        "Uses the critical-point (finite-time singularity) description of price paths, not a "
        "drift/diffusion field (Kramers-Moyal), entropy production (fluctuation theorem) or "
        "spin-magnetisation relaxation. The quantity traded is the curvature structure of the "
        "path, i.e. how much better an imminent power-law singularity explains it than a "
        "constant drift, which is shape-only and independent of the size of the move. The "
        "nonlinear LPPLS calibration is replaced by an exhaustive grid over (tc, m) with "
        "closed-form linear fits, and the multi-window average mimics Sornette's multi-scale "
        "'DS LPPLS confidence' indicator in a deterministic, causal form."
    ),
    limitations=(
        "The singularity model is a phenomenological fit; on short windows R^2 improvements "
        "are noisy and many triggers are ordinary dips. In persistent bear markets "
        "negative-bubble patterns recur and the strategy repeatedly buys falling prices "
        "(development data: weak or negative late equity segments). Log-periodic oscillations "
        "were tested and did not help, so discrete scale invariance is not exploited. "
        "Performance on the development data was sensitive to the trigger quantile and the "
        "holding period (the objective varied by about 0.2 between neighbouring settings), so "
        "the edge is modest. Requires about 160 bars before the first trade and can come close "
        "to the minimum trade count on short, trending FX histories."
    ),
)
