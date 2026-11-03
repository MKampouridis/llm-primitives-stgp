"""cycle_affinity: Schnakenberg cycle affinity (broken detailed balance) of the tercile chain."""

from __future__ import annotations

import math

import numpy as np

from operator_api import LongWindow, Operator, Real, Series

_MIN_VALID = 0.8
_PSEUDO = 0.5  # pseudocount on each transition count


def _cycle_affinity(x: np.ndarray, window: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    T = len(x)
    out = np.full(T, np.nan)
    if T < window:
        return out
    X = np.lib.stride_tricks.sliding_window_view(x, window)
    valid = np.isfinite(X)
    ok = valid.sum(axis=1) >= math.ceil(_MIN_VALID * window)
    if not ok.any():
        return out
    Xo = X[ok]
    vo = valid[ok]
    q1 = np.nanquantile(Xo, 1.0 / 3.0, axis=1)
    q2 = np.nanquantile(Xo, 2.0 / 3.0, axis=1)
    state = (Xo > q1[:, None]).astype(np.int64) + (Xo > q2[:, None]).astype(np.int64)
    state[~vo] = -1
    a, b = state[:, :-1], state[:, 1:]
    pair = (a >= 0) & (b >= 0)

    def n(i: int, j: int) -> np.ndarray:
        return (pair & (a == i) & (b == j)).sum(axis=1) + _PSEUDO

    forward = n(0, 1) * n(1, 2) * n(2, 0)  # low -> mid -> high -> low
    backward = n(1, 0) * n(2, 1) * n(0, 2)  # low -> high -> mid -> low
    res = np.full(len(X), np.nan)
    res[ok] = np.log(forward / backward)
    out[window - 1 :] = res
    return out


OPERATOR = Operator(
    name="cycle_affinity",
    summary=(
        "Schnakenberg cycle affinity of the three-state (window tercile) Markov chain of the series: "
        "the thermodynamic force that breaks detailed balance. 0 = time-reversible dynamics; > 0 the "
        "cycle low->mid->high->low dominates (gradual build-up, abrupt collapse); < 0 the reverse "
        "cycle dominates (abrupt jump, gradual relaxation, e.g. volatility shocks that decay)."
    ),
    inputs=(Series,),
    params=(("window", LongWindow),),
    output=Real,
    lookback=lambda window: int(window),
    missing="min_valid",
    min_valid=_MIN_VALID,
    definition=(
        "Over the trailing window of W bars, code each value into a state "
        "sigma_t in {0 (low), 1 (mid), 2 (high)} by the window terciles of x. Count transitions "
        "n_ij = #{t : sigma_{t-1} = i, sigma_t = j} over adjacent valid pairs. For a stationary "
        "Markov jump process on three states the cycle graph has one independent cycle, and "
        "Schnakenberg's network theory gives the total entropy production rate as "
        "sigma = J_c * A_c, where J_c is the net probability current around the cycle and "
        "A_c = ln[ (P_01 P_12 P_20) / (P_10 P_21 P_02) ] = ln[ (n_01 n_12 n_20) / (n_10 n_21 n_02) ] "
        "is the cycle affinity (the stationary occupations cancel in the product). The operator "
        "returns A_hat = ln[ prod_forward (n_ij + c) / prod_backward (n_ji + c) ] with c = 1/2. "
        "Detailed balance (time-reversal symmetry, equilibrium) holds iff A = 0 (Kolmogorov's "
        "criterion); its sign gives the direction of the circulating current and its magnitude "
        "the entropy produced per completed cycle (in units of k_B). Computed when at least 80% "
        "of the window is valid; invariant to positive rescaling of the series (rank coding)."
    ),
    references=(
        "Schnakenberg, J. (1976). Network theory of microscopic and macroscopic behavior of master equation systems. Reviews of Modern Physics 48(4), 571-585.",
        "Kolmogorov, A. N. (1936). Zur Theorie der Markoffschen Ketten. Mathematische Annalen 112, 155-160.",
        "Seifert, U. (2012). Stochastic thermodynamics, fluctuation theorems and molecular machines. Reports on Progress in Physics 75, 126001.",
        "Roldan, E. and Parrondo, J. M. R. (2010). Estimating dissipation from single stationary trajectories. Physical Review Letters 105, 150607.",
        "Zumbach, G. (2009). Time reversal invariance in finance. Quantitative Finance 9(5), 505-515.",
    ),
    impl=_cycle_affinity,
    invariances=("scale",),
)
