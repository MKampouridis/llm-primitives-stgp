"""Hyperbolic dislocation reversal.

Long-only daily strategy built on the Fisher-Rao (hyperbolic) geometry of the univariate
Gaussian manifold of returns. A short-window return model that has moved far from the
long-window model along a geodesic, in the direction of lower drift, is a "dislocation";
if the move is not a volatility-regime break (the scale component of the displacement is
bounded), the dislocation tends to relax and the strategy holds a long position until
the drift side of the displacement has closed.
"""

from __future__ import annotations

import numpy as np

from strategy_api import LongWindow, Signal, Strategy, Window, trailing_windows

# --- information geometry of N(mu, sigma^2) -------------------------------------------------


def _gauss(x: np.ndarray, w: int) -> tuple[np.ndarray, np.ndarray]:
    """Maximum-likelihood-type Gaussian fit (mean, sample sd) on each trailing window."""
    r = trailing_windows(x, w)
    return r.mean(axis=1), np.maximum(r.std(axis=1, ddof=1), 1e-8)


def _fisher_rao(mu1, s1, mu2, s2):
    """Closed-form Fisher-Rao geodesic distance between N(mu1,s1^2) and N(mu2,s2^2).

    The Fisher metric ds^2 = (dmu^2 + 2 dsigma^2)/sigma^2 is (twice) the Poincare
    half-plane metric in coordinates (mu/sqrt2, sigma), hence
        d = sqrt2 * arccosh(1 + ((mu1-mu2)^2/2 + (s1-s2)^2) / (2 s1 s2)).
    """
    num = 0.5 * (mu1 - mu2) ** 2 + (s1 - s2) ** 2
    arg = 1.0 + num / (2.0 * s1 * s2)
    return np.sqrt(2.0) * np.arccosh(np.maximum(arg, 1.0))


def fr_disloc(log_return, *, window, long_window):
    """Signed Fisher-Rao dislocation of the short-window model from the long-window model,
    in standard-error units: sign(mu_s - mu_l) * d_FR * sqrt(window)."""
    mu_s, sd_s = _gauss(log_return, window)
    mu_l, sd_l = _gauss(log_return, long_window)
    d = _fisher_rao(mu_s, sd_s, mu_l, sd_l)
    return np.sign(mu_s - mu_l) * d * np.sqrt(window)


def fr_scale(log_return, *, window, long_window):
    """Signed Fisher-Rao length of the pure-scale geodesic N(m, s_l^2) -> N(m, s_s^2):
    sqrt2 * ln(s_s / s_l) (positive when recent volatility exceeds the long-run level)."""
    _, sd_s = _gauss(log_return, window)
    _, sd_l = _gauss(log_return, long_window)
    return np.sqrt(2.0) * np.log(sd_s / sd_l)


SIGNALS = (
    Signal(
        name="fr_disloc",
        fn=fr_disloc,
        inputs=("log_return",),
        params={"window": Window(10), "long_window": LongWindow(120)},
        lookback=lambda window, long_window: max(window, long_window),
        description="signed Fisher-Rao distance between short- and long-window Gaussian "
        "return models, scaled by sqrt(window)",
    ),
    Signal(
        name="fr_scale",
        fn=fr_scale,
        inputs=("log_return",),
        params={"window": Window(20), "long_window": LongWindow(252)},
        lookback=lambda window, long_window: max(window, long_window),
        description="signed Fisher-Rao length of the scale geodesic between recent and "
        "long-run volatility",
    ),
)

ENTRY_DISLOC = -1.0  # dislocation (standard-error units) needed to enter
EXIT_DISLOC = 0.0  # exit once the short model's drift is back above the long model's
MAX_SCALE = 0.5  # scale-geodesic gate: sqrt2*ln(s20/s252) < 0.5, i.e. vol ratio < ~1.42
HOLD = 10  # time stop: exit if no entry condition in the last HOLD bars


def _recent_any(cond: np.ndarray, h: int) -> np.ndarray:
    """True at t if cond was true at any bar in [t-h+1, t] (causal)."""
    out = np.zeros(len(cond), dtype=bool)
    for k in range(h):
        out[k:] |= cond[: len(cond) - k]
    return out


