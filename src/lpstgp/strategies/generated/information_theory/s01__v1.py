"""Run-information reversion with energy-entropy regime holding.

Three information-theoretic statistics of the daily return process:

* sign_info        - signed binary-entropy deficit of the up/down string over 10 bars
                     (how compressible the recent run is, and in which direction);
* energy_entropy   - normalised Shannon entropy of the distribution of squared-return
                     "energy" across the last 20 bars (diffuse vs. shock-concentrated risk);
* drift_information- signed Kullback-Leibler information (nats) that the last 252 returns
                     carry against a zero-drift model.
"""
from __future__ import annotations

import numpy as np

from strategy_api import LongWindow, Signal, Strategy, Window, trailing_windows

L_REF = 126   # bars of energy-entropy history used for the adaptive quantile thresholds
Q_HI = 0.5    # energy entropy above its median  -> diffuse (calm) regime
Q_LO = 0.2    # energy entropy below its 20% quantile -> shock-concentrated regime
THETA = 0.1   # bits: a run is "compressible" when |sign_info| > THETA (<=3 or >=7 ups in 10)
X_TP = 0.2    # bits: strongly compressible up-run (>=8 ups in 10) -> take profit
D_MIN = 0.0   # nats: long-run drift information must be positive to hold the calm regime


# --- signals -----------------------------------------------------------------------------------


def sign_info(log_return, *, window):
    """I_s = sign(p - 1/2) * (1 - H2(p)) bits, p = share of positive returns in the window."""
    rows = trailing_windows(log_return, window)
    ok = np.all(np.isfinite(rows), axis=1)
    out = np.full(len(log_return), np.nan)
    p = np.mean(rows[ok] > 0, axis=1)
    pc = np.clip(p, 1e-12, 1 - 1e-12)
    h = -(pc * np.log2(pc) + (1 - pc) * np.log2(1 - pc))
    out[ok] = np.sign(p - 0.5) * (1.0 - h)
    return out


def energy_entropy(abs_return, *, window):
    """H_E = -sum_i e_i ln e_i / ln W, e_i = r_i^2 / sum_j r_j^2 over the last W bars."""
    rows = trailing_windows(abs_return, window) ** 2
    ok = np.all(np.isfinite(rows), axis=1)
    out = np.full(len(abs_return), np.nan)
    r = rows[ok]
    tot = r.sum(axis=1, keepdims=True)
    p = np.where(tot > 0, r / np.where(tot > 0, tot, 1.0), 1.0 / window)
    with np.errstate(divide="ignore", invalid="ignore"):
        h = -np.sum(np.where(p > 0, p * np.log(p), 0.0), axis=1)
    out[ok] = h / np.log(window)
    return out


def drift_information(log_return, *, window):
    """I_d = sign(mu) * n * D_KL(N(mu, s^2) || N(0, s^2)) = sign(mu) * n mu^2 / (2 s^2) nats."""
    rows = trailing_windows(log_return, window)
    ok = np.all(np.isfinite(rows), axis=1)
    out = np.full(len(log_return), np.nan)
    r = rows[ok]
    mu = r.mean(axis=1)
    s2 = r.var(axis=1, ddof=1)
    s2 = np.where(s2 > 0, s2, np.nan)
    val = np.sign(mu) * window * mu * mu / (2.0 * s2)
    out[ok] = np.where(np.isfinite(val), val, 0.0)
    return out


# --- rule --------------------------------------------------------------------------------------


