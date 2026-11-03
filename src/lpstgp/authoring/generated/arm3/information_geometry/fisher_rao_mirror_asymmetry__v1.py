"""Signed Fisher-Rao distance between a binned distribution and its mirror image."""

import numpy as np

from operator_api import BIN_EDGES, Hist, Operator, Real

_C = 0.5 * (BIN_EDGES[:-1] + BIN_EDGES[1:])  # bin centres, symmetric about 0


def _impl(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        tot = p.sum(axis=1, keepdims=True)
        q = np.clip(p, 0.0, None) / tot
        mirror = q[:, ::-1]
        bc = np.sqrt(q * mirror).sum(axis=1)
        dist = 2.0 * np.arccos(np.clip(bc, -1.0, 1.0))
        tilt = q @ _C  # = (E_p[c] - E_mirror[c]) / 2
    sign = np.where(tilt > 0, 1.0, np.where(tilt < 0, -1.0, 0.0))
    out = sign * dist
    out[~(np.all(np.isfinite(p), axis=1) & (tot[:, 0] > 0))] = np.nan
    return out


OPERATOR = Operator(
    name="fisher_rao_mirror_asymmetry",
    summary=(
        "Signed Fisher-Rao geodesic distance between the binned return distribution and its "
        "reflection about the centre: 0 = symmetric, positive = mass tilted to the upper side, "
        "negative = tilted to the lower side (range -pi .. pi)."
    ),
    inputs=(Hist,),
    params=(),
    output=Real,
    lookback=lambda: 1,
    missing="elementwise",
    definition=(
        "The reflection R: c -> -c of the (symmetric) robust-z bins acts on the probability "
        "simplex as the permutation (Rp)_i = p_{N-1-i}, an isometry of the Fisher information "
        "metric whose fixed-point set is the submanifold of symmetric distributions. The "
        "Fisher-Rao (geodesic) distance between p and its image is "
        "d(p, Rp) = 2 arccos(sum_i sqrt(p_i p_{N-1-i})), which is twice the distance from p "
        "along the geodesic to its symmetric midpoint; d = 0 iff p is symmetric and d = pi "
        "when p and Rp have disjoint supports. The output is "
        "A_t = sign(sum_i c_i p_i) * d(p, Rp): the magnitude is a parametrisation-free, "
        "bounded and outlier-robust measure of shape asymmetry, the sign tells whether the "
        "distribution leans to the upper (positive) or lower (negative) side of its robust "
        "centre. Pointwise in t; NaN rows give NaN."
    ),
    references=(
        "Bhattacharyya, A. (1943). On a measure of divergence between two statistical "
        "populations defined by their probability distributions. Bulletin of the Calcutta "
        "Mathematical Society 35, 99-109.",
        "Kass, R. E. & Vos, P. W. (1997). Geometrical Foundations of Asymptotic Inference. "
        "Wiley, New York.",
        "Amari, S. (2016). Information Geometry and Its Applications. Applied Mathematical "
        "Sciences 194, Springer.",
    ),
    impl=_impl,
)
