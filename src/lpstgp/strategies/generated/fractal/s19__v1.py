"""holder_singularity_rebound: buy price drops that are *singular* (low pointwise Hoelder exponent).

A long-only daily strategy from fractal analysis. The pointwise Hoelder exponent alpha(t) of the
log-price path at the latest bar is estimated from the scaling of the path's oscillation over
the trailing scales tau = 1..kmax. A drop with low alpha is a singularity, i.e. an abrupt,
jump-like break concentrated at the current point. A drop with alpha near or above 1/2 is regular
and diffusive. The strategy buys singular drops, then exits when the dip has fully reverted or
after a time stop.
"""
from __future__ import annotations

import numpy as np

from strategy_api import (
    Kmax,
    Signal,
    Strategy,
    Window,
    rolling_std,
    trailing_windows,
)

# --- signals -------------------------------------------------------------------------------------


def holder_now(log_price, *, kmax):
    """Pointwise Hoelder exponent of the log-price path at bar t (oscillation method).

    osc_tau(t) = max(x[t-tau..t]) - min(x[t-tau..t]),  tau = 1..kmax
    alpha(t)   = OLS slope of log osc_tau(t) on log tau.
    """
    lp = np.asarray(log_price, dtype=np.float64)
    rows = trailing_windows(lp, kmax + 1)  # x_{t-kmax} .. x_t
    taus = np.arange(1, kmax + 1)
    logosc = []
    for tau in taus:
        seg = rows[:, kmax - tau:]
        osc = np.max(seg, axis=1) - np.min(seg, axis=1)
        logosc.append(np.log(np.maximum(osc, 1e-12)))
    L = np.vstack(logosc)
    lt = np.log(taus.astype(float))
    lt = lt - lt.mean()
    alpha = (lt[:, None] * (L - L.mean(axis=0))).sum(axis=0) / np.sum(lt * lt)
    alpha[:kmax] = np.nan
    return alpha


def drop_z(log_price, log_return, *, horizon, vol_window):
    """Depth of the current dip below the trailing `horizon`-bar high, in diffusive units:
    z(t) = (x_t - max x[t-h..t]) / (sigma_t * sqrt(h)), sigma_t = std of the last vol_window
    daily log returns. z = 0 means the price is at its h-bar high."""
    lp = np.asarray(log_price, dtype=np.float64)
    rows = trailing_windows(lp, horizon + 1)
    dd = lp - np.max(rows, axis=1)
    sd = rolling_std(np.asarray(log_return, dtype=np.float64), vol_window)
    return dd / (sd * np.sqrt(horizon))


SIG_HOLDER = Signal(
    name="holder_now",
    fn=holder_now,
    inputs=("log_price",),
    params={"kmax": Kmax(10)},
    lookback=lambda kmax: int(kmax + 1),
    description="pointwise Hoelder exponent of the log-price path at the latest bar",
)
SIG_DROP = Signal(
    name="drop_z",
    fn=drop_z,
    inputs=("log_price", "log_return"),
    params={"horizon": Window(10), "vol_window": Window(20)},
    lookback=lambda horizon, vol_window: int(max(horizon + 1, vol_window)),
    description="volatility-scaled depth below the trailing high",
)

# --- rule ----------------------------------------------------------------------------------------

ALPHA_SINGULAR = 0.35  # below the Brownian value 1/2: the move is a singularity
DROP_Z_ENTRY = -0.5  # the path is in a dip of at least half a diffusive unit
HOLD = 30  # time stop: bars after the last singular-drop event


def rule(s):
    a = s["holder_now"]
    z = s["drop_z"]
    ok = np.isfinite(a) & np.isfinite(z)
    event = ok & (a < ALPHA_SINGULAR) & (z < DROP_Z_ENTRY)
    entry = np.where(ok, event.astype(float), np.nan)

    ev = event.astype(float)
    n = len(ev)
    recent = np.zeros(n)
    for k in range(HOLD):
        sh = np.zeros(n)
        sh[k:] = ev[: n - k] if k > 0 else ev
        recent = np.maximum(recent, sh)
    reverted = z >= 0.0  # back at the trailing high: the singular dip has healed
    exit_ = np.where(ok, ((recent == 0) | reverted).astype(float), np.nan)
    return entry, exit_


# --- strategy ------------------------------------------------------------------------------------

