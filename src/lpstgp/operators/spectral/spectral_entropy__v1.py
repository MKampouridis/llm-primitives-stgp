"""SpectralEntropy: normalised Shannon entropy of the window's power spectrum."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.operators.spectral._windows import periodogram_rows, place, windows
from lpstgp.types import Real, Series, Window


def spectral_entropy(x: np.ndarray, window: int) -> np.ndarray:
    if len(x) < window:
        return np.full(len(x), np.nan)
    rows = windows(x, window)
    spec = periodogram_rows(np.nan_to_num(rows))
    total = spec.sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = spec / total
        terms = np.where(p > 0.0, p * np.log(p), 0.0)
    values = -terms.sum(axis=1) / np.log(spec.shape[1])
    values[total[:, 0] <= 0.0] = np.nan
    return place(values, rows, len(x), window)


SPEC = OperatorSpec(
    name="spectral_entropy",
    version=1,
    domain="spectral",
    summary="Entropy of the normalised one-sided periodogram of the demeaned window, divided by log(#bins).",
    inputs=(Series,),
    params=(ParamSpec("window", Window),),
    output=Real,
    lookback=lambda window: window,
    missing=Missing.PROPAGATE,
    definition=r"H_s = -\sum_k \hat P(f_k)\log\hat P(f_k) / \log K, \hat P = periodogram / its sum, K frequencies",
    references=(
        "Powell & Percival (1979), Journal of Physics A 12(11):2053-2071",
        "Inouye et al. (1991), Electroencephalography and Clinical Neurophysiology 79(3):204-210",
    ),
    reference_test="antropy.spectral_entropy(method='fft', normalize=True) per window",
    impl=spectral_entropy,
    invariances=("scale",),
)
