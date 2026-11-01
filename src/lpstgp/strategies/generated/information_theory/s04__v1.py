"""Minimum-discrimination-information (I-projection) forecast of the forward return.

For each bar the strategy re-weights the instrument's own recent history of (state, outcome)
scenarios with the distribution that is closest in Kullback-Leibler divergence to the uniform
(empirical) distribution while reproducing the *current* state, and holds a long position while
the expected forward return under that minimum-relative-entropy posterior is positive.
"""

import numpy as np

from strategy_api import Lag, LongWindow, Signal, Strategy, Window

MIN_SCENARIOS = 60  # smallest scenario set used while the history is still short
RIDGE = 1.0  # Gaussian prior on the dual variables (soft moment constraints)
NEWTON_STEPS = 25


def _i_projection_weights(D: np.ndarray, ridge: float) -> np.ndarray:
    """Weights q_i ∝ exp(theta·d_i) of the (soft) I-projection of the uniform distribution onto
    {q : E_q[d] = 0}: theta minimises log mean exp(theta·d_i) + ridge/2 |theta|^2."""
    k = D.shape[1]
    th = np.zeros(k)
    for _ in range(NEWTON_STEPS):
        a = D @ th
        a -= a.max()
        w = np.exp(a)
        w /= w.sum()
        m = w @ D
        C = (D * w[:, None]).T @ D - np.outer(m, m)
        step = np.linalg.solve(C + ridge * np.eye(k), m + ridge * th)
        th -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    a = D @ th
    a -= a.max()
    w = np.exp(a)
    return w / w.sum()


def _mdi_forecast(log_return, *, scenarios, horizon, state_window):
    r = np.asarray(log_return, dtype=np.float64)
    T = len(r)
    out = np.full(T, np.nan)
    if T < state_window + horizon + MIN_SCENARIOS:
        return out
    # state of day i from r[i-state_window+1 .. i]: drift in volatility units and log volatility
    W = np.lib.stride_tricks.sliding_window_view(r, state_window)
    with np.errstate(invalid="ignore", divide="ignore"):
        vol = np.sqrt(np.maximum(np.mean(W * W, axis=1), 1e-16))
        f_drift = np.full(T, np.nan)
        f_lvol = np.full(T, np.nan)
        f_drift[state_window - 1 :] = np.mean(W, axis=1) / vol
        f_lvol[state_window - 1 :] = np.log(vol)
    # outcome of day i: forward log return r[i+1 .. i+horizon]
    y = np.full(T, np.nan)
    y[: T - horizon] = np.lib.stride_tricks.sliding_window_view(r, horizon).sum(axis=1)[1:]
    for t in range(state_window - 1 + MIN_SCENARIOS + horizon, T):
        fnow = np.array([f_drift[t], f_lvol[t]])
        if not np.all(np.isfinite(fnow)):
            continue
        lo = max(t - horizon - scenarios + 1, 0)
        hi = t - horizon + 1  # outcomes of these days end at or before bar t
        F = np.column_stack((f_drift[lo:hi], f_lvol[lo:hi]))
        Y = y[lo:hi]
        ok = np.all(np.isfinite(F), axis=1) & np.isfinite(Y)
        if ok.sum() < MIN_SCENARIOS:
            continue
        F = F[ok]
        Y = Y[ok]
        mu = F.mean(axis=0)
        sd = F.std(axis=0) + 1e-12
        D = (F - mu) / sd - (fnow - mu) / sd
        q = _i_projection_weights(D, RIDGE)
        out[t] = (q @ Y) / (Y.std() + 1e-12)
    return out


mdi_forecast = Signal(
    name="mdi_forecast",
    fn=_mdi_forecast,
    inputs=("log_return",),
    params={"scenarios": LongWindow(252), "horizon": Lag(10), "state_window": Window(20)},
    lookback=lambda scenarios, horizon, state_window: scenarios + horizon + state_window,
    description=(
        "Expected forward `horizon`-day log return (in units of its scenario standard deviation) "
        "under the minimum-KL re-weighting of the last `scenarios` days that matches today's "
        "state (drift/vol and log vol over `state_window` days)."
    ),
)


