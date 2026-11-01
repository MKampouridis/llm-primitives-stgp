"""mirror_divergence_reversal: distance of the recent return law from its own mirror image on the
asymmetric-Laplace statistical manifold, used as a contrarian (liquidity-provision) entry."""

import numpy as np
from strategy_api import Signal, Strategy, Window, trailing_windows


def _mirror_z(r: np.ndarray, window: int) -> np.ndarray:
    """Signed sqrt(2 n KL(P || iota P)) for the asymmetric-Laplace MLE on a trailing window.

    P = (p, a, b): p = P(r > 0), a = 1 / E[r | r > 0], b = 1 / E[-r | r < 0].
    iota (r -> -r) maps (p, a, b) -> (1 - p, b, a)."""
    rows = trailing_windows(r, window)
    out = np.full(len(r), np.nan)
    ok = np.all(np.isfinite(rows), axis=1)
    if not ok.any():
        return out
    R = rows[ok]
    n = R.shape[1]
    pos = R > 0
    neg = R < 0
    zero = ~(pos | neg)
    # Krichevsky-Trofimov (Jeffreys) half-counts keep p inside (0, 1); zero returns split evenly
    npos = pos.sum(1) + 0.5 * zero.sum(1) + 0.5
    nneg = neg.sum(1) + 0.5 * zero.sum(1) + 0.5
    p = npos / (npos + nneg)
    eps = 1e-12
    mpos = (np.where(pos, R, 0.0).sum(1) + eps) / npos  # mean gain  = 1/a
    mneg = (np.where(neg, -R, 0.0).sum(1) + eps) / nneg  # mean loss  = 1/b
    a = 1.0 / mpos
    b = 1.0 / mneg
    k_freq = (2.0 * p - 1.0) * np.log(p / (1.0 - p))
    k_mag = p * (np.log(a / b) + b / a - 1.0) + (1.0 - p) * (np.log(b / a) + a / b - 1.0)
    kl = np.maximum(k_freq + k_mag, 0.0)
    mean = p * mpos - (1.0 - p) * mneg
    out[ok] = np.sign(mean) * np.sqrt(2.0 * n * kl)
    return out


