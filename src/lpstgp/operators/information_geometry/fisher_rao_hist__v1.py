"""FisherRaoHist: Fisher-Rao (geodesic) distance between two rolling distributions."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec
from lpstgp.types import Hist, Real


def fisher_rao_hist(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    bc = np.sqrt(p * q).sum(axis=1)
    out = 2.0 * np.arccos(np.clip(bc, 0.0, 1.0))
    out[np.isnan(p).any(axis=1) | np.isnan(q).any(axis=1)] = np.nan
    return out


SPEC = OperatorSpec(
    name="fisher_rao_hist",
    version=1,
    domain="information_geometry",
    summary="Fisher-Rao distance on the simplex: twice the angle between sqrt(p) and sqrt(q), in [0, pi].",
    inputs=(Hist, Hist),
    params=(),
    output=Real,
    lookback=lambda: 1,
    missing=Missing.ELEMENTWISE,
    definition=r"d_{FR}(p,q) = 2\arccos\sum_b \sqrt{p(b)q(b)}",
    references=(
        "Rao (1945), Bulletin of the Calcutta Mathematical Society 37:81-91",
        "Amari & Nagaoka (2000), Methods of Information Geometry, AMS/Oxford, ch. 2",
    ),
    reference_test="great-circle distance between sqrt-embeddings on the sphere",
    impl=fisher_rao_hist,
)
