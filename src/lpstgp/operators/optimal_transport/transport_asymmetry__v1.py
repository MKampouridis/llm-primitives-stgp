"""TransportAsymmetry: signed Wasserstein-1 distance between the gain and loss distributions."""

import numpy as np
from numba import njit

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import LongWindow, Real, Series

MIN_SIDE = 3


@njit(cache=True)
def w1_samples(u: np.ndarray, v: np.ndarray) -> float:
    """Wasserstein-1 between two empirical measures on the line (integral of |F_u - F_v|)."""
    su, sv = np.sort(u), np.sort(v)
    allv = np.sort(np.concatenate((su, sv)))
    total = 0.0
    for k in range(len(allv) - 1):
        width = allv[k + 1] - allv[k]
        if width == 0.0:
            continue
        fu = np.searchsorted(su, allv[k], side="right") / len(su)
        fv = np.searchsorted(sv, allv[k], side="right") / len(sv)
        total += abs(fu - fv) * width
    return total


@njit(cache=True)
def _rolling(x: np.ndarray, window: int, min_side: int) -> np.ndarray:
    n = len(x)
    out = np.full(n, np.nan)
    for t in range(window - 1, n):
        seg = x[t - window + 1 : t + 1]
        if np.isnan(seg).any():
            continue
        gains = seg[seg > 0.0]
        losses = -seg[seg < 0.0]
        if len(gains) < min_side or len(losses) < min_side:
            continue
        scale = np.abs(seg).mean()
        if scale <= 0.0:
            continue
        sign = 1.0 if gains.mean() >= losses.mean() else -1.0
        out[t] = sign * w1_samples(gains, losses) / scale
    return out


def transport_asymmetry(x: np.ndarray, window: int) -> np.ndarray:
    return _rolling(x, window, MIN_SIDE)


SPEC = OperatorSpec(
    name="transport_asymmetry",
    version=1,
    domain="optimal_transport",
    summary="sign(mean gain - mean loss) * W1(gains, losses) / mean |x|: gain/loss distribution asymmetry.",
    inputs=(Series,),
    params=(ParamSpec("window", LongWindow),),
    output=Real,
    lookback=lambda window: window,
    missing=Missing.PROPAGATE,
    definition=(
        r"A = \mathrm{sign}(\bar G - \bar L)\, W_1(\mu_G, \mu_L) / \overline{|x|}, \mu_G = law of x_s>0, "
        r"\mu_L = law of -x_s for x_s<0, s in the window"
    ),
    references=(
        "Villani (2009), Optimal Transport: Old and New, Springer, ch. 6",
        "Cont (2001), Quantitative Finance 1(2):223-236 (gain/loss asymmetry)",
    ),
    reference_test="scipy.stats.wasserstein_distance",
    impl=transport_asymmetry,
    invariances=("scale",),
)