def rule(s):
    x = s["sign_info"]
    h = s["energy_entropy"]
    d = s["drift_information"]
    T = len(h)
    rows = trailing_windows(h, L_REF)
    ok = np.all(np.isfinite(rows), axis=1)
    qhi = np.full(T, np.nan)
    qlo = np.full(T, np.nan)
    qhi[ok] = np.quantile(rows[ok], Q_HI, axis=1)
    qlo[ok] = np.quantile(rows[ok], Q_LO, axis=1)
    f = np.isfinite(qhi) & np.isfinite(x) & np.isfinite(d)
    up = d > D_MIN
    # enter: compressible down-run (reversion) OR diffuse energy with no up-run and positive drift info
    entry = (x < -THETA) | ((h > qhi) & (x < THETA) & up)
    # exit: compressible up-run (take profit) OR energy concentrates outside a down-run
    #       OR (no drift support and the run has turned up)
    exit_ = (x > X_TP) | ((h < qlo) & (x > -THETA)) | ((~up) & (x > 0))
    entry = np.where(f, entry.astype(float), np.nan)
    exit_ = np.where(f, exit_.astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="run_information_reversion",
    domain="information_theory",
    hypothesis=(
        "Daily return paths carry two kinds of exploitable information. (1) When the short up/down "
        "string becomes compressible (its binary entropy falls well below 1 bit) on the downside, the "
        "run tends to revert, so a long entered after a low-entropy down-run earns a reversal premium; "
        "a low-entropy up-run is the symmetric signal to take profit. (2) When the risk 'energy' "
        "(squared returns) is spread evenly across recent days (high energy entropy) the market is in a "
        "diffusive regime in which the risk premium is earned with shallow drawdowns, whereas a "
        "concentration of energy in few days signals shocks to step aside from. Holding through the "
        "diffusive regime is only worthwhile when the long-run return series carries positive "
        "information against a zero-drift model."
    ),
    definition=(
        "Let r_t be daily log returns.\n"
        "Run information (W_s = 10): p_t = (1/W_s) sum_{i<W_s} 1[r_{t-i} > 0], "
        "H2(p) = -p log2 p - (1-p) log2(1-p), x_t = sign(p_t - 1/2) (1 - H2(p_t)) in [-1, 1] bits.\n"
        "Energy entropy (W_e = 20): e_i = r_{t-i}^2 / sum_{j<W_e} r_{t-j}^2, "
        "h_t = -sum_i e_i ln e_i / ln W_e in [0, 1] (Shannon entropy of the energy distribution over "
        "time; its Renyi-2 counterpart is ln W_e - ln(sum r^4 / (sum r^2)^2 * W_e)).\n"
        "Drift information (n = 252): d_t = sign(mu) n D_KL(N(mu, s^2) || N(0, s^2)) = sign(mu) n mu^2 / "
        "(2 s^2) nats, mu and s^2 the sample mean and variance of the last n returns.\n"
        "Adaptive thresholds: q_hi, q_lo = 50% and 20% quantiles of h over the last 126 bars.\n"
        "Entry_t = [x_t < -0.1] OR ([h_t > q_hi] AND [x_t < 0.1] AND [d_t > 0]).\n"
        "Exit_t  = [x_t > 0.2] OR ([h_t < q_lo] AND [x_t > -0.1]) OR ([d_t <= 0] AND [x_t > 0]).\n"
        "Long from entry until exit (exit wins ties); the harness applies the one-bar delay and costs."
    ),
    references=(
        "Shannon, C. E. (1948). A Mathematical Theory of Communication. Bell System Technical Journal 27, 379-423, 623-656.",
        "Kullback, S. & Leibler, R. A. (1951). On Information and Sufficiency. Annals of Mathematical Statistics 22(1), 79-86.",
        "Cover, T. M. & Thomas, J. A. (2006). Elements of Information Theory, 2nd ed. Wiley.",
        "Renyi, A. (1961). On measures of entropy and information. Proc. Fourth Berkeley Symposium on Mathematical Statistics and Probability, Vol. 1, 547-561.",
        "Rosso, O. A., Blanco, S., Yordanova, J., Kolev, V., Figliola, A., Schurmann, M. & Basar, E. (2001). Wavelet entropy: a new tool for analysis of short duration brain electrical signals. Journal of Neuroscience Methods 105(1), 65-75.",
        "Risso, W. A. (2008). The informational efficiency and the financial crashes. Research in International Business and Finance 22(3), 396-408.",
        "Lehmann, B. N. (1990). Fads, Martingales, and Market Efficiency. Quarterly Journal of Economics 105(1), 1-28.",
    ),
    signals=(
        Signal("sign_info", sign_info, ("log_return",), {"window": Window(10)}, lambda window: window,
               "signed binary-entropy deficit of the up/down string (bits)"),
        Signal("energy_entropy", energy_entropy, ("abs_return",), {"window": Window(20)},
               lambda window: window, "normalised Shannon entropy of squared-return energy over time"),
        Signal("drift_information", drift_information, ("log_return",), {"window": LongWindow(252)},
               lambda window: window, "signed KL information against zero drift (nats)"),
    ),
    rule=rule,
    rule_lookback=L_REF,
    novelty=(
        "Uses information quantities as both the timing and the regime variables: low-entropy "
        "(compressible) sign runs are traded as reversal/take-profit events, while the entropy of the "
        "temporal energy distribution (a scale-free, kurtosis-like 'shock concentration' measure, "
        "applied in time rather than across wavelet scales) decides whether to hold between runs, and "
        "a KL drift-evidence term gates that holding leg. Thresholds are expressed in bits/nats or as "
        "rolling quantiles, so the rule transfers across assets without rescaling."
    ),
    limitations=(
        "Long-only: on assets without drift (most currency pairs) the holding leg adds little and results "
        "are near zero or negative. The 10-bar run statistic is coarse (p moves in steps of 0.1) and its "
        "reversal effect is strongest in equity indices; it may weaken in strongly trending markets or "
        "when daily autocorrelation turns positive. Turnover is moderate (about 7 round trips per year), "
        "so high-cost markets are penalised. Development results were noisy across nearby parameter "
        "settings (objective roughly 0.05-0.13), so the edge is modest. The 252-bar drift window adds a "
        "one-year warm-up."
    ),
)
