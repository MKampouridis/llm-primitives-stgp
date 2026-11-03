"""monotone_rearrangement_index: how close the price path is to the optimal (monotone) transport
map from calendar time onto its own occupation measure."""

import numpy as np

from operator_api import Operator, Path, Real, Window, trailing_windows


def _impl(path: np.ndarray, window: int) -> np.ndarray:
    p = np.asarray(path, dtype=np.float64)
    w = int(window)
    out = np.full(len(p), np.nan)
    if len(p) < w:
        return out
    X = trailing_windows(p, w)[w - 1 :]
    valid = np.all(np.isfinite(X), axis=1)
    c = np.arange(w, dtype=np.float64) - (w - 1) / 2.0  # centred calendar clock
    Xs = np.sort(np.where(valid[:, None], X, 0.0), axis=1)
    s_path = np.where(valid[:, None], X, 0.0) @ c  # gain of the realised (time-ordered) coupling
    s_opt = Xs @ c  # gain of the comonotone (Brenier) coupling; anti-monotone gives -s_opt
    with np.errstate(invalid="ignore", divide="ignore"):
        idx = np.where(s_opt > 0.0, s_path / s_opt, 0.0)
    idx = np.clip(idx, -1.0, 1.0)
    idx[~valid] = np.nan
    out[w - 1 :] = idx
    return out


OPERATOR = Operator(
    name="monotone_rearrangement_index",
    summary=(
        "Optimality of the time-ordered coupling between the calendar clock and the price "
        "occupation measure over the window: +1 when the path is the monotone (Brenier) map, "
        "i.e. a non-decreasing path; -1 when it is the anti-monotone one; near 0 for a path "
        "that wanders without order."
    ),
    inputs=(Path,),
    params=(("window", Window),),
    output=Real,
    lookback=lambda window: int(window),
    missing="propagate",
    definition=(
        "Over the last w bars let mu be the uniform measure on the clock times s = 1..w and "
        "nu = (1/w) sum_s delta_{p_s} the occupation measure of the log price. The path itself "
        "is a coupling pi_path = (1/w) sum_s delta_{(s, p_s)} of mu and nu. For the quadratic "
        "cost c(s,p) = (s-p)^2, minimising the transport cost is equivalent to maximising the "
        "gain G(pi) = sum (s - sbar) p; by Brenier's theorem in one dimension (equivalently the "
        "Hardy-Littlewood rearrangement inequality) the optimum is the comonotone coupling, "
        "pairing the sorted prices p_(1) <= ... <= p_(w) with s = 1..w, with gain "
        "G* = sum_s (s - sbar) p_(s), and the worst coupling (anti-monotone) has gain -G*. "
        "The index is I = G(pi_path) / G* in [-1, 1] (0 if the window is flat): I = 1 iff the "
        "path is cyclically monotone, i.e. itself the optimal transport map from time to price; "
        "I = -1 iff it is the anti-monotone map. Invariant to adding a constant to and to "
        "positively rescaling the path."
    ),
    references=(
        "Villani, C. (2003). Topics in Optimal Transportation. Graduate Studies in Mathematics "
        "58, American Mathematical Society. (Ch. 2: one-dimensional case, monotone rearrangement.)",
        "Brenier, Y. (1991). Polar factorization and monotone rearrangement of vector-valued "
        "functions. Communications on Pure and Applied Mathematics 44(4), 375-417.",
        "Hardy, G. H., Littlewood, J. E. and Polya, G. (1952). Inequalities, 2nd ed., Ch. X "
        "(rearrangements). Cambridge University Press.",
    ),
    impl=_impl,
    invariances=("shift", "scale"),
)
