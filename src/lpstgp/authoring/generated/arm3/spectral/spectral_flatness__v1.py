"""Multitaper spectral flatness (Wiener entropy) of a series over a trailing window."""

import numpy as np

from operator_api import LongWindow, Operator, Real, Series

N_TAPERS = 5


def _sine_tapers(n: int, k: int) -> np.ndarray:
    """Riedel-Sidorenko sine tapers, shape (k, n), orthonormal."""
    i = np.arange(1, n + 1)[None, :]
    j = np.arange(1, k + 1)[:, None]
    return np.sqrt(2.0 / (n + 1)) * np.sin(np.pi * j * i / (n + 1))


def _impl(x, window):
    x = np.asarray(x, dtype=np.float64)
    T = len(x)
    out = np.full(T, np.nan)
    if T < window:
        return out
    W = np.lib.stride_tricks.sliding_window_view(x, window)
    ok = np.all(np.isfinite(W), axis=1)
    Wc = np.where(ok[:, None], W, 0.0)
    Wc = Wc - Wc.mean(axis=1, keepdims=True)
    tap = _sine_tapers(window, N_TAPERS)
    spec = np.abs(np.fft.rfft(Wc[:, None, :] * tap[None, :, :], axis=2)) ** 2
    nf = (window - 1) // 2
    S = spec.mean(axis=1)[:, 1 : nf + 1]  # Fourier frequencies strictly between 0 and Nyquist
    m = S.mean(axis=1)
    good = ok & (m > 0)
    m_safe = np.where(good, m, 1.0)
    Sn = S / m_safe[:, None] + 1e-12
    flat = np.exp(np.mean(np.log(Sn), axis=1))
    res = np.where(good, flat, np.nan)
    out[window - 1 :] = res
    return out


OPERATOR = Operator(
    name="spectral_flatness",
    summary=(
        "Wiener entropy (spectral flatness) of the multitaper power spectrum of the series over a "
        "trailing window: by the Kolmogorov-Szego formula, the share of the variance that is "
        "unpredictable from the series' own linear past. Near 1 = white (no linear structure), "
        "lower = power concentrated in some frequency band (persistent trends, cycles, "
        "volatility clustering or alternation)."
    ),
    inputs=(Series,),
    params=(("window", LongWindow),),
    output=Real,
    lookback=lambda window: int(window),
    missing="propagate",
    definition=(
        "Let x_1..x_N be the last N = window values, demeaned. Sine-multitaper spectrum with "
        "K = 5 orthonormal tapers v_k(n) = sqrt(2/(N+1)) sin(pi k n/(N+1)): "
        "S(f_j) = (1/K) sum_k |sum_n v_k(n) x_n exp(-2 pi i f_j n)|^2 at the Fourier "
        "frequencies f_j = j/N, j = 1..floor((N-1)/2). Output: spectral flatness "
        "F = exp(mean_j log S(f_j)) / mean_j S(f_j) in (0, 1], the ratio of geometric to "
        "arithmetic mean of the spectrum. By the Kolmogorov-Szego formula "
        "sigma^2_innov = exp(int log S), F estimates the ratio of the one-step linear prediction "
        "error variance to the total variance (1 = white noise; the multitaper estimator gives "
        "about 0.9 for white noise because E log chi^2_10/10 < 0). Scale-invariant; NaN if any "
        "value in the window is missing."
    ),
    references=(
        "Thomson, D. J. (1982). Spectrum estimation and harmonic analysis. Proceedings of the "
        "IEEE 70(9), 1055-1096.",
        "Riedel, K. S. and Sidorenko, A. (1995). Minimum bias multiple taper spectral "
        "estimation. IEEE Transactions on Signal Processing 43(1), 188-195.",
        "Gray, A. H. and Markel, J. D. (1974). A spectral-flatness measure for studying the "
        "autocorrelation method of linear prediction of speech analysis. IEEE Transactions on "
        "Acoustics, Speech, and Signal Processing 22(3), 207-217.",
        "Percival, D. B. and Walden, A. T. (1993). Spectral Analysis for Physical Applications. "
        "Cambridge University Press.",
    ),
    impl=_impl,
    invariances=("scale",),
)
