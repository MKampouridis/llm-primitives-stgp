"""dispersive_geodesic_relaxation

Long-only daily strategy built on the Fisher-Rao geometry of the univariate Gaussian family
(a hyperbolic half-plane).  The model fitted to the last few weeks of returns is a point on
that manifold; the model fitted to the last year is an anchor.  After a volatility shock the
short-horizon point sits far from the anchor on the *dispersive* side (higher scale).  The
strategy watches the *radial geodesic velocity* of that point - the rate of change of its
Fisher-Rao distance to the anchor - and is long only while the point is travelling back
towards the anchor (the shock is being absorbed).  It exits at the first outward step or once
the point has crossed to the calm side of the anchor.
"""

from __future__ import annotations

import numpy as np

from strategy_api import Lag, LongWindow, Signal, Strategy, Window, trailing_windows

# ---------------------------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------------------------


def _fisher_rao_gauss(m1, s1, m2, s2):
    """Closed-form Fisher-Rao geodesic distance between N(m1, s1^2) and N(m2, s2^2).

    The Fisher metric ds^2 = (dmu^2 + 2 dsigma^2) / sigma^2 is sqrt(2) times the Poincare
    half-plane metric in coordinates (mu / sqrt(2), sigma), hence
    d = sqrt(2) * arccosh(1 + ((m1 - m2)^2 / 2 + (s1 - s2)^2) / (2 s1 s2)).
    """
    num = 0.5 * (m1 - m2) ** 2 + (s1 - s2) ** 2
    return np.sqrt(2.0) * np.arccosh(1.0 + num / (2.0 * s1 * s2))


def _signed_excursion(x: np.ndarray, window: int, long_window: int) -> np.ndarray:
    """Fisher-Rao distance from the short-window Gaussian to the long-window (anchor) Gaussian,
    signed + on the dispersive side (short sigma > anchor sigma) and - on the calm side."""
    rs = trailing_windows(x, window)
    rl = trailing_windows(x, long_window)
    ms, ss = np.mean(rs, axis=1), np.std(rs, axis=1, ddof=1)
    ml, sl = np.mean(rl, axis=1), np.std(rl, axis=1, ddof=1)
    out = np.full(len(x), np.nan)
    ok = np.isfinite(ss) & np.isfinite(sl) & (ss > 0) & (sl > 0)
    if ok.any():
        d = _fisher_rao_gauss(ms[ok], ss[ok], ml[ok], sl[ok])
        out[ok] = d * np.where(ss[ok] > sl[ok], 1.0, -1.0)
    return out


# ---------------------------------------------------------------------------------------------
# signals
# ---------------------------------------------------------------------------------------------


def excursion(log_return, *, window, long_window):
    """Signed Fisher-Rao excursion E_t of the short model from the anchor model."""
    return _signed_excursion(np.asarray(log_return, dtype=float), window, long_window)


def radial_velocity(log_return, *, window, long_window, lag):
    """Radial geodesic velocity V_t = E_t - E_{t-lag} (per `lag` bars): negative while the
    short-horizon model moves back towards the anchor, positive while it moves away."""
    e = _signed_excursion(np.asarray(log_return, dtype=float), window, long_window)
    out = np.full(len(e), np.nan)
    if len(e) > lag:
        out[lag:] = e[lag:] - e[:-lag]
    return out


# ---------------------------------------------------------------------------------------------
# rule
# ---------------------------------------------------------------------------------------------

SHOCK = 0.35  # Fisher-Rao distance (nats-scale geodesic units) defining a dispersive shock
INWARD = -0.075  # radial velocity per lag that counts as relaxation towards the anchor


def rule(s):
    e = s["excursion"]
    v = s["radial_velocity"]
    ok = np.isfinite(e) & np.isfinite(v)
    e_prev = e - v  # excursion `lag` bars ago
    entry = (e_prev > SHOCK) & (v < INWARD)
    exit_ = (e < 0.0) | (v > 0.0)
    return (
        np.where(ok, entry.astype(float), np.nan),
        np.where(ok, exit_.astype(float), np.nan),
    )


# ---------------------------------------------------------------------------------------------
# strategy
# ---------------------------------------------------------------------------------------------

