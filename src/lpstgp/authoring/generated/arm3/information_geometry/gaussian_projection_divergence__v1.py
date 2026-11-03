"""KL divergence from a binned distribution to its m-projection on the discrete Gaussian family."""

import numpy as np

from operator_api import BIN_EDGES, Hist, Operator, Real

_C = 0.5 * (BIN_EDGES[:-1] + BIN_EDGES[1:])  # bin centres (robust z units)
_C2 = _C * _C
_C3 = _C2 * _C
_C4 = _C2 * _C2
_ITER = 60
_MAX_STEP = 2.0


def _impl(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=np.float64)
    T = p.shape[0]
    out = np.full(T, np.nan)
    with np.errstate(invalid="ignore"):
        tot = p.sum(axis=1)
    ok = np.all(np.isfinite(p), axis=1) & (tot > 0)
    if not ok.any():
        return out
    P = np.clip(p[ok], 0.0, None)
    P = P / P.sum(axis=1, keepdims=True)
    eta1 = P @ _C
    eta2 = P @ _C2
    var = np.maximum(eta2 - eta1 * eta1, 1e-3)
    th1 = eta1 / var
    th2 = -0.5 / var
    for _ in range(_ITER):
        logits = th1[:, None] * _C + th2[:, None] * _C2
        logits -= logits.max(axis=1, keepdims=True)
        q = np.exp(logits)
        q /= q.sum(axis=1, keepdims=True)
        m1, m2, m3, m4 = q @ _C, q @ _C2, q @ _C3, q @ _C4
        g1, g2 = m1 - eta1, m2 - eta2
        a = m2 - m1 * m1
        b = m3 - m1 * m2
        d = m4 - m2 * m2
        det = a * d - b * b
        det = np.where(det > 1e-14, det, 1e-14)
        s1 = (d * g1 - b * g2) / det
        s2 = (a * g2 - b * g1) / det
        norm = np.sqrt(s1 * s1 + s2 * s2)
        scale = np.minimum(1.0, _MAX_STEP / np.maximum(norm, 1e-300))
        th1 = th1 - scale * s1
        th2 = th2 - scale * s2
    logits = th1[:, None] * _C + th2[:, None] * _C2
    logits -= logits.max(axis=1, keepdims=True)
    logq = logits - np.log(np.exp(logits).sum(axis=1, keepdims=True))
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(P > 0, P * (np.log(np.where(P > 0, P, 1.0)) - logq), 0.0)
    out[ok] = np.maximum(terms.sum(axis=1), 0.0)
    return out


OPERATOR = Operator(
    name="gaussian_projection_divergence",
    summary=(
        "Kullback-Leibler divergence (nats) from the binned return distribution to its "
        "m-projection onto the discretised Gaussian exponential family: the information lost "
        "by describing the market's current distribution with mean and variance alone."
    ),
    inputs=(Hist,),
    params=(),
    output=Real,
    lookback=lambda: 1,
    missing="elementwise",
    definition=(
        "Let c_i be the 16 bin centres and M = {q_theta(i) = exp(theta_1 c_i + theta_2 c_i^2 - "
        "psi(theta))} the two-parameter exponential (e-flat) family of discretised Gaussians on "
        "them, psi the log-partition function. For the binned distribution p (a Hist row), the "
        "m-projection q* = argmin_{q in M} KL(p || q) is the unique member whose expectation "
        "parameters match p: E_q*[c] = E_p[c], E_q*[c^2] = E_p[c^2]; it is found by Newton's "
        "method on the convex dual psi(theta) - <theta, eta_p> (Hessian = Fisher information "
        "Cov_q(c, c^2)). The output is D_t = KL(p || q*) = sum_i p_i log(p_i / q*_i). By the "
        "generalised Pythagorean theorem of the dually flat structure, "
        "D = H(q*) - H(p) and KL(p || q) = D + KL(q* || q) for every q in M, so D is the part "
        "of the distribution (skew, fat or thin tails, multimodality) orthogonal to the "
        "Gaussian manifold: the excess structure beyond the first two moments. 0 for an exactly "
        "discretised Gaussian. Pointwise in t; NaN rows give NaN."
    ),
    references=(
        "Csiszar, I. (1975). I-divergence geometry of probability distributions and "
        "minimization problems. Annals of Probability 3(1), 146-158.",
        "Amari, S. (2001). Information geometry on hierarchy of probability distributions. "
        "IEEE Transactions on Information Theory 47(5), 1701-1711.",
        "Amari, S. & Nagaoka, H. (2000). Methods of Information Geometry. Translations of "
        "Mathematical Monographs 191, American Mathematical Society / Oxford University Press.",
    ),
    impl=_impl,
)