def rule(sig):
    s = sig["fr_disloc"]
    v = sig["fr_scale"]
    ok = np.isfinite(s) & np.isfinite(v)
    cond = ok & (s < ENTRY_DISLOC) & (v < MAX_SCALE)
    recent = _recent_any(cond, HOLD)
    entry = np.where(ok, cond.astype(float), np.nan)
    exit_ = np.where(ok, ((s > EXIT_DISLOC) | ~recent).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="hyperbolic_dislocation_reversal",
    domain="information_geometry",
    hypothesis=(
        "On the statistical manifold of Gaussian return models, equipped with the Fisher-Rao "
        "metric (a hyperbolic half-plane), the model fitted to the last two weeks of returns "
        "wanders around the model fitted to the last six months. A large geodesic excursion "
        "towards lower drift that is NOT accompanied by a large excursion along the scale "
        "(volatility) direction is mostly sampling noise / liquidity-driven overshoot and tends "
        "to relax back towards the long-run model, giving a positive expected return to a long "
        "position held until the drift side of the excursion closes. Excursions with a large "
        "scale component are regime breaks (volatility shocks) where the long-run model is no "
        "longer a valid anchor, so they are not traded."
    ),
    definition=(
        "Gaussian fits on trailing windows of daily log returns r: (mu_s, s_s) over n=10 bars, "
        "(mu_l, s_l) over L=120 bars. Fisher-Rao distance on the univariate normal manifold "
        "(metric ds^2=(dmu^2+2 dsigma^2)/sigma^2, a scaled Poincare half-plane): "
        "d_FR = sqrt2 * arccosh(1 + ((mu_s-mu_l)^2/2 + (s_s-s_l)^2)/(2 s_s s_l)). "
        "Dislocation signal D_t = sign(mu_s-mu_l) * d_FR * sqrt(n) (geodesic distance in units "
        "of the sampling standard error ~ 1/sqrt(n)). Scale signal V_t = sqrt2*ln(s_20/s_252), "
        "the signed Fisher-Rao length of the pure-scale geodesic between the 20- and 252-bar "
        "volatility models. Entry condition E_t = [D_t < -1] AND [V_t < 0.5]. "
        "Exit condition X_t = [D_t > 0] OR [E_tau false for all tau in (t-10, t]] (time stop: "
        "a position is not kept more than 10 bars after the last dislocation signal). "
        "The harness holds a long position from an entry until an exit."
    ),
    references=(
        "Rao, C. R. (1945). Information and the accuracy attainable in the estimation of "
        "statistical parameters. Bulletin of the Calcutta Mathematical Society, 37, 81-91.",
        "Atkinson, C., & Mitchell, A. F. S. (1981). Rao's distance measure. Sankhya: The Indian "
        "Journal of Statistics, Series A, 43(3), 345-365.",
        "Costa, S. I. R., Santos, S. A., & Strapasson, J. E. (2015). Fisher information "
        "distance: A geometrical reading. Discrete Applied Mathematics, 197, 59-69.",
        "Amari, S. (2016). Information Geometry and Its Applications. Applied Mathematical "
        "Sciences 194, Springer.",
        "Nielsen, F. (2020). An elementary introduction to information geometry. Entropy, "
        "22(10), 1100.",
        "Lehmann, B. N. (1990). Fads, martingales, and market efficiency. Quarterly Journal of "
        "Economics, 105(1), 1-28.",
    ),
    signals=SIGNALS,
    rule=rule,
    rule_lookback=HOLD,
    novelty=(
        "Short-term reversal is usually measured with z-scores of price or return. Here the "
        "trigger is the hyperbolic (Fisher-Rao) geodesic distance between two fitted return "
        "distributions, which jointly prices drift and scale changes in an invariant way, and "
        "the decomposition of the manifold displacement into its drift-signed total length and "
        "its pure-scale geodesic length is used to separate tradeable dislocations from "
        "volatility regime breaks. During development, gating on the scale component in both "
        "directions was tested: dips in calm regimes (V<0) lost money, unbounded scale "
        "excursions added drawdown, and the bounded gate V<0.5 worked best."
    ),
    limitations=(
        "Gaussian fits on 10 bars are noisy, so the signal is close to a statistical test with "
        "a modest edge; the development objective was only marginally positive (about +0.01) "
        "and nearby variants scattered roughly +/-0.1, so performance is fragile. The edge "
        "comes mainly from equity indices and commodities; on currency pairs (no drift, "
        "symmetric) long-only reversal had roughly zero Sharpe with real drawdowns. It does "
        "badly in persistent bear markets, where dips keep extending. Turnover is about 20-30 "
        "per year, so it is sensitive to trading costs. The 252-bar warm-up of the scale "
        "signal means it does not trade in the first year of data."
    ),
)