STRATEGY = Strategy(
    name="dispersive_geodesic_relaxation",
    domain="information_geometry",
    hypothesis=(
        "A volatility shock throws the short-horizon return law far from the long-run law on the "
        "dispersive (high-scale) side of the Gaussian statistical manifold. While the shock is "
        "still expanding, the risk of continued losses is high; once the short-horizon model "
        "starts travelling back along the manifold towards the long-run model (negative radial "
        "geodesic velocity), the shock is being absorbed and the market tends to pay the "
        "elevated risk premium demanded during the shock (post-shock rebound / volatility "
        "mean-reversion). A long position held only during this inward motion, and abandoned at "
        "the first outward step, harvests that premium with short holding periods, low exposure "
        "and small drawdowns. Because Fisher-Rao distance is invariant to rescaling returns, the "
        "same thresholds apply to any asset class."
    ),
    definition=(
        "Let r_t be daily log returns. Short model: theta_t = (mu_t, sigma_t), sample mean and "
        "standard deviation of r over the last w = 20 bars. Anchor: theta^A_t = (mu^A_t, sigma^A_t) "
        "over the last L = 252 bars. On the Gaussian manifold with Fisher metric "
        "ds^2 = (dmu^2 + 2 dsigma^2)/sigma^2 (sqrt(2) x Poincare half-plane in (mu/sqrt2, sigma)), "
        "the geodesic distance is "
        "d(theta1, theta2) = sqrt(2) * arccosh(1 + ((mu1-mu2)^2/2 + (sigma1-sigma2)^2)/(2 sigma1 sigma2)). "
        "Signed excursion: E_t = sign(sigma_t - sigma^A_t) * d(theta_t, theta^A_t) "
        "(+ = dispersive side, - = calm side). Radial geodesic velocity over lag k = 5: "
        "V_t = E_t - E_{t-k}. Rule: entry when E_{t-k} > 0.35 (the model was in a dispersive "
        "shock) and V_t < -0.075 (it is moving back towards the anchor); exit when V_t > 0 "
        "(first outward step) or E_t < 0 (the model has crossed to the calm side, shock fully "
        "absorbed). Lookback: 252 + 5 bars."
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
        "Moreira, A., & Muir, T. (2017). Volatility-managed portfolios. Journal of Finance, "
        "72(4), 1611-1644.",
    ),
    signals=(
        Signal(
            "excursion",
            excursion,
            ("log_return",),
            {"window": Window(20), "long_window": LongWindow(252)},
            lambda window, long_window: max(window, long_window),
            "Signed Fisher-Rao distance of the short Gaussian model from the long-run anchor.",
        ),
        Signal(
            "radial_velocity",
            radial_velocity,
            ("log_return",),
            {"window": Window(20), "long_window": LongWindow(252), "lag": Lag(5)},
            lambda window, long_window, lag: max(window, long_window) + lag,
            "Change of the signed Fisher-Rao excursion over `lag` bars (radial geodesic velocity).",
        ),
    ),
    rule=rule,
    rule_lookback=0,
    novelty=(
        "The earlier hyperbolic_dislocation_reversal strategy uses the *position* of the short "
        "model relative to the anchor, decomposed into drift and scale components, trades "
        "drift-side excursions and explicitly refuses scale (volatility) shocks. This strategy "
        "trades only the scale-side shocks, and uses a kinematic quantity instead of a static "
        "one: the radial geodesic velocity, i.e. the time derivative of the Fisher-Rao distance "
        "of the moving model to the anchor along its trajectory on the manifold. It enters on "
        "inward motion after a dispersive shock and exits on the first outward motion, so the "
        "signal is the direction of travel on the statistical manifold, not how far the model "
        "has strayed or in which coordinate."
    ),
    limitations=(
        "Low exposure (about 5-12% of days) and roughly 2-4 entries per year: on calm "
        "instruments the entry count can fall close to the 2-per-year minimum. The rolling "
        "20-bar model has a 'ghost' effect: a single large return leaving the window produces a "
        "sharp inward velocity, so part of the entry timing is mechanical (about one month after "
        "a shock). The Gaussian family ignores fat tails and skew, and the Fisher-Rao distance "
        "mixes drift and scale, so a strong rally with high volatility also counts as a "
        "dispersive excursion. The edge relies on a post-shock risk premium; it fails in "
        "persistent bear markets or crashes that unfold in successive waves (several commodity "
        "and equity segments lost money). On the development data the median instrument's "
        "score is slightly negative: its typical six-month segment has no trades or a small "
        "trade, so the median segment Sharpe is 0. The positive results are concentrated in "
        "the equity indices and some commodities."
    ),
)