def rule(signals):
    f = signals["mdi_forecast"]
    ok = np.isfinite(f)
    entry = np.where(ok, (f > 0.0).astype(float), np.nan)
    exit_ = np.where(ok, (f < 0.0).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="min_discrimination_forecast",
    domain="information_theory",
    hypothesis=(
        "Whether holding a market is rewarded depends on its current state (recent drift and "
        "volatility), but the sign and shape of that dependence differ across markets and "
        "drift over time (momentum here, rebounds after stress there, leverage effects in "
        "equities, flight-to-safety rallies in others). Kullback's principle of minimum "
        "discrimination information gives the least-biased way to condition a market's own "
        "recent history on today's state. Among all re-weightings of the past year's "
        "(state, forward return) scenarios whose average state equals today's, choose the one "
        "closest to the empirical distribution in relative entropy, i.e. the one that adds the "
        "fewest nats of information beyond the state constraint. The expected forward return "
        "under this I-projection is a model-free, market-specific forecast. A long position is "
        "held while that forecast is positive and closed when it turns negative. The strategy "
        "therefore steps aside in states that the market's own history associates with losses "
        "(e.g. high-volatility sell-offs in equities) and stays invested where similar states "
        "were rewarded."
    ),
    definition=(
        "Daily log returns r_t. State of day i (s = state_window = 20): "
        "x_i = (m_i/v_i, log v_i), with m_i = (1/s) sum_{k=0}^{s-1} r_{i-k} and "
        "v_i = sqrt((1/s) sum_{k=0}^{s-1} r_{i-k}^2). Outcome of day i (h = horizon = 10): "
        "y_i = sum_{k=1}^{h} r_{i+k}. At bar t the scenario set is "
        "S_t = {i : t-h-N+1 <= i <= t-h} (N = scenarios = 252, using at least 60 while history "
        "is shorter), so every outcome y_i is known at t. The states are standardised over S_t "
        "(z_i = (x_i - mean)/sd) and d_i = z_i - z_t. Minimum discrimination information "
        "(I-projection, Kullback 1959; Csiszar 1975): q* = argmin_q KL(q || u) subject to "
        "E_q[d] = 0, with u uniform on S_t. Its solution is the exponential family "
        "q_i(theta) = exp(theta.d_i) / sum_j exp(theta.d_j), where theta minimises the convex "
        "dual log sum_i exp(theta.d_i). The constraint is softened with a Gaussian prior on "
        "theta (ridge lambda = 1): theta* = argmin_theta [log sum_i exp(theta.d_i) + "
        "(lambda/2)|theta|^2], solved by Newton's method. Equivalently, q* is the MAP "
        "exponential tilt and KL(q*||u) stays finite when today's state lies outside the "
        "historical hull. Signal: F_t = sum_i q*_i y_i / sd_{S_t}(y), the minimum-relative-"
        "entropy forecast of the h-day forward return, in standard-deviation units. "
        "Rule: entry when F_t > 0, exit when F_t < 0 (position from entry until exit)."
    ),
    references=(
        "Kullback, S. (1959). Information Theory and Statistics. New York: Wiley.",
        "Csiszar, I. (1975). I-divergence geometry of probability distributions and "
        "minimization problems. Annals of Probability, 3(1), 146-158.",
        "Shore, J. E., & Johnson, R. W. (1980). Axiomatic derivation of the principle of maximum "
        "entropy and the principle of minimum cross-entropy. IEEE Transactions on Information "
        "Theory, 26(1), 26-37.",
        "Cover, T. M., & Thomas, J. A. (2006). Elements of Information Theory (2nd ed.), "
        "ch. 11 (Information theory and statistics; I-projection, Sanov's theorem). Wiley.",
        "Meucci, A. (2008). Fully Flexible Views: Theory and Practice. Risk, 21(10), 97-102.",
        "Stutzer, M. (1996). A simple nonparametric approach to derivative security valuation. "
        "Journal of Finance, 51(5), 1633-1652.",
    ),
    novelty=(
        "The earlier strategies in this field measure entropy or complexity of the return "
        "process itself: binary/energy entropy of runs, permutation entropy, and context-tree-"
        "weighting compression of block ranks. This strategy measures no entropy of returns at "
        "all. It uses relative entropy as an inference principle: the minimum-discrimination-"
        "information (I-projection / entropy-pooling) update of the empirical scenario "
        "distribution, conditioned on today's drift/volatility state, gives a nonparametric "
        "conditional forecast of the forward return. There is no fixed model of how state "
        "maps to return. The exponential tilt learns, per market and over a rolling year, "
        "whether e.g. high volatility or recent losses preceded gains or losses. The ridge-"
        "regularised dual keeps the update finite for states never seen before."
    ),
    limitations=(
        "The forecast is a weighted mean of about 250 overlapping 10-day outcomes, so it is "
        "noisy. In driftless markets (most currency pairs) it hovers around zero, giving about "
        "40-50% exposure with little edge. It learns only from the last year, so it adapts "
        "late to new regimes and can be wrong right after a break (e.g. the first sell-off "
        "after a long calm). Overlapping outcomes and the shared state window make the "
        "effective sample much smaller than 252. Because the rule has no hysteresis, "
        "trade frequency depends on how often the forecast changes sign. Hysteresis was "
        "tested and made entries too rare for the minimum-trading requirement, so turnover "
        "is moderate (about 2-10 round trips a year). The roughly 90-bar warm-up and the "
        "short one-year memory make early results depend on the first year of data. Results "
        "on the development data were sensitive to the horizon, state window and ridge."
    ),
    signals=(mdi_forecast,),
    rule=rule,
    rule_lookback=0,
)
