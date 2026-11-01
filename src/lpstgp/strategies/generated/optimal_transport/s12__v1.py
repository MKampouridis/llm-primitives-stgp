"""gain_loss_time_transport: optimal transport on the time axis between the temporal law of
gains and the temporal law of losses inside a trailing window.

Long while the loss mass of the window has been transported toward the present relative to the
gain mass (a pullback after earlier gains); flat once the ordering has flipped (losses older than
gains, the rebound is done). Hysteresis on the normalised transport index limits turnover.
"""

from __future__ import annotations

import numpy as np

from strategy_api import Signal, Strategy, Window, trailing_windows

ENTRY_LEVEL = -0.25  # enter when D < -0.25 (loss mass clearly later than gain mass)
EXIT_LEVEL = 0.25  # exit when D > +0.25 (loss mass clearly earlier than gain mass)


def _temporal_cdf(mass: np.ndarray) -> np.ndarray:
    """Row-wise CDF on the time grid 1/W, 2/W, ..., 1 of a non-negative mass profile."""
    total = np.sum(mass, axis=1, keepdims=True)
    total = np.where(total > 0, total, np.nan)
    return np.cumsum(mass, axis=1) / total


def _gain_loss_time_transport(log_return: np.ndarray, *, window: int) -> np.ndarray:
    """D_t = int (F_L - F_G) dtau / int |F_L - F_G| dtau  in [-1, 1] over the last `window` bars.

    F_G, F_L: CDFs on the time axis of the gain mass max(r,0) and the loss mass max(-r,0).
    The denominator is the 1-D Wasserstein-1 distance between the two temporal laws, the
    numerator its signed version (mean time of gains minus mean time of losses).
    D > 0: gains came after losses (rebound). D < 0: losses came after gains (pullback).
    """
    r = np.asarray(log_return, dtype=np.float64)
    out = np.full(len(r), np.nan)
    rows = trailing_windows(r, window)
    ok = np.all(np.isfinite(rows), axis=1)
    if not ok.any():
        return out
    x = rows[ok]
    f_loss = _temporal_cdf(np.maximum(-x, 0.0))
    f_gain = _temporal_cdf(np.maximum(x, 0.0))
    diff = f_loss - f_gain
    w1 = np.mean(np.abs(diff), axis=1)
    signed = np.mean(diff, axis=1)
    d = signed / np.where(w1 > 0, w1, np.nan)
    out[ok] = np.where(np.isfinite(d), d, 0.0)
    return out


GAIN_LOSS_TIME_TRANSPORT = Signal(
    name="gain_loss_time_transport",
    fn=_gain_loss_time_transport,
    inputs=("log_return",),
    params={"window": Window(60)},
    lookback=lambda window: window,
    description=(
        "Normalised signed Wasserstein-1 transport on the time axis from the temporal law of "
        "loss mass to the temporal law of gain mass in the trailing window; in [-1, 1]."
    ),
)


