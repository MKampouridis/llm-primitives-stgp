"""ShannonEntropy: normalised Shannon entropy of a rolling distribution."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec
from lpstgp.types import N_BINS, Hist, Real


def shannon_entropy(h: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(h > 0.0, h * np.log(h), 0.0)
    out = -terms.sum(axis=1) / np.log(N_BINS)
    out[np.isnan(h).any(axis=1)] = np.nan
    return out


SPEC = OperatorSpec(
    name="shannon_entropy",
    version=1,
    domain="information_theory",
    summary="Entropy of the rolling histogram, normalised to [0, 1] by log(number of bins).",
    inputs=(Hist,),
    params=(),
    output=Real,
    lookback=lambda: 1,
    missing=Missing.ELEMENTWISE,
    definition=r"H(p_t) = -\sum_b p_t(b)\log p_t(b) / \log B",
    references=(
        "Shannon (1948), Bell System Technical Journal 27(3):379-423",
        "Cover & Thomas (2006), Elements of Information Theory, 2nd ed., Wiley, ch. 2",
    ),
    reference_test="scipy.stats.entropy",
    impl=shannon_entropy,
)
