"""Gain-free log-spectral distance between the recent and the preceding window."""

import numpy as np

from operator_api import LongWindow, Operator, Real, Series

N_TAPERS = 5
N_BANDS = 8


def _sine_tapers(n: int, k: int) -> np.ndarray:
    i = np.arange(1, n + 1)[None, :]
    j = np.arange(1, k + 1)[:, None]
    return np.sqrt(2.0 / (n + 1)) * np.sin(np.pi * j * i / (n + 1))


def _band_log_spectrum(W: np.ndarray, n: int) -> np.ndarray:
    """Log band powers (rows of W are windows of length n, finite)."""
    Wc = W - W.mean(axis=1, keepdims=True)
    tap = _sine_tapers(n, N_TAPERS)
    spec = np.abs(np.fft.rfft(Wc[:, None, :] * tap[None, :, :], axis=2)) ** 2
    nf = (n - 1) // 2
    S = spec.mean(axis=1)[:, 1 : nf + 1]
    bands = np.array_split(np.arange(nf), N_BANDS)
    P = np.stack([S[:, b].mean(axis=1) for b in bands], axis=1)
    tot = P.sum(axis=1, keepdims=True)
    tot = np.where(tot > 0, tot, 1.0)
    return np.log(P / tot + 1e-12)


def _impl(x, window):
    x = np.asarray(x, dtype=np.float64)
    T = len(x)
    L = 2 * window
    out = np.full(T, np.nan)
    if T < L:
        return out
    W = np.lib.stride_tricks.sliding_window_view(x, L)
    ok = np.all(np.isfinite(W), axis=1)
    W = np.where(ok[:, None], W, 0.0)
    old = _band_log_spectrum(W[:, :window], window)
    new = _band_log_spectrum(W[:, window:], window)
    d = new - old
    dist = np.sqrt(np.mean((d - d.mean(axis=1, keepdims=True)) ** 2, axis=1))
    var_ok = (np.var(W[:, :window], axis=1) > 0) & (np.var(W[:, window:], axis=1) > 0)
    out[L - 1 :] = np.where(ok & var_ok, dist, np.nan)
    return out


OPERATOR = Operator(
    name="spectral_shape_change",
    summary=(
        "Gain-free log-spectral distance between the multitaper power spectrum of the last "
        "`window` values and that of the `window` values before them: how much the frequency "
        "content (the balance of slow and fast fluctuations, i.e. the autocorrelation "
        "structure) has changed, irrespective of any change in overall variance. 0 = same "
        "spectral shape, larger = the series' dynamics have changed."
    ),
    inputs=(Series,),
    params=(("window", LongWindow),),
    output=Real,
    lookback=lambda window: int(2 * window),
    missing="propagate",
    definition=(
        "Split the last 2N values (N = window) into the preceding block A and the recent block "
        "B. For each block (demeaned) compute the sine-multitaper spectrum with K = 5 tapers at "
        "the Fourier frequencies j/N, j = 1..floor((N-1)/2), and average it over 8 contiguous "
        "equal-width frequency bands: P_b. Normalise to unit total power, p_b = P_b / sum P, "
        "and take d_b = log p_b^B - log p_b^A. Output: the gain-free log-spectral distance "
        "D = sqrt( (1/8) sum_b (d_b - mean d)^2 ), the standard deviation over bands of the "
        "log spectral ratio. A pure change of variance (gain) leaves D unchanged; D measures "
        "the change of the spectral shape, i.e. of the normalised autocovariance function. "
        "Scale-invariant; NaN if any value in the 2N window is missing."
    ),
    references=(
        "Gray, A. H. and Markel, J. D. (1976). Distance measures for speech processing. IEEE "
        "Transactions on Acoustics, Speech, and Signal Processing 24(5), 380-391.",
        "Thomson, D. J. (1982). Spectrum estimation and harmonic analysis. Proceedings of the "
        "IEEE 70(9), 1055-1096.",
        "Riedel, K. S. and Sidorenko, A. (1995). Minimum bias multiple taper spectral "
        "estimation. IEEE Transactions on Signal Processing 43(1), 188-195.",
        "Basseville, M. (1989). Distance measures for signal processing and pattern "
        "recognition. Signal Processing 18(4), 349-369.",
    ),
    impl=_impl,
    invariances=("scale",),
)
