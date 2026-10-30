"""WaveletEnergyShare: share of detail energy at one Haar DWT level (4 levels) in the window."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.operators.spectral._windows import place, windows
from lpstgp.types import LongWindow, Real, Series, WLevel

LEVELS = 4
BLOCK = 2**LEVELS


def detail_energies(rows: np.ndarray) -> np.ndarray:
    """Energy of Haar detail coefficients at levels 1..4 for each row (length a multiple of 16)."""
    approx = rows
    energies = []
    for _ in range(LEVELS):
        even, odd = approx[:, 0::2], approx[:, 1::2]
        detail = (odd - even) / np.sqrt(2.0)
        approx = (even + odd) / np.sqrt(2.0)
        energies.append((detail**2).sum(axis=1))
    return np.stack(energies, axis=1)


def wavelet_energy_share(x: np.ndarray, window: int, level: int) -> np.ndarray:
    if len(x) < window:
        return np.full(len(x), np.nan)
    rows = windows(x, window)
    used = BLOCK * (window // BLOCK)
    energy = detail_energies(np.nan_to_num(rows[:, window - used :]))  # the most recent bars
    total = energy.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        values = energy[:, level - 1] / total
    values[~(total > 0.0)] = np.nan
    return place(values, rows, len(x), window)


SPEC = OperatorSpec(
    name="wavelet_energy_share",
    version=1,
    domain="spectral",
    summary="E_j / (E_1+..+E_4): Haar detail energy at level j over the last 16*floor(w/16) bars.",
    inputs=(Series,),
    params=(ParamSpec("window", LongWindow), ParamSpec("level", WLevel)),
    output=Real,
    lookback=lambda window, level: window,
    missing=Missing.PROPAGATE,
    definition=r"E_j = \sum_k d_{j,k}^2 (Haar DWT detail coefficients at level j), share = E_j / \sum_{i=1}^4 E_i",
    references=(
        "Mallat (1989), IEEE Trans. Pattern Analysis and Machine Intelligence 11(7):674-693",
        "Percival & Walden (2000), Wavelet Methods for Time Series Analysis, Cambridge UP",
    ),
    reference_test="pywt.wavedec(wavelet='haar', level=4)",
    impl=wavelet_energy_share,
    invariances=("scale",),
)
