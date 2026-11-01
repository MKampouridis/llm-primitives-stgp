"""Fluctuation-theorem NESS dip strategy (statistical physics).

A market is treated as a driven stochastic system. Over a long window it is either close to
equilibrium (time-reversible increments, no net probability current, zero entropy production)
or in a non-equilibrium steady state (NESS) that carries a persistent current. The
Evans-Searles / Gallavotti-Cohen fluctuation theorem (FT) states that, in a NESS with entropy
production rate Sigma, fluctuations of the time-integrated current A obey

    ln[ P(+A) / P(-A) ] = Sigma * A .

So the sign of an increment, given its size, is logistic in the size with slope Sigma. We
estimate Sigma by maximum likelihood on that FT symmetry function and test it against zero
(detailed balance). In a positive-current NESS, short negative fluctuations of the integrated
current are exponentially suppressed but not absent, and they are transient. The rule buys
such fluctuations and exits once they have relaxed (overshot upward) or once the current has
vanished.
"""

import numpy as np

from strategy_api import LongWindow, Lag, Signal, Strategy, Window, trailing_windows


# --- signal 1: fluctuation-theorem entropy-production z-score -------------------------------


def _ft_symmetry_mle(a: np.ndarray, iters: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """Row-wise MLE of Sigma in P(sign=+ | |a|) = 1 / (1 + exp(-Sigma |a|)).

    Returns (Sigma_hat, z) with z = Sigma_hat * sqrt(Fisher information)."""
    x = np.abs(a)
    y = (a > 0).astype(float)
    valid = a != 0
    s = np.zeros(a.shape[0])
    for _ in range(iters):  # Newton-Raphson, concave log-likelihood
        p = 1.0 / (1.0 + np.exp(-s[:, None] * x))
        grad = np.sum(np.where(valid, (y - p) * x, 0.0), axis=1)
        hess = np.sum(np.where(valid, p * (1.0 - p) * x * x, 0.0), axis=1)
        s = np.clip(s + grad / np.maximum(hess, 1e-12), -20.0, 20.0)
    p = 1.0 / (1.0 + np.exp(-s[:, None] * x))
    info = np.sum(np.where(valid, p * (1.0 - p) * x * x, 0.0), axis=1)
    return s, s * np.sqrt(info)


def entropy_production_z(log_return, *, long_window):
    rows = trailing_windows(log_return, long_window)
    out = np.full(len(log_return), np.nan)
    ok = np.all(np.isfinite(rows), axis=1)
    if ok.any():
        r = rows[ok]
        sd = np.std(r, axis=1, keepdims=True)
        _, z = _ft_symmetry_mle(r / np.maximum(sd, 1e-12))
        out[ok] = z
    return out


# --- signal 2: standardised fluctuation of the integrated current over tau bars -------------


def current_fluctuation(log_price, *, window, tau):
    lp = np.asarray(log_price, dtype=float)
    n = len(lp)
    r = np.full(n, np.nan)
    r[1:] = np.diff(lp)
    temp = np.sqrt(np.mean(trailing_windows(r, window) ** 2, axis=1))  # local "temperature"
    a = np.full(n, np.nan)
    a[tau:] = lp[tau:] - lp[:-tau]
    with np.errstate(divide="ignore", invalid="ignore"):
        d = a / (temp * np.sqrt(tau))
    d[~np.isfinite(d)] = np.nan
    return d


ENTROPY = Signal(
    name="entropy_production_z",
    fn=entropy_production_z,
    inputs=("log_return",),
    params={"long_window": LongWindow(252)},
    lookback=lambda long_window: long_window,
    description="Fisher z of the fluctuation-theorem entropy-production rate Sigma (MLE of "
    "ln P(+a)/P(-a) = Sigma*a) over the last long_window standardised daily returns.",
)

FLUCT = Signal(
    name="current_fluctuation",
    fn=current_fluctuation,
    inputs=("log_price",),
    params={"window": Window(60), "tau": Lag(5)},
    lookback=lambda window, tau: max(window, tau) + 1,
    description="tau-bar integrated current (log-price change) in units of its equilibrium "
    "scale sqrt(tau) * rms daily return over window.",
)


# --- rule ------------------------------------------------------------------------------------

Z_ENTER = 0.0     # current must point upward (Sigma_hat > 0)
Z_EXIT = -0.5     # current has reversed: leave the NESS
D_DIP = -0.5      # negative fluctuation against the current (in equilibrium units)
D_RELAX = 1.0     # fluctuation has relaxed and overshot upward


def rule(signals):
    z = signals["entropy_production_z"]
    d = signals["current_fluctuation"]
    ok = np.isfinite(z) & np.isfinite(d)
    entry = np.where(ok, ((z > Z_ENTER) & (d < D_DIP)).astype(float), np.nan)
    exit_ = np.where(ok, ((d > D_RELAX) | (z < Z_EXIT)).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="fluctuation_theorem_ness_dip",
    domain="statistical_physics",
    hypothesis=(
        "Price increments are the time-integrated current of a driven stochastic system. Over "
        "about a year an instrument is either close to equilibrium (detailed balance, "
        "time-reversible increments, zero entropy production) or in a non-equilibrium steady "
        "state (NESS) with a persistent current. The fluctuation theorem implies that, in a "
        "NESS with positive entropy production Sigma, negative fluctuations of the integrated "
        "current are exponentially suppressed (P(-A)/P(+A) = exp(-Sigma A)). They still occur "
        "but are transient and relax back along the current. Buying short negative "
        "fluctuations only while the estimated entropy production is positive, and leaving "
        "once they have relaxed or once the current disappears, harvests the steady-state "
        "drift with low exposure and avoids equilibrium (driftless) or reversed-current regimes."
    ),
    definition=(
        "Daily log returns r_t, log price p_t.\n"
        "1) Entropy production (FT symmetry function). Over the last L=252 bars standardise "
        "a_i = r_i / sd(r). Under the fluctuation theorem ln[P(+a)/P(-a)] = Sigma*a, so "
        "P(sign a_i = + | |a_i|) = 1/(1+exp(-Sigma |a_i|)). Sigma_hat is the maximum-likelihood "
        "estimate (8 Newton steps on the concave log-likelihood "
        "sum_i [y_i ln p_i + (1-y_i) ln(1-p_i)], y_i = 1{a_i>0}). Its Fisher information is "
        "I = sum_i p_i(1-p_i) a_i^2 and the test statistic is z_t = Sigma_hat * sqrt(I), with "
        "z ~ N(0,1) under detailed balance (Sigma = 0).\n"
        "2) Current fluctuation: d_t = (p_t - p_{t-tau}) / (sqrt(tau) * T_t), tau=5, with "
        "local temperature T_t = sqrt(mean_{60 bars} r^2).\n"
        "Rule: entry when z_t > 0 and d_t < -0.5 (negative fluctuation inside a positive-"
        "current NESS); exit when d_t > 1.0 (fluctuation relaxed and overshot) or z_t < -0.5 "
        "(current reversed). Long otherwise held; flat otherwise."
    ),
    references=(
        "Evans, D. J., Cohen, E. G. D. & Morriss, G. P. (1993). Probability of second law "
        "violations in shearing steady states. Physical Review Letters 71, 2401-2404.",
        "Gallavotti, G. & Cohen, E. G. D. (1995). Dynamical ensembles in nonequilibrium "
        "statistical mechanics. Physical Review Letters 74, 2694-2697.",
        "Kurchan, J. (1998). Fluctuation theorem for stochastic dynamics. Journal of Physics A "
        "31, 3719-3729.",
        "Evans, D. J. & Searles, D. J. (2002). The fluctuation theorem. Advances in Physics 51, "
        "1529-1585.",
        "Seifert, U. (2012). Stochastic thermodynamics, fluctuation theorems and molecular "
        "machines. Reports on Progress in Physics 75, 126001.",
    ),
    novelty=(
        "Unlike the Kramers-Moyal state-drift strategy, this estimates no state-dependent drift "
        "or potential landscape D1(z). It tests detailed balance through the fluctuation-theorem "
        "symmetry function of the increment distribution: a one-parameter logistic MLE of "
        "ln P(+a)/P(-a) = Sigma*a, with a Fisher z-score. The trading event is a transient "
        "negative fluctuation of the integrated current inside a positive-entropy-production "
        "steady state, not the current displacement of price from a local mean."
    ),
    limitations=(
        "The FT form assumes a stationary NESS within the 252-bar window; regime changes are "
        "detected only with a lag of months. The logistic symmetry function is exact for "
        "Gaussian-like increments with drift; strong skew (e.g. equity crash asymmetry) biases "
        "Sigma_hat. The z-score treats days as independent, so volatility clustering overstates "
        "its precision. Holding periods are short (days to weeks) with moderate turnover, so "
        "high-cost markets lose part of the edge. The long window needs a year of warm-up, and "
        "markets with little history may trade close to the minimum frequency. Driftless "
        "markets such as many FX pairs give near-zero results by design."
    ),
    signals=(ENTROPY, FLUCT),
    rule=rule,
    rule_lookback=0,
)
