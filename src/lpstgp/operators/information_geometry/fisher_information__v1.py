"""FisherInformation: discrete Fisher information measure of a rolling distribution."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec
from lpstgp.types import Hist, Real


def fisher_information(h: np.ndarray) -> np.ndarray:
    root = np.sqrt(h)
    out = 0.5 * np.sum(np.diff(root, axis=1) ** 2, axis=1)
    out[np.isnan(h).any(axis=1)] = np.nan
    return out


SPEC = OperatorSpec(
    name="fisher_information",
    version=1,
    domain="information_geometry",
    summary="Fisher information of the binned density (location family), in [0, 1]: high when irregular.",
    inputs=(Hist,),
    params=(),
    output=Real,
    lookback=lambda: 1,
    missing=Missing.ELEMENTWISE,
    definition=r"F[p] = \tfrac12\sum_{b=1}^{B-1}\left(\sqrt{p(b+1)} - \sqrt{p(b)}\right)^2",
    references=(
        "Frieden (2004), Science from Fisher Information, Cambridge University Press",
        "Vignat & Bercher (2003), Physics Letters A 312(1-2):27-33",
        "Olivares, Plastino & Rosso (2012), Physica A 391(8):2518-2526",
    ),
    reference_test="ordpy.fisher_shannon on ordinal distributions (same discrete functional)",
    impl=fisher_information,
)