STRATEGY = Strategy(
    name="holder_singularity_rebound",
    domain="fractal",
    hypothesis=(
        "Price drops differ in their local regularity. A drop concentrated in an abrupt, "
        "jump-like break at the current point is a singularity of the price path, with a "
        "pointwise Hoelder exponent well below the Brownian value 1/2. Such breaks are "
        "typically liquidity or overreaction shocks, and they tend to revert. A drop that "
        "unfolds regularly, with alpha near or above 1/2, is a diffusive or trending repricing "
        "and carries no such rebound premium. A long-only holder should therefore buy only "
        "singular drops, stay invested while the dip heals, and step aside once the price has "
        "regained its pre-shock high or the shock has aged. This keeps exposure low in "
        "driftless markets while capturing the rebound premium where it exists."
    ),
    definition=(
        "x_t = log price. Pointwise Hoelder exponent at bar t (oscillation method): "
        "osc_tau(t) = max_{t-tau<=s<=t} x_s - min_{t-tau<=s<=t} x_s for tau = 1..K (K = 10). "
        "Since osc_tau(t) ~ C tau^{alpha(t)}, estimate alpha(t) as the OLS slope of "
        "log osc_tau(t) on log tau. For Brownian motion alpha = 1/2. For a smooth trend "
        "alpha -> 1. For a jump at t, osc_tau ~ const and alpha -> 0. "
        "Dip depth in diffusive units: z_t = (x_t - max_{t-h<=s<=t} x_s) / (sigma_t sqrt(h)), "
        "with h = 10 and sigma_t the sample std of the last 20 daily log returns. "
        "Event E_t = 1{alpha(t) < 0.35 and z_t < -0.5}. Entry condition: E_t. Exit condition: "
        "(no event in bars t-29..t) or z_t >= 0 (price back at its 10-bar high). The harness "
        "holds the long position from entry to exit."
    ),
    references=(
        "Mandelbrot, B. B. (1997). Fractals and Scaling in Finance: Discontinuity, "
        "Concentration, Risk. Springer.",
        "Mallat, S., & Hwang, W. L. (1992). Singularity detection and processing with wavelets. "
        "IEEE Transactions on Information Theory, 38(2), 617-643.",
        "Dubuc, B., Quiniou, J. F., Roques-Carmes, C., Tricot, C., & Zucker, S. W. (1989). "
        "Evaluating the fractal dimension of profiles. Physical Review A, 39(3), 1500-1512.",
        "Peltier, R.-F., & Levy Vehel, J. (1995). Multifractional Brownian motion: definition "
        "and preliminary results. INRIA Research Report RR-2645.",
        "Struzik, Z. R. (2000). Determining local singularity strengths and their spectra with "
        "the wavelet transform. Fractals, 8(2), 163-179.",
        "Bianchi, S., Pantanella, A., & Pianese, A. (2013). Modeling stock prices by "
        "multifractional Brownian motion: an improved estimation of the pointwise regularity. "
        "Quantitative Finance, 13(8), 1317-1330.",
    ),
    signals=(SIG_HOLDER, SIG_DROP),
    rule=rule,
    rule_lookback=HOLD,
    novelty=(
        "The strategy uses the pointwise (local) Hoelder exponent at the current bar, the "
        "quantity of multifractional and multifractal singularity analysis. It uses it as an "
        "event classifier for the type of a drawdown, not as a regime level. "
        "higuchi_smooth_path_filter averages roughness (fractal dimension D) over a window and "
        "filters regimes. fbm_increment_forecast uses a window-global Hurst exponent and the "
        "fBm increment correlation 2^(2H-1) - 1 to forecast the next move. Here the regularity "
        "of the latest point decides whether a dip is a transient singular shock, which is "
        "bought, or a regular diffusive decline, which is ignored. The exit is tied to the "
        "healing of the singularity, i.e. a return to the pre-shock high. In development "
        "tests the Hoelder condition was essential. Without it the same dip rule became "
        "almost always-long and scored about -0.01 instead of about +0.26."
    ),
    limitations=(
        "The Hoelder estimate uses only K = 10 trailing points. It is noisy and is driven "
        "mostly by how much of the 10-day range sits in the last few bars. Results were "
        "sensitive to the absolute alpha threshold: on development data, 0.30 / 0.35 / 0.40 "
        "gave objectives of about 0.10 / 0.26 / -0.03, so out-of-sample performance should "
        "be expected to be lower. The rebound premium is a short-horizon reversal effect. It "
        "can fail in sustained crashes made of repeated jumps, where the 30-bar time stop is "
        "the only protection, and in markets with genuine price gaps from news. The strategy "
        "is long-only and holds about 35-45% of the time. Turnover is about 12-18 one-way "
        "trades per year, so costs matter for expensive instruments. The time stop and the "
        "recovery exit are rule choices, not consequences of the fractal theory."
    ),
)
