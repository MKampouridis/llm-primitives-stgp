"""SSATrendShare: variance share of the leading singular-spectrum component of the window's path."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.operators.spectral._windows import place, windows
from lpstgp.types import LongWindow, Path, Real

EMBED = 10


def ssa_trend_share(p: np.ndarray, window: int) -> np.ndarray:
    if len(p) < window:
        return np.full(len(p), np.nan)
    rows = windows(p, window)
    centred = np.nan_to_num(rows - rows.mean(axis=1, keepdims=True))
    lagged = np.lib.stride_tricks.sliding_window_view(centred, EMBED, axis=1)  # (n, K, L)
    cov = np.einsum("nki,nkj->nij", lagged, lagged)
    eig = np.linalg.eigvalsh(cov)  # ascending; only eigenvalues (squared singular values) are used
    total = eig.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        values = eig[:, -1] / total
    values[~(total > 0.0)] = np.nan
    return place(values, rows, len(p), window)


SPEC = OperatorSpec(
    name="ssa_trend_share",
    version=1,
    domain="spectral",
    summary="lambda_1 / sum(lambda) of the 10-lag trajectory matrix of the centred path (trend dominance).",
    inputs=(Path,),
    params=(ParamSpec("window", LongWindow),),
    output=Real,
    lookback=lambda window: window,
    missing=Missing.PROPAGATE,
    definition=(
        r"\sigma_1^2/\sum_i\sigma_i^2, \sigma_i the singular values of the L\times K Hankel matrix "
        r"of the window's centred path, L = 10"
    ),
    references=(
        "Broomhead & King (1986), Physica D 20(2-3):217-236",
        "Golyandina, Nekrutkin & Zhigljavsky (2001), Analysis of Time Series Structure: SSA, Chapman & Hall",
    ),
    reference_test="numpy.linalg.svd of the explicit Hankel matrix (scipy.linalg.hankel)",
    impl=ssa_trend_share,
    invariances=("shift", "scale"),
)
