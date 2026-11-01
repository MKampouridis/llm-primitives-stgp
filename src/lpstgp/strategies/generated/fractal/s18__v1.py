"""fbm_increment_forecast: long-only timing from the fractional-Brownian-motion increment
correlation rho(H) = 2^(2H-1) - 1, with H from a null-corrected rolling DFA."""

from __future__ import annotations

import numpy as np

from strategy_api import LongWindow, Signal, Strategy, Window, trailing_windows

# --- detrended fluctuation analysis (DFA-1) with exact white-noise bias correction ---------------


def _dfa_scales(w: int) -> np.ndarray:
    """Six log-spaced box sizes from 4 to w/4."""
    return np.unique(np.round(np.geomspace(4, max(8, w // 4), 6)).astype(int))


def _detrend_mats(scales):
    """Residual-maker matrices I - X(X'X)^-1 X' for a linear fit inside a box of size n."""
    mats = {}
    for n in scales:
        x = np.vstack([np.ones(n), np.arange(n, dtype=float)]).T
        mats[int(n)] = np.eye(n) - x @ np.linalg.pinv(x)
    return mats


def _null_logf(w, scales, mats):
    """Exact log E[F^2(n)]^(1/2) of the same DFA procedure applied to i.i.d. unit-variance noise
    (window-demeaned, cumulated, boxed from the end, linearly detrended)."""
    c = np.tril(np.ones((w, w)))
    d = np.eye(w) - np.ones((w, w)) / w
    sy = c @ d @ c.T  # covariance of the profile under the null
    out = []
    for n in scales:
        k = w // n
        o = w - k * n
        m = mats[int(n)]
        tot = 0.0
        for j in range(k):
            a = o + j * n
            tot += np.trace(m @ sy[a : a + n, a : a + n] @ m.T)
        out.append(0.5 * np.log(tot / (k * n)))
    return np.array(out)


def _dfa_rolling(x: np.ndarray, w: int) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), np.nan)
    scales = _dfa_scales(w)
    mats = _detrend_mats(scales)
    ls = np.log(scales.astype(float))
    null_excess = _null_logf(w, scales, mats) - 0.5 * ls  # finite-size deviation from n^0.5
    for t in range(w - 1, len(x)):
        seg = x[t - w + 1 : t + 1]
        if not np.all(np.isfinite(seg)):
            continue
        y = np.cumsum(seg - seg.mean())
        lf = np.empty(len(scales))
        ok = True
        for i, n in enumerate(scales):
            k = w // n
            r = y[w - k * n :].reshape(k, n) @ mats[int(n)].T
            f = np.sqrt(np.mean(r * r))
            if not f > 0:
                ok = False
                break
            lf[i] = np.log(f)
        if ok:
            out[t] = np.polyfit(ls, lf - null_excess, 1)[0]
    return out


def dfa_hurst(log_return, *, window):
    """Bias-corrected DFA-1 Hurst exponent of the last `window` daily log returns."""
    return _dfa_rolling(log_return, window)


def drift_z(log_return, *, window):
    """Standardised last-`window`-bar increment: sum(r) / (sd(r) * sqrt(window))."""
    rows = trailing_windows(log_return, window)
    s = rows.sum(axis=1)
    sd = rows.std(axis=1, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = s / (sd * np.sqrt(window))
    z[~np.isfinite(z)] = np.nan
    return z


# --- rule ------------------------------------------------------------------------------------------

K_IN = 0.05  # enter when the standardised fBm forecast exceeds +0.05
K_OUT = 0.10  # exit when it falls below -0.10 (asymmetric dead band against churning)


def rule(sig):
    h = np.clip(sig["dfa_hurst"], 0.05, 0.95)
    z = sig["drift_z"]
    ok = np.isfinite(h) & np.isfinite(z)
    rho = 2.0 ** (2.0 * h - 1.0) - 1.0  # corr. of adjacent equal-length fBm increments
    f = rho * z  # E[next increment | last increment] in units of increment s.d.
    entry = np.where(ok, (f > K_IN).astype(float), np.nan)
    exit_ = np.where(ok, (f < -K_OUT).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="fbm_increment_forecast",
    domain="fractal",
    hypothesis=(
        "If log prices behave locally like fractional Brownian motion with Hurst exponent H, then "
        "two adjacent price moves over equal horizons have correlation rho(H) = 2^(2H-1) - 1. By "
        "self-similarity this holds at every horizon. So the local H, together with the latest "
        "move, gives a conditional forecast of the next move. In persistent regimes (H > 1/2) "
        "moves tend to continue; in anti-persistent regimes (H < 1/2) they tend to reverse; near "
        "H = 1/2 the past carries no information. A long-only holder should buy when this forecast "
        "is clearly positive (a persistent advance, or a sell-off in an anti-persistent market), "
        "sell when it is clearly negative (a persistent decline, or a rally in an anti-persistent "
        "market), and otherwise keep the current position. The rule therefore follows trends or "
        "fades them depending on the measured memory of the market, rather than holding a fixed "
        "momentum or reversal bias."
    ),
    definition=(
        "Inputs: daily log returns r_t. "
        "(1) Hurst exponent by DFA-1 on the last W=120 returns: profile y_i = sum_{j<=i}(r_j - "
        "mean(r)); for box sizes n in {4,6,9,13,20,30} (log-spaced, 4..W/4), cut the profile "
        "into floor(W/n) non-overlapping boxes aligned to the latest bar. Remove a least-squares "
        "line from each box and take F(n) = sqrt(mean of squared residuals). Finite-size "
        "correction: F0(n) is the exact expected DFA fluctuation of i.i.d. unit noise under the "
        "same procedure, F0(n)^2 = sum_k tr(M_n S_k M_n') / (K n), where S = C D C' is the "
        "null covariance of the profile (C lower-triangular ones, D = I - 11'/W) and M_n = I - "
        "X(X'X)^-1X'. H_t is the OLS slope of log F(n) - [log F0(n) - 0.5 log n] on log n, "
        "so white noise gives H = 0.5 without small-sample bias. H is clipped to [0.05, 0.95]. "
        "(2) Standardised last move over L=40 bars: z_t = sum_{i=t-L+1..t} r_i / (s_t sqrt(L)), "
        "where s_t is the sample s.d. of those L returns. "
        "(3) fBm conditional forecast: for fBm, Corr(X(t+L)-X(t), X(t)-X(t-L)) = 2^(2H-1) - 1 =: "
        "rho(H), so the standardised forecast is f_t = rho(H_t) * z_t. "
        "Rule: entry if f_t > 0.05; exit if f_t < -0.10; otherwise no action (hysteresis). "
        "Lookback 121 bars."
    ),
    references=(
        "Mandelbrot, B. B. and Van Ness, J. W. (1968). Fractional Brownian motions, fractional "
        "noises and applications. SIAM Review 10(4), 422-437.",
        "Peng, C.-K., Buldyrev, S. V., Havlin, S., Simons, M., Stanley, H. E. and Goldberger, "
        "A. L. (1994). Mosaic organization of DNA nucleotides. Physical Review E 49, 1685-1689.",
        "Kantelhardt, J. W., Koscielny-Bunde, E., Rego, H. H. A., Havlin, S. and Bunde, A. (2001). "
        "Detecting long-range correlations with detrended fluctuation analysis. Physica A 295, "
        "441-454.",
        "Hu, K., Ivanov, P. Ch., Chen, Z., Carpena, P. and Stanley, H. E. (2001). Effect of trends "
        "on detrended fluctuation analysis. Physical Review E 64, 011114.",
        "Peters, E. E. (1994). Fractal Market Analysis: Applying Chaos Theory to Investment and "
        "Economics. Wiley.",
        "Kristoufek, L. (2012). Fractal markets hypothesis and the global financial crisis: "
        "scaling, investment horizons and liquidity. Advances in Complex Systems 15(6), 1250065.",
    ),
    signals=(
        Signal(
            "dfa_hurst",
            dfa_hurst,
            ("log_return",),
            {"window": LongWindow(120)},
            lambda window: window + 1,
            "null-corrected DFA-1 Hurst exponent of daily log returns",
        ),
        Signal(
            "drift_z",
            drift_z,
            ("log_return",),
            {"window": Window(40)},
            lambda window: window + 1,
            "standardised cumulative return over the last `window` bars",
        ),
    ),
    rule=rule,
    rule_lookback=0,
    novelty=(
        "The earlier higuchi_smooth_path_filter uses path roughness (D = 2 - H) as a direction-"
        "blind stress filter: it stays in when the path is smooth. This strategy uses a different "
        "piece of mathematics: the exact covariance of fractional Gaussian noise, in which the sign "
        "of H - 1/2 decides whether the latest move should be extrapolated or reversed. Its "
        "decisions depend on the direction of the move, so the same H leads to opposite actions "
        "after a rise and after a fall, and an anti-persistent market can be a reason to buy. The "
        "DFA exponent is corrected with the exact finite-window white-noise expectation of the "
        "fluctuation function, so that the threshold H = 1/2 is meaningful in 120-bar windows; "
        "without the correction raw DFA is biased upward. In development, an ablation without the "
        "Hurst term (plain sign of the 60-day drift) scored clearly worse than the H-conditioned "
        "versions."
    ),
    limitations=(
        "A 120-bar DFA estimate of H is noisy (sampling s.d. of roughly 0.05-0.08), and rho(H) is "
        "small near H = 1/2, so the forecast often sits inside the dead band and positions can "
        "last a long time. On low-volatility currency pairs the number of round trips is only "
        "about 3 per year, close to the 2-per-year minimum. The fBm model assumes stationary "
        "Gaussian increments and ignores volatility clustering and fat tails. A volatility spike "
        "inflates s_t and shrinks z_t, which can delay exits in fast crashes. Results in "
        "development were sensitive to the drift horizon (L = 20/30/40/60 gave objectives of "
        "about -0.08/-0.02/+0.08/+0.01), and the median edge is small. Long-only exposure to "
        "driftless FX pairs still suffers drawdowns of about 0.3-0.5 annual sigma per six months. "
        "Equity bear phases are only partly avoided."
    ),
)
