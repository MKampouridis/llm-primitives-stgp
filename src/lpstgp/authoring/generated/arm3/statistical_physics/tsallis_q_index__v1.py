"""tsallis_q_index: entropic index q of the q-Gaussian (Tsallis) fit to a binned distribution."""

from __future__ import annotations

import numpy as np
import scipy.stats as stats

from operator_api import BIN_EDGES, Hist, Operator, Real

_Q_GRID = np.round(np.arange(0.5, 2.8 + 1e-9, 0.05), 4)  # entropic index q
_S_GRID = np.exp(np.linspace(np.log(0.2), np.log(4.0), 61))  # scale s (robust z units)
_P_FLOOR = 1e-12


def _q_gaussian_cdf(z: np.ndarray, q: float, s: float) -> np.ndarray:
    """CDF of the q-Gaussian exp_q(-beta z^2) with beta = 1 / ((3 - q) s^2)."""
    if abs(q - 1.0) < 1e-9:
        return stats.norm.cdf(z / s)
    if q > 1.0:  # Student t with nu = (3-q)/(q-1) degrees of freedom and scale s
        return stats.t.cdf(z / s, df=(3.0 - q) / (q - 1.0))
    # q < 1: compact support |z| <= R, symmetric Beta(a, a) on [-R, R]
    R = s * np.sqrt((3.0 - q) / (1.0 - q))
    a = 1.0 / (1.0 - q) + 1.0
    u = np.clip((z / R + 1.0) / 2.0, 0.0, 1.0)
    return stats.beta.cdf(u, a, a)


def _bin_log_probs() -> np.ndarray:
    """log P[bin | q, s] for every grid point, shape (N_BINS, n_q * n_s); outer bins absorb tails."""
    inner = BIN_EDGES[1:-1]
    cols = []
    for q in _Q_GRID:
        for s in _S_GRID:
            c = np.concatenate([[0.0], _q_gaussian_cdf(inner, float(q), float(s)), [1.0]])
            cols.append(np.diff(c))
    P = np.maximum(np.array(cols).T, _P_FLOOR)
    P = P / P.sum(axis=0, keepdims=True)
    return np.log(P)


_LOGP = _bin_log_probs()


def _tsallis_q_index(h: np.ndarray) -> np.ndarray:
    h = np.asarray(h, dtype=np.float64)
    T = h.shape[0]
    out = np.full(T, np.nan)
    ok = np.all(np.isfinite(h), axis=1)
    if not ok.any():
        return out
    H = h[ok]
    H = H / H.sum(axis=1, keepdims=True)
    ll = (H @ _LOGP).reshape(len(H), len(_Q_GRID), len(_S_GRID))
    prof = ll.max(axis=2)  # profile log-likelihood in q
    k = np.argmax(prof, axis=1)
    qhat = _Q_GRID[k].astype(np.float64)
    # parabolic refinement of the maximum between grid neighbours
    inner = (k > 0) & (k < len(_Q_GRID) - 1)
    idx = np.nonzero(inner)[0]
    if len(idx):
        ki = k[idx]
        y0 = prof[idx, ki - 1]
        y1 = prof[idx, ki]
        y2 = prof[idx, ki + 1]
        den = y0 - 2.0 * y1 + y2
        with np.errstate(divide="ignore", invalid="ignore"):
            off = np.where(den < 0, 0.5 * (y0 - y2) / den, 0.0)
        step = _Q_GRID[1] - _Q_GRID[0]
        qhat[idx] = qhat[idx] + np.clip(off, -0.5, 0.5) * step
    out[ok] = qhat
    return out


OPERATOR = Operator(
    name="tsallis_q_index",
    summary=(
        "Entropic index q of the q-Gaussian (Tsallis maximum-entropy) distribution fitted by "
        "maximum likelihood to the binned return distribution: q = 1 Boltzmann-Gibbs (Gaussian), "
        "q > 1 power-law tails (tail exponent 2/(q-1)), q < 1 truncated, thin-tailed distribution."
    ),
    inputs=(Hist,),
    params=(),
    output=Real,
    lookback=lambda: 1,
    missing="elementwise",
    definition=(
        "The q-Gaussian p_q(z) proportional to exp_q(-beta z^2) = [1 - (1-q) beta z^2]_+^{1/(1-q)} "
        "maximises the Tsallis entropy S_q = (1 - sum p^q)/(q - 1) under a fixed (escort) "
        "second moment, and reduces to the Boltzmann-Gibbs Gaussian at q = 1. With "
        "beta = 1/((3-q) s^2) it is a Student t with nu = (3-q)/(q-1) degrees of freedom and "
        "scale s for 1 < q < 3 (tails |z|^{-2/(q-1)}), a Gaussian of s.d. s at q = 1, and a "
        "symmetric Beta law on |z| <= s sqrt((3-q)/(1-q)) for q < 1. For each bar, with h_i the "
        "probabilities of the 16 robust-z bins (outer bins absorb the tails), the operator "
        "maximises the multinomial log-likelihood L(q, s) = sum_i h_i ln P_i(q, s), "
        "P_i = F_q(e_{i+1}; s) - F_q(e_i; s), over the grid q in [0.5, 2.8] (step 0.05) and "
        "61 log-spaced scales s in [0.2, 4]; it returns the maximiser of the profile likelihood "
        "max_s L(q, s), refined by parabolic interpolation between grid neighbours. Pointwise in "
        "time (lookback 1); a missing histogram gives a missing output."
    ),
    references=(
        "Tsallis, C. (1988). Possible generalization of Boltzmann-Gibbs statistics. Journal of Statistical Physics 52, 479-487.",
        "Tsallis, C., Anteneodo, C., Borland, L. and Osorio, R. (2003). Nonextensive statistical mechanics and economics. Physica A 324, 89-100.",
        "Borland, L. (2002). Option pricing formulas based on a non-Gaussian stock price model. Physical Review Letters 89, 098701.",
        "Umarov, S., Tsallis, C. and Steinberg, S. (2008). On a q-central limit theorem consistent with nonextensive statistical mechanics. Milan Journal of Mathematics 76, 307-328.",
    ),
    impl=_tsallis_q_index,
)
