"""fmh_horizon_gap: Fractal Markets Hypothesis, scale-dependent Hurst exponents.

Long-only daily rule. The local Hurst exponent is estimated separately at short horizons
(1-3 days) and at long horizons (5-20 days) from the power-law scaling of the second-order
structure function of log prices. When the long-horizon exponent rises above the short-horizon
exponent by more than is usual for the market (the scaling law "breaks" and long horizons become
trend-dominated), the Fractal Markets Hypothesis says the horizon structure that provides
liquidity is failing; the strategy steps aside. Otherwise it is invested.
"""
import numpy as np

from strategy_api import Signal, Strategy, Window, rolling_quantile, trailing_windows

SHORT_SCALES = (1, 2, 3)
LONG_SCALES = (5, 10, 20)
MEDIAN_WINDOW = 126


def _structure_function(lp: np.ndarray, tau: int, w: int) -> np.ndarray:
    """S2(tau) = mean over the trailing w bars of (X_t - X_{t-tau})^2 (causal)."""
    d = np.full(len(lp), np.nan)
    d[tau:] = lp[tau:] - lp[:-tau]
    return np.mean(trailing_windows(d * d, w), axis=1)


def _hurst(lp: np.ndarray, taus: tuple, w: int) -> np.ndarray:
    """OLS slope of log S2(tau) on log tau, divided by 2 (= local Hurst exponent H)."""
    lt = np.log(np.asarray(taus, dtype=float))
    ls = np.vstack([np.log(_structure_function(lp, t, w) + 1e-300) for t in taus])
    ltc = lt - lt.mean()
    slope = (ltc[:, None] * (ls - ls.mean(axis=0))).sum(axis=0) / (ltc**2).sum()
    return slope / 2.0


def _windows(window: int) -> tuple:
    return (int(round(window * 2 / 3)), window, int(round(window * 1.5)))


def horizon_gap(log_price, *, window):
    """G_t = H_long - H_short, averaged over estimation windows (2/3 W, W, 3/2 W)."""
    lp = np.asarray(log_price, dtype=float)
    ws = _windows(window)
    out = np.zeros(len(lp))
    for w in ws:
        out = out + _hurst(lp, LONG_SCALES, w) - _hurst(lp, SHORT_SCALES, w)
    return out / len(ws)


HORIZON_GAP = Signal(
    name="horizon_gap",
    fn=horizon_gap,
    inputs=("log_price",),
    params={"window": Window(60)},
    lookback=lambda window: int(round(window * 1.5)) + max(LONG_SCALES),
    description="Long-horizon minus short-horizon local Hurst exponent (structure-function "
    "scaling), averaged over three estimation windows.",
)


def rule(signals):
    g = signals["horizon_gap"]
    med = rolling_quantile(g, MEDIAN_WINDOW, 0.5)
    ok = np.isfinite(med) & np.isfinite(g)
    entry = np.where(ok, (g < med).astype(float), np.nan)
    exit_ = np.where(ok, (g > med).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="fmh_horizon_gap",
    domain="fractal",
    hypothesis=(
        "Fractal Markets Hypothesis (Peters 1994; Kristoufek 2012, 2013): a market is stable "
        "when traders with many investment horizons coexist, so that price fluctuations obey a "
        "single scaling law across horizons. Turbulent, illiquid phases are marked by a breakdown "
        "of this self-similarity: the scaling exponent at long horizons rises relative to the one "
        "at short horizons (long-horizon moves become persistent, one-sided repricing while "
        "short-horizon dynamics are noisy/anti-persistent). A long-only holder should therefore "
        "be invested while the long-horizon Hurst exponent does not exceed the short-horizon one "
        "by more than is usual for that market, and step aside when the horizon gap is in the "
        "upper half of its recent distribution. This cuts exposure in regimes where drawdowns "
        "cluster while retaining exposure in balanced, multi-horizon (liquid) regimes."
    ),
    definition=(
        "Let X_t be the log price. Second-order structure function over a trailing window of w "
        "bars: S2(tau; t, w) = (1/w) * sum_{s=t-w+1..t} (X_s - X_{s-tau})^2. For self-affine "
        "(fBm-like) paths S2(tau) ~ c * tau^(2H). Local scale-restricted Hurst exponents are OLS "
        "slopes in log-log coordinates: H_short(t,w) = (1/2) * slope of log S2(tau) on log tau "
        "for tau in {1,2,3}; H_long(t,w) = (1/2) * slope for tau in {5,10,20}. Horizon gap: "
        "G_t = (1/3) * sum_{w in {2W/3, W, 3W/2}} [H_long(t,w) - H_short(t,w)], W = 60 "
        "(windows 40, 60, 90). Under a single scaling law (e.g. fBm with any H) G = 0 in "
        "expectation; G > 0 means a crossover to stronger persistence at long horizons. Rule: "
        "m_t = median of G over the trailing 126 bars; entry if G_t < m_t, exit if G_t > m_t. "
        "Lookback: 90 + 20 bars for G plus 126 for the median."
    ),
    references=(
        "Peters, E. E. (1994). Fractal Market Analysis: Applying Chaos Theory to Investment and "
        "Economics. John Wiley & Sons.",
        "Kristoufek, L. (2012). Fractal markets hypothesis and the global financial crisis: "
        "Scaling, investment horizons and liquidity. Advances in Complex Systems 15(6), 1250065.",
        "Kristoufek, L. (2013). Fractal markets hypothesis and the global financial crisis: "
        "Wavelet power evidence. Scientific Reports 3, 2857.",
        "Di Matteo, T., Aste, T., Dacorogna, M. M. (2005). Long-term memories of developed and "
        "emerging markets: Using the scaling analysis to characterize their stage of "
        "development. Journal of Banking & Finance 29(4), 827-851.",
        "Mandelbrot, B. B., Van Ness, J. W. (1968). Fractional Brownian motions, fractional "
        "noises and applications. SIAM Review 10(4), 422-437.",
    ),
    signals=(HORIZON_GAP,),
    rule=rule,
    rule_lookback=MEDIAN_WINDOW,
    novelty=(
        "Unlike the earlier strategies, which use a single roughness or memory number (Higuchi "
        "fractal dimension, one Hurst exponent combined with the latest move, a pointwise "
        "Hoelder exponent), this rule uses the scale dependence of the Hurst exponent itself: "
        "the crossover between short- and long-horizon scaling regimes that the Fractal Markets "
        "Hypothesis links to the investment-horizon structure and liquidity of a market. It uses "
        "no price direction and no trend or volatility level, only the shape of the "
        "multi-horizon scaling law."
    ),
    limitations=(
        "Scale-restricted Hurst exponents from 40-90 bar windows are noisy (especially at "
        "tau = 20), so the signal is a weak, statistical regime filter; on development data "
        "results were sensitive to the estimation window, which is why three windows are "
        "averaged. The rule is invested about half the time, so in steadily trending bull "
        "markets it gives up drift. Currency pairs with no drift gain little. The raw (not "
        "demeaned) structure function lets strong drift raise H_long, so the gap partly reflects "
        "one-sided trends as well as memory. Trade frequency is about 3-7 round trips per year; "
        "costs matter on expensive instruments."
    ),
)
