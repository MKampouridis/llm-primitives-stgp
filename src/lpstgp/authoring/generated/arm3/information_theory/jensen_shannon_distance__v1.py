"""Jensen-Shannon distance between two rolling return distributions."""

import numpy as np

from operator_api import Hist, Operator, Real


def _impl(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=np.float64)
    q = np.asarray(q, dtype=np.float64)
    T = p.shape[0]
    out = np.full(T, np.nan)
    ok = np.all(np.isfinite(p), axis=1) & np.all(np.isfinite(q), axis=1)
    if not ok.any():
        return out
    P = np.clip(p[ok], 0.0, None)
    Q = np.clip(q[ok], 0.0, None)
    sp = P.sum(axis=1)
    sq = Q.sum(axis=1)
    good = (sp > 0) & (sq > 0)
    P = P / np.where(sp > 0, sp, 1.0)[:, None]
    Q = Q / np.where(sq > 0, sq, 1.0)[:, None]
    M = 0.5 * (P + Q)
    with np.errstate(divide="ignore", invalid="ignore"):
        kp = np.where(P > 0, P * np.log2(P / M), 0.0).sum(axis=1)
        kq = np.where(Q > 0, Q * np.log2(Q / M), 0.0).sum(axis=1)
    jsd = np.clip(0.5 * (kp + kq), 0.0, 1.0)
    res = np.sqrt(jsd)
    res[~good] = np.nan
    out[ok] = res
    return out


OPERATOR = Operator(
    name="jensen_shannon_distance",
    summary=(
        "Jensen-Shannon distance (square root of the JS divergence, in bits) between two binned "
        "return distributions, e.g. the recent window versus the preceding one: 0 = same shape, "
        "1 = disjoint support; a detector of distributional regime change."
    ),
    inputs=(Hist, Hist),
    params=(),
    output=Real,
    lookback=lambda: 1,
    missing="elementwise",
    definition=(
        "For probability vectors P_t and Q_t on the same 16 bins (rows of the two Hist inputs, "
        "renormalised to sum to one), let M = (P + Q)/2 and "
        "JSD(P||Q) = 1/2 KL(P||M) + 1/2 KL(Q||M), with KL(A||B) = sum_k A_k log2(A_k / B_k) and "
        "0 log 0 = 0. JSD lies in [0, 1] bits, is symmetric and always finite (no smoothing "
        "needed even with empty bins). The output is the Jensen-Shannon distance "
        "D_t = sqrt(JSD(P_t||Q_t)), a true metric on distributions. It is computed bar by bar; "
        "NaN if either row is missing. Typical use: P = rolling_hist(ret, w), "
        "Q = past_hist(ret, w), measuring how much information distinguishes the current "
        "return distribution from the previous one."
    ),
    references=(
        "Lin, J. (1991). Divergence measures based on the Shannon entropy. IEEE Transactions on "
        "Information Theory 37(1), 145-151.",
        "Endres, D. M. and Schindelin, J. E. (2003). A new metric for probability distributions. "
        "IEEE Transactions on Information Theory 49(7), 1858-1860.",
        "Cover, T. M. and Thomas, J. A. (2006). Elements of Information Theory, 2nd ed. Wiley.",
    ),
    impl=_impl,
    invariances=(),
)