def mirror_divergence(log_return, *, window):
    """Multi-scale signed mirror divergence: average of z over windows w/2, w, 2w."""
    r = np.asarray(log_return, dtype=np.float64)
    h = max(window // 2, 2)
    return (_mirror_z(r, h) + _mirror_z(r, window) + _mirror_z(r, 2 * window)) / 3.0


SIG = Signal(
    name="mirror_divergence",
    fn=mirror_divergence,
    inputs=("log_return",),
    params={"window": Window(20)},
    lookback=lambda window: 2 * window,
    description="signed multi-scale sqrt(2 n KL(P || mirror P)) on the asymmetric-Laplace manifold",
)

ENTRY_Z = -1.5  # law significantly on the loss side of its mirror image
EXIT_Z = 0.0  # law has crossed back to the gain side of the symmetric submanifold


def rule(s):
    z = s["mirror_divergence"]
    known = np.isfinite(z)
    entry = np.where(known, (z < ENTRY_Z).astype(float), np.nan)
    exit_ = np.where(known, (z > EXIT_Z).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="mirror_divergence_reversal",
    domain="information_geometry",
    hypothesis=(
        "The sign flip r -> -r acts on any family of return laws. Its fixed points form the "
        "submanifold of direction-symmetric laws, where up and down moves are equally frequent "
        "and equally large. When the recent law sits significantly on the loss side of its mirror "
        "image (losses more frequent and/or larger than gains, beyond sampling noise), the "
        "imbalance is mostly transient one-sided order flow: forced selling or inventory pressure "
        "that liquidity providers absorb at a premium. It then decays back towards the symmetric "
        "submanifold. A long position opened when the loss-side divergence is large, and held until "
        "the law crosses back to the gain side, collects that premium. The divergence does not change "
        "when returns are rescaled (r -> c r), so the same thresholds apply to every asset class."
    ),
    definition=(
        "Model: asymmetric-Laplace (two-piece exponential) family for the daily log return r, "
        "f(r; p,a,b) = p a exp(-a r) 1{r>0} + (1-p) b exp(b r) 1{r<0}, with p = P(r>0), "
        "1/a = E[r | r>0], 1/b = E[-r | r<0]. Fisher metric: ds^2 = dp^2/(p(1-p)) + p da^2/a^2 + "
        "(1-p) db^2/b^2. MLE on a trailing window of n bars with Krichevsky-Trofimov half counts: "
        "p = (n_+ + 1/2)/(n + 1), 1/a = S_+/(n_+ + 1/2), 1/b = S_-/(n_- + 1/2) (S_+- = sums of gains "
        "and losses; zero returns split evenly). Mirror involution iota: (p,a,b) -> (1-p,b,a), an "
        "isometry of the Fisher metric whose fixed set is the symmetric submanifold M_s = {p=1/2, "
        "a=b}. Divergence to the mirror image (KL chain rule = frequency part + magnitude part): "
        "D = KL(P || iota P) = (2p-1) ln(p/(1-p)) + p[ln(a/b) + b/a - 1] + (1-p)[ln(b/a) + a/b - 1]. "
        "Here KL(P||iota P) = KL(iota P||P), so D is half the Jeffreys divergence. Locally "
        "sqrt(2D) ~ d_FR(P, iota P), and the geodesic from P to iota P meets M_s at its midpoint. "
        "Signed statistic: z_n = sgn(m) sqrt(2 n D), m = p/a - (1-p)/b (model mean). Multi-scale "
        "signal: Z_t = [z_{w/2} + z_w + z_{2w}]/3 with w = 20 (windows of 10, 20 and 40 bars). Rule: "
        "entry when Z_t < -1.5 (law clearly on the loss side of M_s); exit when Z_t > 0 (law back on "
        "the gain side). Lookback 2w = 40 bars."
    ),
    references=(
        "Amari, S. (2016). Information Geometry and Its Applications. Springer, Applied "
        "Mathematical Sciences 194.",
        "Amari, S., Nagaoka, H. (2000). Methods of Information Geometry. AMS / Oxford University "
        "Press, Translations of Mathematical Monographs 191.",
        "Kullback, S., Leibler, R. A. (1951). On information and sufficiency. Annals of "
        "Mathematical Statistics 22(1), 79-86.",
        "Jeffreys, H. (1946). An invariant form for the prior probability in estimation problems. "
        "Proceedings of the Royal Society A 186, 453-461.",
        "Kotz, S., Kozubowski, T. J., Podgorski, K. (2001). The Laplace Distribution and "
        "Generalizations. Birkhauser.",
        "Krichevsky, R., Trofimov, V. (1981). The performance of universal encoding. IEEE "
        "Transactions on Information Theory 27(2), 199-207.",
        "Campbell, J. Y., Grossman, S. J., Wang, J. (1993). Trading volume and serial correlation "
        "in stock returns. Quarterly Journal of Economics 108(4), 905-939.",
        "Nagel, S. (2012). Evaporating liquidity. Review of Financial Studies 25(7), 2005-2039.",
    ),
    signals=(SIG,),
    rule=rule,
    rule_lookback=0,
    novelty=(
        "There is no long-run anchor model and no Gaussian manifold. The earlier strategies measure "
        "a short-horizon Gaussian law against a long-horizon one (drift/scale excursions, radial "
        "velocity) or the speed of the law between adjacent windows. This one measures how far the "
        "current law is from its own image under the reflection group, i.e. from the "
        "reflection-invariant submanifold of a non-Gaussian (asymmetric-Laplace) family. That "
        "captures frequency asymmetry and magnitude (skew) asymmetry together through the KL chain "
        "rule, and it uses no volatility level or volatility change at all."
    ),
    limitations=(
        "Contrarian with no stop: in persistent, accelerating sell-offs the law can stay on the "
        "loss side for weeks, and the position takes the drawdown (falling-knife risk). The "
        "exponential magnitude model is sensitive to single large losses, so one outsized down day "
        "can trigger an entry. The edge on the development data is thin and noisy: single-window "
        "variants scored between -0.10 and +0.17 depending on the window, which is why the signal "
        "averages three scales. Entries are infrequent (about 3-6 per year), so short samples may "
        "fall near the 2-entries-per-year minimum. Long-only, so assets in a steady downtrend (e.g. "
        "a depreciating currency) can keep generating losing reversal trades."
    ),
)
