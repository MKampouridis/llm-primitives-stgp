"""TsallisEntropy: normalised Tsallis q-entropy of a rolling distribution."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import N_BINS, Hist, QEnt, Real


def tsallis_entropy(h: np.ndarray, q: float) -> np.ndarray:
    out = (1.0 - np.sum(h**q, axis=1)) / (1.0 - N_BINS ** (1.0 - q))
    out[np.isnan(h).any(axis=1)] = np.nan
    return out


SPEC = OperatorSpec(
    name="tsallis_entropy",
    version=1,
    domain="statistical_physics",
    summary="Tsallis entropy S_q of the rolling histogram divided by its maximum (uniform distribution).",
    inputs=(Hist,),
    params=(ParamSpec("q", QEnt),),
    output=Real,
    lookback=lambda q: 1,
    missing=Missing.ELEMENTWISE,
    definition=r"S_q/S_q^{\max} = \frac{1 - \sum_b p(b)^q}{1 - B^{1-q}}, \lim_{q\to1} = H/\log B",
    references=(
        "Tsallis (1988), Journal of Statistical Physics 52(1-2):479-487",
        "Tsallis (2009), Introduction to Nonextensive Statistical Mechanics, Springer",
    ),
    reference_test="closed form; q -> 1 limit equals normalised Shannon entropy (scipy.stats.entropy)",
    impl=tsallis_entropy,
)
