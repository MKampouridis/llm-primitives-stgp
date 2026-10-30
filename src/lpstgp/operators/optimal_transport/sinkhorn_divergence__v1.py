"""SinkhornDivergence: debiased entropic optimal transport between two rolling distributions.

Matrix-scaling Sinkhorn iterations (u = a / Kv, v = b / K'u). The kernel K = exp(-C/eps) has a unit
diagonal, so Kv >= min(v) never underflows for the regularisation grid used (eps >= 0.25 in squared
z units, smallest kernel entry ~1e-98). Each row is solved independently with its own stopping
rule (marginal error), so a row's value never depends on other rows (prefix invariance holds).
"""

import numpy as np
from numba import njit

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import BIN_EDGES, Epsilon, Hist, Real

CENTRES = 0.5 * (BIN_EDGES[:-1] + BIN_EDGES[1:])
COST = (CENTRES[:, None] - CENTRES[None, :]) ** 2
MAX_ITER = 10000
TOL = 1e-9  # L1 violation of the first marginal


@njit(cache=True)
def entropic_ot(
    a: np.ndarray, b: np.ndarray, kernel: np.ndarray, eps: float, max_iter: int, tol: float
) -> float:
    """OT_eps(a, b) = <a, f> + <b, g> with f = eps log u, g = eps log v at the Sinkhorn fixed point."""
    n = len(a)
    u = np.ones(n)
    v = np.ones(n)
    for _ in range(max_iter):
        for i in range(n):
            s = 0.0
            for j in range(n):
                s += kernel[i, j] * v[j]
            u[i] = a[i] / s
        for j in range(n):
            s = 0.0
            for i in range(n):
                s += kernel[i, j] * u[i]
            v[j] = b[j] / s
        err = 0.0  # after the v-update the second marginal is exact; check the first
        for i in range(n):
            s = 0.0
            for j in range(n):
                s += kernel[i, j] * v[j]
            err += abs(u[i] * s - a[i])
        if err < tol:
            break
    total = 0.0
    for i in range(n):
        total += eps * (a[i] * np.log(u[i]) + b[i] * np.log(v[i]))
    return total


@njit(cache=True)
def _rows(
    p: np.ndarray, q: np.ndarray, kernel: np.ndarray, eps: float, max_iter: int, tol: float
) -> np.ndarray:
    n = p.shape[0]
    out = np.full(n, np.nan)
    for t in range(n):
        if np.isnan(p[t, 0]) or np.isnan(q[t, 0]):
            continue
        pq = entropic_ot(p[t], q[t], kernel, eps, max_iter, tol)
        pp = entropic_ot(p[t], p[t], kernel, eps, max_iter, tol)
        qq = entropic_ot(q[t], q[t], kernel, eps, max_iter, tol)
        out[t] = pq - 0.5 * (pp + qq)
    return out


def sinkhorn_divergence(p: np.ndarray, q: np.ndarray, epsilon: float) -> np.ndarray:
    return _rows(p, q, np.exp(-COST / epsilon), epsilon, MAX_ITER, TOL)


SPEC = OperatorSpec(
    name="sinkhorn_divergence",
    version=1,
    domain="optimal_transport",
    summary="Debiased Sinkhorn divergence (squared-distance cost on bin centres, regularisation epsilon).",
    inputs=(Hist, Hist),
    params=(ParamSpec("epsilon", Epsilon),),
    output=Real,
    lookback=lambda epsilon: 1,
    missing=Missing.ELEMENTWISE,
    definition=(
        r"S_\varepsilon(p,q) = OT_\varepsilon(p,q) - \tfrac12 OT_\varepsilon(p,p) - \tfrac12 OT_\varepsilon(q,q), "
        r"OT_\varepsilon = \min_{P\in U(p,q)} \langle P, C\rangle + \varepsilon\,KL(P\|p\otimes q), C_{ij} = (c_i - c_j)^2"
    ),
    references=(
        "Cuturi (2013), Advances in Neural Information Processing Systems 26:2292-2300",
        "Genevay, Peyre & Cuturi (2018), AISTATS, PMLR 84:1608-1617",
        "Feydy, Sejourne, Vialard, Amari, Trouve & Peyre (2019), AISTATS, PMLR 89:2681-2690",
    ),
    reference_test="POT ot.sinkhorn plan (converged), objective recomputed",
    impl=sinkhorn_divergence,
)
