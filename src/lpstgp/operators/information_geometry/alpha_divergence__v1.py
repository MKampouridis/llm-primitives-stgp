"""AlphaDivergence: Amari's alpha-divergence between two rolling distributions."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import Alpha, Hist, Real


def alpha_divergence(p: np.ndarray, q: np.ndarray, alpha: float) -> np.ndarray:
    a, b = (1.0 - alpha) / 2.0, (1.0 + alpha) / 2.0
    out = 4.0 / (1.0 - alpha**2) * (1.0 - np.sum(p**a * q**b, axis=1))
    out[np.isnan(p).any(axis=1) | np.isnan(q).any(axis=1)] = np.nan
    return out


SPEC = OperatorSpec(
    name="alpha_divergence",
    version=1,
    domain="information_geometry",
    summary="Amari alpha-divergence D_alpha(p||q); alpha=0 is 4(1 - Bhattacharyya), alpha -> -1 is KL(p||q).",
    inputs=(Hist, Hist),
    params=(ParamSpec("alpha", Alpha),),
    output=Real,
    lookback=lambda alpha: 1,
    missing=Missing.ELEMENTWISE,
    definition=r"D_\alpha(p\|q) = \frac{4}{1-\alpha^2}\left(1 - \sum_b p(b)^{\frac{1-\alpha}2} q(b)^{\frac{1+\alpha}2}\right)",
    references=(
        "Amari (2009), IEEE Trans. Information Theory 55(11):4925-4931",
        "Amari (2016), Information Geometry and Its Applications, Springer, ch. 3",
    ),
    reference_test="KL limits (scipy.special.rel_entr) and the Hellinger closed form",
    impl=alpha_divergence,
)
