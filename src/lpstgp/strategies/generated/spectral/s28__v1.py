"""long_memory_scaled_dip: buy short-term dips with a depth requirement set by the
low-frequency spectral memory parameter d (multitaper GPH log-periodogram regression)."""
from __future__ import annotations

import numpy as np

from strategy_api import Kmax, LongWindow, Signal, Strategy, Window, trailing_windows

NTAPERS = 3  # number of sine tapers in the multitaper spectrum estimate
SLOPE = 5.0  # sensitivity of the dip threshold to the memory parameter d
BASE = -0.5  # dip threshold (in sigma units) for white-noise returns (d = 0)
EXIT = 0.5  # exit once the 10-day standardized move has overshot to +0.5 sigma


def _gph_d(log_return, *, window, band):
    """Multitaper GPH estimate of the fractional memory parameter d of daily returns
    over the trailing `window` bars, using the m lowest Fourier frequencies."""
    x = np.asarray(log_return, dtype=np.float64)
    rows = trailing_windows(x, window)
    out = np.full(len(x), np.nan)
    ok = np.all(np.isfinite(rows), axis=1)
    if not ok.any():
        return out
    m = int(round(np.sqrt(window) * band / 8.0 * 1.25))  # band 8, N 252 -> m = 20
    r = rows[ok] - rows[ok].mean(axis=1, keepdims=True)
    tt = np.arange(1, window + 1)
    spec = np.zeros((r.shape[0], window // 2 + 1))
    for j in range(1, NTAPERS + 1):
        taper = np.sqrt(2.0 / (window + 1)) * np.sin(np.pi * j * tt / (window + 1))
        spec += np.abs(np.fft.rfft(r * taper, axis=1)) ** 2
    spec /= NTAPERS
    k = np.arange(1, m + 1)
    lam = 2.0 * np.pi * k / window
    reg = -np.log(4.0 * np.sin(lam / 2.0) ** 2)
    rc = reg - reg.mean()
    ls = np.log(spec[:, k] + 1e-30)
    out[ok] = (ls - ls.mean(axis=1, keepdims=True)) @ rc / (rc @ rc)
    return out


def _dip(log_return, *, window, vol_window):
    """Standardized `window`-day log return: sum of returns / (sigma_vol_window * sqrt(window))."""
    x = np.asarray(log_return, float)
    s = np.std(trailing_windows(x, vol_window), axis=1, ddof=1)
    short = trailing_windows(x, window).sum(axis=1)
    return short / (s * np.sqrt(window) + 1e-12)


d_sig = Signal(
    "gph_d", _gph_d, ("log_return",),
    {"window": LongWindow(252), "band": Kmax(8)},
    lambda window, band: window,
    description="multitaper log-periodogram (GPH) estimate of the memory parameter d of returns",
)
dip_sig = Signal(
    "dip_z", _dip, ("log_return",),
    {"window": Window(10), "vol_window": LongWindow(120)},
    lambda window, vol_window: max(window, vol_window),
    description="10-day log return in units of its white-noise standard deviation",
)


def rule(s):
    d = s["gph_d"]
    z = s["dip_z"]
    nan = ~(np.isfinite(d) & np.isfinite(z))
    entry = (z < BASE - SLOPE * d).astype(float)
    exit_ = (z > EXIT).astype(float)
    entry[nan] = np.nan
    exit_[nan] = np.nan
    return entry, exit_


STRATEGY = Strategy(
    name="long_memory_scaled_dip",
    domain="spectral",
    hypothesis=(
        "The behaviour of the return spectrum near frequency zero shows whether multi-week price "
        "moves tend to persist or to revert. If the low-frequency spectrum of daily returns falls "
        "towards zero frequency (memory parameter d < 0, anti-persistent returns, so the price "
        "mean-reverts at horizons of weeks), a short-term decline is likely to be partly undone, "
        "and even a modest dip is worth buying. If the spectrum rises towards zero frequency "
        "(d > 0, persistent returns), declines tend to continue, and only an unusually deep, "
        "capitulation-like dip should be bought. Making the required dip depth a continuous "
        "function of d, instead of an on/off regime switch, keeps the strategy active in every "
        "regime. It buys reversion where the spectrum supports it and avoids catching falling "
        "knives where the spectrum indicates persistence. Holding until a modest overshoot "
        "(+0.5 sigma) captures the rebound plus the asset's drift while being flat roughly half "
        "the time."
    ),
    definition=(
        "Let r_t be daily log returns. (1) Memory parameter: over the last N=252 returns "
        "(demeaned), compute the sine-multitaper spectrum S(l_k) = (1/K) sum_{j=1..K} "
        "|sum_t h_j(t) r_t exp(-i l_k t)|^2 with K=3 sine tapers h_j(t)=sqrt(2/(N+1)) "
        "sin(pi j t/(N+1)) and Fourier frequencies l_k = 2 pi k/N. Using the m=20 lowest "
        "frequencies (k=1..m, periods of about 12.6 to 252 days; m = round(1.25 sqrt(N))), "
        "estimate d by the Geweke-Porter-Hudak log-periodogram regression "
        "log S(l_k) = c + d * X_k + e_k, with X_k = -log(4 sin^2(l_k/2)), so that S(l) ~ l^(-2d) "
        "near zero (d = OLS slope). (2) Dip: z_t = (r_{t-9}+...+r_t) / (sigma_t sqrt(10)), where "
        "sigma_t is the sample standard deviation of the last 120 returns. (3) Rule: entry when "
        "z_t < -0.5 - 5 d_t (white noise d=0: dip below -0.5 sigma; anti-persistent d=-0.1: any "
        "negative 10-day move; persistent d=+0.1: dip below -1 sigma). Exit when z_t > +0.5. Long "
        "only, flat otherwise. Total lookback is 252 bars."
    ),
    references=(
        "Geweke, J. and Porter-Hudak, S. (1983). The estimation and application of long memory "
        "time series models. Journal of Time Series Analysis 4(4), 221-238.",
        "Robinson, P. M. (1995). Log-periodogram regression of time series with long range "
        "dependence. Annals of Statistics 23(3), 1048-1072.",
        "Riedel, K. S. and Sidorenko, A. (1995). Minimum bias multiple taper spectral estimation. "
        "IEEE Transactions on Signal Processing 43(1), 188-195.",
        "Velasco, C. (1999). Non-stationary log-periodogram regression. Journal of Econometrics "
        "91(2), 325-371.",
        "Hosking, J. R. M. (1981). Fractional differencing. Biometrika 68(1), 165-176.",
        "Percival, D. B. and Walden, A. T. (1993). Spectral Analysis for Physical Applications: "
        "Multitaper and Conventional Univariate Techniques. Cambridge University Press.",
        "Lo, A. W. and MacKinlay, A. C. (1988). Stock market prices do not follow random walks: "
        "evidence from a simple specification test. Review of Financial Studies 1(1), 41-66.",
    ),
    signals=(d_sig, dip_sig),
    rule=rule,
    rule_lookback=0,
    novelty=(
        "The earlier spectral strategies use the leading SSA component as a reversion anchor, "
        "the phase of the fundamental Fourier mode of a Brownian-bridge residual, or the spectral "
        "entropy (flatness) of the whole spectrum. This strategy instead uses the low-frequency "
        "power-law exponent of the return spectrum: the fractional memory parameter d, estimated "
        "by multitaper GPH log-periodogram regression. d does not decide whether to trade. It "
        "continuously sets how deep a short-term dip has to be before buying, so the spectral "
        "shape near zero frequency becomes a horizon-matched oversold threshold. No price anchor, "
        "phase or entropy is involved."
    ),
    limitations=(
        "The GPH estimate from 252 bars and 20 frequencies is noisy (standard error about 0.07 to "
        "0.1 with 3 tapers), so the threshold modulation is partly random. The linear map from d "
        "to the threshold (base -0.5, slope 5) is heuristic, not derived from a forecast model. "
        "The strategy relies on short-horizon reversion plus drift. On currency pairs without "
        "drift it was roughly break-even to slightly negative in development (negative F on most "
        "FX pairs), and on indices in persistent bear phases it keeps buying dips that fail. Its "
        "turnover is fairly high (about 15 to 25 one-way trades a year on equities), so it is "
        "sensitive to costs. Development objective: -0.04 (median F over 21 instruments); mean F "
        "+0.05. Neighbouring parameter settings scored between -0.13 and -0.04."
    ),
)