def rule(signals):
    d = signals["gain_loss_time_transport"]
    ok = np.isfinite(d)
    entry = np.where(ok, (d < ENTRY_LEVEL).astype(float), np.nan)
    exit_ = np.where(ok, (d > EXIT_LEVEL).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="gain_loss_time_transport",
    domain="optimal_transport",
    hypothesis=(
        "Inside a recent window, the gains and the losses each form a probability law on the "
        "time axis (where in the window the up-moves and the down-moves happened, weighted by "
        "their size). Optimally transporting the loss law onto the gain law along time tells "
        "whether the market rose and then gave some of it back (loss mass transported toward "
        "the present: a pullback) or fell and then recovered (loss mass in the past: the rebound "
        "has already happened). Pullbacks after earlier gains are mostly driven by liquidity "
        "demand and profit taking rather than new information. Investors who supply liquidity "
        "by buying them earn a short-horizon reversal premium until the ordering flips. Once "
        "the gains are the most recent part of the window, that premium has already been paid "
        "and the strategy steps aside. Each temporal law is normalised by its own total mass, so "
        "the index depends only on the timing of gains relative to losses. It does not depend on "
        "the net drift of the window, the volatility level or the share of up days. That makes it "
        "neither a momentum nor a plain reversal rule on the window return."
    ),
    definition=(
        "Let r_1..r_W be the last W log returns (W = window = 60, i = 1 oldest), tau_i = i/W. "
        "Gain mass g_i = max(r_i, 0), loss mass l_i = max(-r_i, 0). Temporal probability laws "
        "mu_G = sum_i (g_i / sum_j g_j) delta_{tau_i}, mu_L = sum_i (l_i / sum_j l_j) delta_{tau_i}, "
        "with CDFs F_G(tau_k) = sum_{i<=k} g_i / sum g, F_L likewise. On the line the optimal "
        "transport cost is W1(mu_L, mu_G) = int_0^1 |F_L(tau) - F_G(tau)| dtau (Vallender), and the "
        "signed transport displacement is S = int_0^1 (F_L - F_G) dtau = E_{mu_G}[tau] - E_{mu_L}[tau]. "
        "Discretely, W1 = (1/W) sum_k |F_L(tau_k) - F_G(tau_k)|, S = (1/W) sum_k (F_L - F_G)(tau_k). "
        "The signal is the transport dominance index D = S / W1 in [-1, 1]. D = +1 iff mu_G "
        "first-order dominates mu_L in time, i.e. gains come after losses at every quantile "
        "level. D = -1 iff loss mass lies later at every level. D = 0 if a window has no gains, no "
        "losses or identical temporal laws. Rule (hysteresis): entry when D_t < -0.25 (loss mass "
        "transported toward the present, a pullback), exit when D_t > +0.25 (loss mass in the past); "
        "the position is otherwise held."
    ),
    references=(
        "Villani, C. (2009). Optimal Transport: Old and New. Grundlehren der mathematischen "
        "Wissenschaften 338, Springer.",
        "Vallender, S. S. (1974). Calculation of the Wasserstein distance between probability "
        "distributions on the line. Theory of Probability and Its Applications 18(4), 784-786.",
        "Santambrogio, F. (2015). Optimal Transport for Applied Mathematicians. Progress in "
        "Nonlinear Differential Equations and Their Applications 87, Birkhauser.",
        "Peyre, G. and Cuturi, M. (2019). Computational Optimal Transport. Foundations and Trends "
        "in Machine Learning 11(5-6), 355-607.",
        "Lehmann, B. N. (1990). Fads, martingales, and market efficiency. Quarterly Journal of "
        "Economics 105(1), 1-28.",
        "Jegadeesh, N. (1990). Evidence of predictable behavior of security returns. Journal of "
        "Finance 45(3), 881-898.",
        "Nagel, S. (2012). Evaporating liquidity. Review of Financial Studies 25(7), 2005-2039.",
    ),
    signals=(GAIN_LOSS_TIME_TRANSPORT,),
    rule=rule,
    rule_lookback=0,
    novelty=(
        "The earlier strategies in this field all transport in the space of return values. They "
        "compare quantiles of a recent return law with a reference law, the loss half of a law "
        "with an earlier period, or gain magnitudes with loss magnitudes in the same window. This "
        "strategy transports along the time axis instead. The probability measures are the "
        "temporal occupation laws of gain mass and of loss mass, and the transport plan says how "
        "far, and in which direction in time, the loss mass must move to match the gain mass. The "
        "signal is therefore about the ordering of gains and losses within the window. It does "
        "not use their sizes relative to each other or to a reference period: rescaling all "
        "gains, or all losses, by a constant leaves it unchanged. The dominance normalisation "
        "S / W1 turns it into a scale-free measure of first-order stochastic dominance in time."
    ),
    limitations=(
        "On the development data the edge came mainly from commodities and equity indices; "
        "currency pairs, which trend more than they revert at this horizon, were mixed to "
        "negative. Government bonds and cryptocurrencies were not in the development set. The "
        "result depends on the window: 20, 30, 40 and 60 bars beat a buy-and-hold baseline, but "
        "90 bars did not. Without hysteresis the same signal was about neutral, so the "
        "thresholds matter. The rule buys pullbacks without a stop, so in a persistent bear "
        "market it can repeatedly re-enter falling prices. Exposure is about 50%, with roughly "
        "12-16 round trips per year, so instruments with high trading costs pay a noticeable "
        "turnover drag. The segment-median objective is noisy across nearby parameter choices, "
        "so out-of-sample performance should be expected to be well below the in-sample best."
    ),
)
