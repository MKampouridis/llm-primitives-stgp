"""SpectralSlope: Geweke-Porter-Hudak (GPH) log-periodogram estimate of the memory parameter d."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.operators.spectral._windows import place, windows
from lpstgp.types import LongWindow, Real, Series


def spectral_slope(x: np.ndarray, window: int) -> np.ndarray:
    if len(x) < window:
        return np.full(len(x), np.nan)
    rows = windows(x, window)
    clean = np.nan_to_num(rows)
    m = int(np.floor(np.sqrt(window)))
    j = np.arange(1, m + 1)
    omega = 2.0 * np.pi * j / window
    reg = np.log(4.0 * np.sin(omega / 2.0) ** 2)
    spec = np.abs(np.fft.rfft(clean - clean.mean(axis=1, keepdims=True), axis=1)[:, 1 : m + 1]) ** 2
    with np.errstate(divide="ignore", invalid="ignore"):
        y = np.log(spec)
        xc = reg - reg.mean()
        slope = ((y - y.mean(axis=1, keepdims=True)) * xc).sum(axis=1) / (xc**2).sum()
    values = -slope
    values[~np.isfinite(values)] = np.nan
    return place(values, rows, len(x), window)


SPEC = OperatorSpec(
    name="spectral_slope",
    version=1,
    domain="spectral",
    summary="GPH estimate of d: minus the slope of log I(w_j) on log(4 sin^2(w_j/2)), j = 1..floor(sqrt(w)).",
    inputs=(Series,),
    params=(ParamSpec("window", LongWindow),),
    output=Real,
    lookback=lambda window: window,
    missing=Missing.PROPAGATE,
    definition=(
        r"\hat d = -\mathrm{slope}(\log(4\sin^2(\omega_j/2)), \log I(\omega_j)), \omega_j = 2\pi j/w, "
        r"j = 1..\lfloor\sqrt w\rfloor, I the periodogram of the demeaned window"
    ),
    references=("Geweke & Porter-Hudak (1983), Journal of Time Series Analysis 4(4):221-238",),
    reference_test="scipy.signal.periodogram + numpy.polyfit",
    impl=spectral_slope,
    invariances=("scale",),
)
