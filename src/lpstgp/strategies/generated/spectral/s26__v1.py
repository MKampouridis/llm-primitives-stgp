"""bridge_fourier_phase: long-only timing from the phase of the fundamental Fourier
component of the bridge-detrended log price over a trailing window."""

import numpy as np

from strategy_api import Signal, Strategy, Window, trailing_windows


def _fundamental_phase(log_price, n):
    """cos and sin of the phase, at the last bar, of the fundamental (k = 1) DFT component of
    the trailing n-bar log price after removing the chord joining its two end points."""
    rows = trailing_windows(log_price, n)
    cs = np.full(len(rows), np.nan)
    sn = np.full(len(rows), np.nan)
    ok = np.all(np.isfinite(rows), axis=1)
    if not ok.any():
        return cs, sn
    x = rows[ok]
    t = np.arange(n)
    chord = x[:, :1] + (x[:, -1:] - x[:, :1]) * (t / (n - 1))
    y = x - chord                       # bridge: y_0 = y_{n-1} = 0, periodic extension continuous
    X1 = np.fft.rfft(y, axis=1)[:, 1]   # fundamental coefficient, period = n bars
    theta = np.angle(X1) + 2.0 * np.pi * (n - 1) / n   # phase of the k=1 cosine at the last bar
    cs[ok] = np.cos(theta)
    sn[ok] = np.sin(theta)
    return cs, sn


def _cycle_cos(log_price, *, window):
    return _fundamental_phase(log_price, window)[0]


def _cycle_sin(log_price, *, window):
    return _fundamental_phase(log_price, window)[1]


CYCLE_COS = Signal(
    name="cycle_cos",
    fn=_cycle_cos,
    inputs=("log_price",),
    params={"window": Window(60)},
    lookback=lambda window: window,
    description="cos(theta_t): position of the bar on the fundamental cycle (-1 trough, +1 peak)",
)
CYCLE_SIN = Signal(
    name="cycle_sin",
    fn=_cycle_sin,
    inputs=("log_price",),
    params={"window": Window(60)},
    lookback=lambda window: window,
    description="sin(theta_t): direction on the fundamental cycle (< 0 rising, > 0 falling)",
)


def rule(signals):
    c = signals["cycle_cos"]
    s = signals["cycle_sin"]
    unknown = ~(np.isfinite(c) & np.isfinite(s))
    entry = ((c < 0) & (s < 0)).astype(float)   # theta in (pi, 3pi/2): just past the trough, rising
    exit_ = ((c > 0) & (s > 0)).astype(float)   # theta in (0, pi/2): just past the peak, falling
    entry[unknown] = np.nan
    exit_[unknown] = np.nan
    return entry, exit_


STRATEGY = Strategy(
    name="bridge_fourier_phase",
    domain="spectral",
    hypothesis=(
        "Over a window of about one quarter (60 trading days), the log price moves as a "
        "drift plus a slow swing around that drift. The fundamental Fourier component of the "
        "drift-free part of the window (the Brownian-bridge residual) summarises the swing, "
        "and its phase at the last bar shows where on the swing the price now is. Buying just "
        "after the swing has turned up from its trough and selling just after it has turned "
        "down from its peak captures the rising half of the oscillation. Being out of the "
        "market for about half the time, mostly during falling phases, also cuts drawdowns "
        "compared with buy and hold."
    ),
    definition=(
        "For each bar t take the last n = 60 log prices x_0..x_{n-1} (x_{n-1} = log price at t). "
        "Remove the chord through the two end points: y_j = x_j - [x_0 + (x_{n-1} - x_0) j/(n-1)], "
        "so y_0 = y_{n-1} = 0 (Brownian-bridge detrending, which avoids the end-point jump that "
        "would otherwise leak into all frequencies of the DFT). Fundamental DFT coefficient: "
        "X_1 = sum_j y_j exp(-2 pi i j / n), with amplitude |X_1| and phase arg X_1. The k=1 "
        "harmonic is (2/n)|X_1| cos(2 pi j/n + arg X_1); its phase at the last sample is "
        "theta_t = arg X_1 + 2 pi (n-1)/n. Signals: cycle_cos = cos theta_t, cycle_sin = "
        "sin theta_t. Rule: entry when cos theta_t < 0 and sin theta_t < 0 (theta in (pi, 3pi/2): "
        "past the trough, harmonic rising); exit when cos theta_t > 0 and sin theta_t > 0 "
        "(theta in (0, pi/2): past the peak, harmonic falling). The two quadrants are not "
        "adjacent, which gives hysteresis; the position is otherwise held. Lookback: 60 bars."
    ),
    references=(
        "Granger, C.W.J. and Morgenstern, O. (1963). Spectral analysis of New York stock market "
        "prices. Kyklos 16(1), 1-27.",
        "Priestley, M.B. (1981). Spectral Analysis and Time Series. Academic Press, London.",
        "Percival, D.B. and Walden, A.T. (1993). Spectral Analysis for Physical Applications: "
        "Multitaper and Conventional Univariate Techniques. Cambridge University Press.",
        "Poterba, J.M. and Summers, L.H. (1988). Mean reversion in stock prices: evidence and "
        "implications. Journal of Financial Economics 22(1), 27-59.",
        "Ehlers, J.F. (2001). Rocket Science for Traders: Digital Signal Processing Applications. "
        "Wiley, New York.",
    ),
    signals=(CYCLE_COS, CYCLE_SIN),
    rule=rule,
    rule_lookback=0,
    novelty=(
        "This rule trades on the phase of one Fourier harmonic, not on the size of a deviation. "
        "ssa_residual_reversion measures how far the price sits below a data-adaptive SSA trend "
        "(an eigen-decomposition of the trajectory matrix) and trades that excursion against a "
        "threshold. Here the trend is the fixed end-point chord, the decomposition is the fixed "
        "Fourier basis, and the decision depends only on the angle of the fundamental component "
        "(where the bar sits on the cycle and which way it is moving). There is no amplitude "
        "threshold, so the rule is scale-free across assets and volatility regimes. Exits happen "
        "after the cycle peak, not on a positive overshoot."
    ),
    limitations=(
        "The phase of a single harmonic is a noisy estimate, and results depend clearly on the "
        "window: on the development data, 60 bars scored about 0.30, 90 bars about 0.12 and 40 "
        "bars was negative. Under a pure random walk the phase carries no information, so the "
        "edge depends on real quarter-scale oscillations. The rule ignores the chord slope, so "
        "it keeps buying troughs during persistent bear markets (weak equity segments late in "
        "the sample). With a 60-bar window it enters about four times a year, so trading costs "
        "and the 2-entries-per-year minimum matter for longer windows. It does worst on some "
        "currency pairs with no drift."
    ),
)
