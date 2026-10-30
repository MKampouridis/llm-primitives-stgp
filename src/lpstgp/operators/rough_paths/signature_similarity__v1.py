"""SignatureSimilarity: cosine similarity of depth-3 signatures of the current and previous window.

Each window's time-augmented path (time in [0, 1], z-scored increments / sqrt(w)) is summarised by
its truncated signature, a faithful description of the path's shape up to reparametrisation; the
cosine measures whether the latest shape repeats the previous one.
"""

import numpy as np
from numba import njit

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.operators.rough_paths._paths import signature3, standardised_increments
from lpstgp.types import Path, Real, Window


@njit(cache=True)
def _rolling(p: np.ndarray, window: int) -> np.ndarray:
    n = len(p)
    out = np.full(n, np.nan)
    dtau = np.full(window, 1.0 / window)
    root = np.sqrt(window)
    for t in range(2 * window, n):
        now = standardised_increments(p, t, window)
        before = standardised_increments(p, t - window, window)
        if len(now) == 0 or len(before) == 0:
            continue
        a = signature3(dtau, now / root)
        b = signature3(dtau, before / root)
        na, nb = np.sqrt((a * a).sum()), np.sqrt((b * b).sum())
        out[t] = (a * b).sum() / (na * nb)
    return out


def signature_similarity(p: np.ndarray, window: int) -> np.ndarray:
    return _rolling(p, window)


SPEC = OperatorSpec(
    name="signature_similarity",
    version=1,
    domain="rough_paths",
    summary="Cosine between the depth-3 signatures of (t, X) over the last and the previous w bars.",
    inputs=(Path,),
    params=(ParamSpec("window", Window),),
    output=Real,
    lookback=lambda window: 2 * window + 1,
    missing=Missing.PROPAGATE,
    definition=(
        r"\cos\angle(S^{\le3}(\gamma_t), S^{\le3}(\gamma_{t-w})), \gamma_s = (\tau, \tilde X) on (s-w, s], "
        r"signature levels 1-3 (14 terms) via Chen's identity"
    ),
    references=(
        "Chen (1958), Annals of Mathematics 65(1):163-178",
        "Kiraly & Oberhauser (2019), Journal of Machine Learning Research 20(31):1-45",
        "Chevyrev & Oberhauser (2022), Journal of Machine Learning Research 23(176):1-42",
    ),
    reference_test="roughpy signature (depth 3) of each window",
    impl=signature_similarity,
    invariances=("shift", "scale"),
)
