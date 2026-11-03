"""hawkes_branching_ratio: criticality (reflexivity) of extreme-move events from count dispersion."""

from __future__ import annotations

import math

import numpy as np

from operator_api import LongWindow, Operator, Real, Series

_MIN_VALID = 0.8
_EVENT_SHARE = 0.2  # events: the 20% largest absolute deviations from the window median
_BLOCK = 10  # counting-block length (bars)
_F_FLOOR = 0.1  # floor on the dispersion index (bounds the output below at 1 - 1/sqrt(0.1))


def _hawkes_branching_ratio(x: np.ndarray, window: int) -> np.ndarray:
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
    dev = np.abs(Xo - med[:, None])
    thr = np.nanquantile(dev, 1.0 - _EVENT_SHARE, axis=1)
    ev = np.where(vo, dev > thr[:, None], False).astype(np.float64)
    cs = np.concatenate([np.zeros((len(ev), 1)), np.cumsum(ev, axis=1)], axis=1)
    counts = cs[:, _BLOCK:] - cs[:, :-_BLOCK]  # overlapping block counts
    m = counts.mean(axis=1)
    v = counts.var(axis=1)
    p = m / _BLOCK
    fpc = (window - _BLOCK) / (window - 1.0)  # finite-population (hypergeometric) correction
    with np.errstate(divide="ignore", invalid="ignore"):
        F = v / (m * (1.0 - p) * fpc)
        n = 1.0 - 1.0 / np.sqrt(np.maximum(F, _F_FLOOR))
    n[~(m > 0) | ~(p < 1)] = np.nan
    res = np.full(len(X), np.nan)
    res[ok] = n
    out[window - 1 :] = res
    return out


OPERATOR = Operator(
    name="hawkes_branching_ratio",
    summary=(
        "Branching ratio of a self-exciting (Hawkes) description of extreme moves, from the "
        "dispersion of event counts: 0 = shocks arrive independently, -> 1 = the market is near "
        "criticality (most shocks are triggered by earlier shocks: reflexive, cascading dynamics), "
        "< 0 = shocks are more regular than random."
    ),
    inputs=(Series,),
    params=(("window", LongWindow),),
    output=Real,
    lookback=lambda window: int(window),
    missing="min_valid",
    min_valid=_MIN_VALID,
    definition=(
        "Over the trailing window of W bars, an event occurs at bar t when the absolute deviation "
        "|x_t - median_W(x)| exceeds its own window 80% quantile (the 20% largest moves). In a "
        "stationary Hawkes process with branching ratio n = integral of the excitation kernel, "
        "each event begets on average n offspring, the total cluster size is 1/(1-n), and the "
        "index of dispersion of counts over long intervals is F = Var[N_Delta]/E[N_Delta] -> "
        "1/(1-n)^2 (Hardiman and Bouchaud 2014). With N_k the event counts in all overlapping "
        "blocks of Delta = 10 bars inside the window, m and v their mean and variance and "
        "p = m/Delta, the dispersion index relative to independent occupation of the window by the "
        "same number of events (hypergeometric block counts) is "
        "F = v / (m (1 - p) (W - Delta)/(W - 1)), and the operator returns n_hat = 1 - 1/sqrt(max(F, 0.1)). "
        "n_hat = 0 for independent events, n_hat -> 1 at the critical (endogenous, cascading) "
        "point, and n_hat < 0 for under-dispersed (regular) event sequences. Computed when at "
        "least 80% of the window is valid; invariant to positive rescaling (rank-defined events)."
    ),
    references=(
        "Hawkes, A. G. (1971). Spectra of some self-exciting and mutually exciting point processes. Biometrika 58(1), 83-90.",
        "Hardiman, S. J. and Bouchaud, J.-P. (2014). Branching-ratio approximation for the self-exciting Hawkes process. Physical Review E 90, 062807.",
        "Filimonov, V. and Sornette, D. (2012). Quantifying reflexivity in financial markets: toward a prediction of flash crashes. Physical Review E 85, 056108.",
        "Harris, T. E. (1963). The Theory of Branching Processes. Springer.",
    ),
    impl=_hawkes_branching_ratio,
    invariances=("scale",),
)
