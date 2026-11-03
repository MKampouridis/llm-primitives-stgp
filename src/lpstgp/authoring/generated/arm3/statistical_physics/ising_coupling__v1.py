"""ising_coupling: inverse 1D Ising problem on the median-binarised series."""

from __future__ import annotations

import math

import numpy as np

from operator_api import LongWindow, Operator, Real, Series

_MIN_VALID = 0.8
_PSEUDO = 0.5  # Haldane-Anscombe pseudocount on each pair count


def _ising_coupling(x: np.ndarray, window: int) -> np.ndarray:
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
    med = np.nanmedian(Xo, axis=1)
    s = np.sign(Xo - med[:, None])
    s[~vo] = 0.0  # missing bars are vacant sites; ties with the median are too
    a, b = s[:, :-1], s[:, 1:]
    npp = ((a > 0) & (b > 0)).sum(axis=1) + _PSEUDO
    nmm = ((a < 0) & (b < 0)).sum(axis=1) + _PSEUDO
    npm = ((a > 0) & (b < 0)).sum(axis=1) + _PSEUDO
    nmp = ((a < 0) & (b > 0)).sum(axis=1) + _PSEUDO
    J = 0.25 * np.log((npp * nmm) / (npm * nmp))
    res = np.full(len(X), np.nan)
    res[ok] = J
    out[window - 1 :] = res
    return out


OPERATOR = Operator(
    name="ising_coupling",
    summary=(
        "Maximum-likelihood nearest-neighbour coupling beta*J of a 1D Ising chain fitted to the "
        "series binarised at its window median: > 0 ferromagnetic (states persist: trending signs "
        "or clustered volatility), < 0 antiferromagnetic (states alternate), 0 = free spins."
    ),
    inputs=(Series,),
    params=(("window", LongWindow),),
    output=Real,
    lookback=lambda window: int(window),
    missing="min_valid",
    min_valid=_MIN_VALID,
    definition=(
        "Over the trailing window of W bars, spins s_t = sign(x_t - median_W(x)) in {-1, +1} "
        "(missing bars and exact ties are vacant sites, s = 0). The sequence is modelled as a 1D "
        "Ising chain with Hamiltonian -beta*H = J * sum_t s_t s_{t+1} + h * sum_t s_t. By the "
        "transfer-matrix solution, the stationary pair law is p(s, s') = v(s) T(s, s') v(s') / "
        "lambda with T(s, s') = exp(J s s' + h (s + s')/2), so the eigenvector and field factors "
        "cancel in the pair odds ratio and p(+,+) p(-,-) / (p(+,-) p(-,+)) = exp(4J) exactly. "
        "The (conditional) maximum-likelihood estimate of the coupling is therefore "
        "J_hat = (1/4) ln[(n_{++}+c)(n_{--}+c) / ((n_{+-}+c)(n_{-+}+c))], with n_{ab} the counts "
        "of adjacent occupied pairs (s_{t-1}, s_t) = (a, b) in the window and c = 1/2 the "
        "Haldane-Anscombe correction. The correlation length of the chain is "
        "xi = -1/ln tanh|J|. Computed when at least 80% of the window is valid. Invariant to "
        "positive rescaling of the series (rank-based spins)."
    ),
    references=(
        "Ising, E. (1925). Beitrag zur Theorie des Ferromagnetismus. Zeitschrift fur Physik 31, 253-258.",
        "Baxter, R. J. (1982). Exactly Solved Models in Statistical Mechanics. Academic Press, ch. 2 (transfer matrix of the 1D Ising model).",
        "Nguyen, H. C., Zecchina, R. and Berg, J. (2017). Inverse statistical problems: from the inverse Ising problem to data science. Advances in Physics 66(3), 197-261.",
        "Bornholdt, S. (2001). Expectation bubbles in a spin model of markets: intermittency from frustration across scales. International Journal of Modern Physics C 12(5), 667-674.",
    ),
    impl=_ising_coupling,
    invariances=("scale",),
)
