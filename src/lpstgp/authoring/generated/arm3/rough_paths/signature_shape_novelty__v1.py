"""signature_shape_novelty: signature distance between the recent and the preceding path segment."""

from __future__ import annotations

import numpy as np

from operator_api import Operator, Path, Real, Window, trailing_windows

_DEPTH = 4


def _signatures(inc: np.ndarray) -> list[np.ndarray]:
    """Truncated signature (levels 1.._DEPTH) of piecewise-linear 2-d paths, batched.

    inc: (M, n, 2) increments. Returns [S1 (M,2), S2 (M,4), S3 (M,8), S4 (M,16)].
    Chen's identity: S <- S (x) exp(v) for each segment v.
    """
    M, n, _ = inc.shape
    S = [np.ones((M, 1))] + [np.zeros((M, 2**k)) for k in range(1, _DEPTH + 1)]
    for s in range(n):
        v = inc[:, s, :]
        powers = [np.ones((M, 1)), v]
        for k in range(2, _DEPTH + 1):
            powers.append((powers[-1][:, :, None] * v[:, None, :]).reshape(M, -1) / k)
        new = [S[0]]
        for k in range(1, _DEPTH + 1):
            acc = np.zeros((M, 2**k))
            for j in range(0, k + 1):
                acc += (S[j][:, :, None] * powers[k - j][:, None, :]).reshape(M, -1)
            new.append(acc)
        S = new
    return S[1:]


def _impl(path: np.ndarray, window: int) -> np.ndarray:
    x = np.asarray(path, dtype=np.float64)
    w = int(window)
    T = len(x)
    out = np.full(T, np.nan)
    L = 2 * w + 1
    if T < L:
        return out
    seg = trailing_windows(x, L)[L - 1 :]         # X_{t-2w} .. X_t
    d = np.diff(seg, axis=1)                      # 2w increments
    prev, rec = d[:, :w], d[:, w:]
    M = d.shape[0]
    qp = np.sqrt(np.sum(prev * prev, axis=1))
    qr = np.sqrt(np.sum(rec * rec, axis=1))
    ok = (qp > 0) & (qr > 0) & np.isfinite(qp) & np.isfinite(qr)
    with np.errstate(invalid="ignore", divide="ignore"):
        prev_n = np.where(ok[:, None], prev / qp[:, None], 0.0)
        rec_n = np.where(ok[:, None], rec / qr[:, None], 0.0)
    dt = np.full((M, w), 1.0 / w)
    inc = np.concatenate(
        [np.stack([dt, prev_n], axis=2), np.stack([dt, rec_n], axis=2)], axis=0
    )
    S = _signatures(inc)
    dist2 = np.zeros(M)
    for Sk in S:
        diff = Sk[M:] - Sk[:M]
        dist2 += np.sum(diff * diff, axis=1)
    val = np.sqrt(dist2)
    val[~ok] = np.nan
    out[L - 1 :] = val
    return out


OPERATOR = Operator(
    name="signature_shape_novelty",
    summary=(
        "Distance between the depth-4 signatures of the last `window` bars of the "
        "time-augmented, volatility-normalised log-price path and of the `window` bars before "
        "it: 0 = the market is tracing the same path shape (direction, curvature, ordering of "
        "moves) as before, large = the shape of the path has changed."
    ),
    inputs=(Path,),
    params=(("window", Window),),
    output=Real,
    lookback=lambda window: 2 * int(window) + 1,
    missing="propagate",
    definition=(
        "Split the last 2w increments of the path into the preceding block P and the recent "
        "block R (w = window each). Each block is turned into a planar piecewise-linear path "
        "Z = (s, Y) with s running uniformly over [0, 1] and Y the cumulative increments divided "
        "by the block's own root quadratic variation (so sum dY^2 = 1: shape, not volatility "
        "level, is compared). The truncated signature S^{<=4}(Z) = (S^1, ..., S^4), "
        "S^k = int_{0<u_1<...<u_k<1} dZ_{u_1} (x) ... (x) dZ_{u_k} in (R^2)^{(x)k}, is computed "
        "exactly by Chen's identity S(Z * v) = S(Z) (x) exp(v) over the linear segments v. "
        "Output: d = ( sum_{k=1..4} ||S^k(R) - S^k(P)||_2^2 )^{1/2}, the Euclidean distance "
        "in truncated tensor algebra. The signature determines a time-augmented path uniquely "
        "(Hambly-Lyons), and its levels are graded descriptors: net normalised move (level 1), "
        "Levy area/convexity (level 2), and higher-order shape at levels 3-4. Invariant to "
        "adding a constant to, or rescaling, the path."
    ),
    references=(
        "Chen, K.-T. (1958). Integration of paths - a faithful representation of paths by "
        "noncommutative formal power series. Transactions of the AMS 89(2), 395-407.",
        "Hambly, B., Lyons, T. (2010). Uniqueness for the signature of a path of bounded "
        "variation and the reduced path group. Annals of Mathematics 171(1), 109-167.",
        "Chevyrev, I., Kormilitzin, A. (2016). A primer on the signature method in machine learning. "
        "arXiv:1603.03788.",
        "Lyons, T., McLeod, A. D. (2022). Signature methods in machine learning. arXiv:2206.14674.",
    ),
    impl=_impl,
    invariances=("shift", "scale"),
)
