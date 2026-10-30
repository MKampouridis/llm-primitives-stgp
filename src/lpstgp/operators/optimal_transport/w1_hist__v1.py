"""W1Hist: Wasserstein-1 distance between two rolling distributions on the common bins."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec
from lpstgp.types import BIN_EDGES, Hist, Real

BIN_WIDTH = float(BIN_EDGES[1] - BIN_EDGES[0])


def w1_hist(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    gap = np.abs(np.cumsum(p - q, axis=1))[:, :-1]
    out = gap.sum(axis=1) * BIN_WIDTH
    out[np.isnan(p).any(axis=1) | np.isnan(q).any(axis=1)] = np.nan
    return out


SPEC = OperatorSpec(
    name="w1_hist",
    version=1,
    domain="optimal_transport",
    summary="Earth mover's distance between two histograms on the shared robust-z bin centres.",
    inputs=(Hist, Hist),
    params=(),
    output=Real,
    lookback=lambda: 1,
    missing=Missing.ELEMENTWISE,
    definition=r"W_1(p,q) = \int |F_p - F_q| = \Delta\sum_{b<B} |\sum_{c\le b} (p(c) - q(c))|, \Delta = bin width",
    references=(
        "Villani (2009), Optimal Transport: Old and New, Springer, ch. 6",
        "Peyre & Cuturi (2019), Foundations and Trends in Machine Learning 11(5-6):355-607, §2.6",
    ),
    reference_test="POT ot.emd2 with |c_i - c_j| cost and ot.wasserstein_1d",
    impl=w1_hist,
)
