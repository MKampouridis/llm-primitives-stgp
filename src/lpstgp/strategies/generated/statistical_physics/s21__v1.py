"""Kramers-Moyal state-conditional drift strategy (statistical physics).

The log price is treated as a Langevin/Fokker-Planck process whose drift depends on a
dimensionless state variable (the normalised displacement of price from its local mean).
The first two finite-time Kramers-Moyal conditional moments are estimated non-parametrically
(Nadaraya-Watson kernel in state space) from the instrument's own recent history; the strategy
is long while the estimated drift at the current state is positive relative to the diffusion.
"""

import numpy as np

from strategy_api import Lag, LongWindow, Signal, Strategy, Window, trailing_windows

_BANDWIDTH = 0.5  # Gaussian kernel bandwidth in units of the state variable z
_ENTRY = 0.10     # enter when the drift-to-diffusion ratio exceeds this
_EXIT = 0.0       # exit when the estimated drift turns negative


def _state(log_price: np.ndarray, window: int) -> np.ndarray:
    """z_t = (x_t - mean(x_{t-w+1..t})) / std(x_{t-w+1..t}), x = log price."""
    rows = trailing_windows(log_price, window)
    m = np.mean(rows, axis=1)
    s = np.std(rows, axis=1, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (log_price - m) / s
    z[~np.isfinite(z)] = np.nan
    return z


def km_drift(log_price, *, state_window=Window(60), est_window=LongWindow(252), tau=Lag(5)):
    """Kramers-Moyal drift-to-diffusion ratio at the current state.

    For each bar t, pairs (z_s, dx_s) with dx_s = x_{s+tau} - x_s and s + tau <= t are taken from
    the last ``est_window`` admissible s. With Gaussian kernel weights
    w_s = exp(-(z_s - z_t)^2 / (2 h^2)):
        M1(z_t) = sum w dx / sum w      (finite-tau first KM moment,  = tau * D1)
        M2(z_t) = sum w dx^2 / sum w    (finite-tau second KM moment, ~ 2 tau * D2)
    and the signal is M1 / sqrt(M2) (drift relative to diffusive spread over tau).
    """
    z = _state(log_price, state_window)
    n = len(log_price)
    out = np.full(n, np.nan)
    dx = np.full(n, np.nan)
    if n > tau:
        dx[: n - tau] = log_price[tau:] - log_price[: n - tau]
    start = state_window - 1 + est_window + tau
    for t in range(start, n):
        if not np.isfinite(z[t]):
            continue
        lo = t - tau - est_window + 1
        hi = t - tau + 1  # s in [lo, hi) so that s + tau <= t (strictly causal)
        zs = z[lo:hi]
        d = dx[lo:hi]
        ok = np.isfinite(zs) & np.isfinite(d)
        if ok.sum() < est_window // 2:
            continue
        zs, d = zs[ok], d[ok]
        w = np.exp(-0.5 * ((zs - z[t]) / _BANDWIDTH) ** 2)
        sw = w.sum()
        if sw <= 1e-8:
            continue
        m1 = np.sum(w * d) / sw
        m2 = np.sum(w * d * d) / sw
        if m2 <= 0:
            continue
        out[t] = m1 / np.sqrt(m2)
    return out


KM_DRIFT = Signal(
    name="km_drift",
    fn=km_drift,
    inputs=("log_price",),
    params={"state_window": Window(60), "est_window": LongWindow(252), "tau": Lag(5)},
    lookback=lambda state_window, est_window, tau: state_window + est_window + tau + 1,
    description="Kernel Kramers-Moyal drift / sqrt(second moment) at the current state z_t.",
)


def rule(signals):
    k = signals["km_drift"]
    f = np.isfinite(k)
    entry = np.where(f, (k > _ENTRY).astype(float), np.nan)
    exit_ = np.where(f, (k < _EXIT).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="kramers_moyal_state_drift",
    domain="statistical_physics",
    hypothesis=(
        "Price dynamics can be described as a Langevin process dx = D1(z) dt + sqrt(2 D2(z)) dW "
        "whose drift depends on a dimensionless state z (displacement of log price from its "
        "local mean in units of local dispersion). The state-dependent drift field D1(z), i.e. "
        "the effective force -dU/dz of the landscape the price moves in, is persistent enough "
        "over months to be estimated from an instrument's own recent history with finite-time "
        "Kramers-Moyal coefficients. Being long only when the estimated drift at the current "
        "state is clearly positive relative to the diffusion captures adaptive trend or "
        "reversion behaviour (whichever the instrument's recent dynamics shows) and stays flat "
        "where the drift field is indistinguishable from zero (driftless, random-walk-like "
        "markets)."
    ),
    definition=(
        "x_t = log price. State: z_t = (x_t - mean_{60}(x)) / std_{60}(x) over the trailing 60 "
        "bars. Finite-time increments dx_s = x_{s+tau} - x_s, tau = 5. For each t, use the "
        "252 most recent s with s + tau <= t and Gaussian kernel weights "
        "w_s = exp(-(z_s - z_t)^2 / (2 h^2)), h = 0.5. Conditional Kramers-Moyal moments: "
        "M1(z_t) = sum_s w_s dx_s / sum_s w_s (= tau D1(z_t) + O(tau^2)), "
        "M2(z_t) = sum_s w_s dx_s^2 / sum_s w_s (= 2 tau D2(z_t) + O(tau^2)). "
        "Signal K_t = M1(z_t) / sqrt(M2(z_t)), a drift-to-diffusion (Peclet-type) ratio. "
        "Rule: entry when K_t > 0.10; exit when K_t < 0 (hysteresis band [0, 0.10]). "
        "Total lookback 60 + 252 + 5 + 1 = 318 bars."
    ),
    references=(
        "Risken, H. (1989). The Fokker-Planck Equation: Methods of Solution and Applications, "
        "2nd ed. Springer.",
        "Friedrich, R., Peinke, J. (1997). Description of a turbulent cascade by a Fokker-Planck "
        "equation. Physical Review Letters 78, 863-866.",
        "Friedrich, R., Peinke, J., Renner, C. (2000). How to quantify deterministic and random "
        "influences on the statistics of the foreign exchange market. Physical Review Letters "
        "84, 5224-5227.",
        "Friedrich, R., Peinke, J., Sahimi, M., Tabar, M. R. R. (2011). Approaching complexity by "
        "stochastic methods: From biological systems to turbulence. Physics Reports 506, 87-162.",
        "Siegert, S., Friedrich, R., Peinke, J. (1998). Analysis of data sets of stochastic "
        "systems. Physics Letters A 243, 275-280.",
        "Nadaraya, E. A. (1964). On estimating regression. Theory of Probability and its "
        "Applications 9, 141-142.",
    ),
    signals=(KM_DRIFT,),
    rule=rule,
    rule_lookback=0,
    novelty=(
        "Instead of a fixed trend or reversion rule, the strategy reconstructs the state-"
        "dependent drift field of a Fokker-Planck description of each instrument's price from "
        "data (finite-time Kramers-Moyal conditional moments, kernel-smoothed in state space) "
        "and trades the sign and strength of the drift at the current state. The same "
        "estimator yields momentum-like behaviour where the drift field increases with z, "
        "reversion-like behaviour where it decreases, and no position where it is flat. "
        "Using tau = 5 increments rather than daily ones raised the signal-to-noise of the "
        "drift estimate and improved results markedly on development data."
    ),
    limitations=(
        "The kernel drift estimate uses about 252 overlapping 5-bar increments and is noisy; "
        "per-instrument results on development data varied a lot with small changes to the "
        "parameters (median objective about -0.05 at best, with neighbouring settings between "
        "-0.09 and -0.2). The finite-tau KM estimate is biased when tau is not small relative "
        "to the drift's time scale. It assumes a quasi-stationary drift field over the "
        "estimation window, so regime breaks (crashes, policy shocks) are picked up only after "
        "a lag. The strategy is long-only, so on driftless markets (most currency pairs) it is "
        "often flat and the drawdowns of its occasional positions dominate the score. The "
        "first ~318 bars produce no signal."
    ),
)
