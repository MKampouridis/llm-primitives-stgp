"""transport_direction: net direction of the one-dimensional optimal transport plan that carries
one binned distribution onto another."""

import numpy as np

from operator_api import BIN_EDGES, Hist, Operator, Real


def _impl(target: np.ndarray, source: np.ndarray) -> np.ndarray:
    a = np.asarray(target, dtype=np.float64)
    b = np.asarray(source, dtype=np.float64)
    valid = np.all(np.isfinite(a), axis=1) & np.all(np.isfinite(b), axis=1)
    width = np.diff(BIN_EDGES)[:-1]  # distances between consecutive bin centres
    Fa = np.cumsum(np.where(valid[:, None], a, 0.0), axis=1)[:, :-1]
    Fb = np.cumsum(np.where(valid[:, None], b, 0.0), axis=1)[:, :-1]
    diff = (Fb - Fa) * width[None, :]  # > 0: target has less mass below the cut (moved up)
    net = diff.sum(axis=1)
    tot = np.abs(diff).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(tot > 1e-12, net / tot, 0.0)
    out = np.clip(out, -1.0, 1.0)
    out[~valid] = np.nan
    return out


OPERATOR = Operator(
    name="transport_direction",
    summary=(
        "Net direction of the Wasserstein-1 optimal transport plan from the second distribution "
        "(e.g. the preceding window) to the first (the recent window): +1 = every unit of mass "
        "moves up (first-order stochastic dominance), -1 = every unit moves down, near 0 = "
        "mass spreads or contracts without a net shift."
    ),
    inputs=(Hist, Hist),
    params=(),
    output=Real,
    lookback=lambda: 1,
    missing="elementwise",
    definition=(
        "Let a (target) and b (source) be probability vectors on the 16 fixed bins with centres "
        "z_1 < ... < z_16 and cumulative distribution functions F_a, F_b. On the line the "
        "monotone (quantile) coupling is optimal for every convex cost and, for the cost |x-y|, "
        "its total cost is W1(a,b) = sum_{k=1}^{15} |F_b(k) - F_a(k)| (z_{k+1} - z_k): the mass "
        "carried across each cut between bins k and k+1 is |F_b(k) - F_a(k)|, upward when "
        "F_b(k) > F_a(k) and downward otherwise. The output is the net share of transport work "
        "done upward, D = sum_k (F_b(k) - F_a(k)) dz_k / W1(a,b) in [-1, 1] (0 if a = b). "
        "D = +1 iff a first-order stochastically dominates b, D = -1 iff b dominates a; "
        "|D| < 1 when the plan moves mass both ways (a change of spread or shape)."
    ),
    references=(
        "Vallender, S. S. (1974). Calculation of the Wasserstein distance between probability "
        "distributions on the line. Theory of Probability and Its Applications 18(4), 784-786.",
        "Santambrogio, F. (2015). Optimal Transport for Applied Mathematicians. Birkhauser, "
        "Progress in Nonlinear Differential Equations 87 (Ch. 2: one-dimensional transport).",
        "Rachev, S. T. and Ruschendorf, L. (1998). Mass Transportation Problems, Vol. I: "
        "Theory. Springer.",
    ),
    impl=_impl,
)
