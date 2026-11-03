"""Phase, at the current bar, of the dominant Fourier harmonic of the detrended log price."""

import numpy as np

from operator_api import Operator, Path, Real, Window


def _impl(p, window):
    p = np.asarray(p, dtype=np.float64)
    T = len(p)
    out = np.full(T, np.nan)
    if T < window:
        return out
    n = window
    W = np.lib.stride_tricks.sliding_window_view(p, n)
    ok = np.all(np.isfinite(W), axis=1)
    W = np.where(ok[:, None], W, 0.0)
    t = np.arange(n, dtype=np.float64)
    tc = t - t.mean()
    slope = (W @ tc) / (tc @ tc)
    R = W - W.mean(axis=1, keepdims=True) - slope[:, None] * tc[None, :]
    kmax = max(1, n // 4)  # periods of at least 4 bars
    Y = np.fft.rfft(R, axis=1)[:, 1 : kmax + 1]
    pw = np.abs(Y) ** 2
    kidx = np.argmax(pw, axis=1)
    k = kidx + 1
    Yk = Y[np.arange(len(Y)), kidx]
    # component of frequency k: (2/n)|Y_k| cos(2 pi k t / n + arg Y_k); phase at t = n - 1
    theta = 2.0 * np.pi * k * (n - 1) / n + np.angle(Yk)
    frac = np.mod(theta - np.pi, 2.0 * np.pi) / (2.0 * np.pi)  # 0 = trough, 0.5 = crest
    good = ok & (pw.max(axis=1) > 0)
    out[n - 1 :] = np.where(good, frac, np.nan)
    return out


OPERATOR = Operator(
    name="dominant_cycle_phase",
    summary=(
        "Harmonic analysis of the linearly detrended log-price window: the phase, at the current "
        "bar, of its strongest Fourier harmonic (period between 4 bars and the window), as a "
        "fraction of the cycle: 0 = at the trough, 0.25 = rising through the mean, "
        "0.5 = at the crest, 0.75 = falling through the mean, back to 1 = trough."
    ),
    inputs=(Path,),
    params=(("window", Window),),
    output=Real,
    lookback=lambda window: int(window),
    missing="propagate",
    definition=(
        "Let y_0..y_{N-1} be the last N = window values of the path, with its least-squares "
        "line removed: r_t = y_t - a - b t. Discrete Fourier transform "
        "Y_k = sum_t r_t exp(-2 pi i k t / N), k = 1..max(1, floor(N/4)) (periods N/k >= 4 "
        "bars). Dominant harmonic k* = argmax_k |Y_k|^2 (the periodogram peak); its least-"
        "squares sinusoid is (2/N)|Y_k*| cos(theta_t) with theta_t = 2 pi k* t / N + arg Y_k*. "
        "Output: the phase at the current bar as a cycle fraction, "
        "phi = ((theta_{N-1} - pi) mod 2 pi) / (2 pi) in [0, 1): 0 at the trough of the "
        "dominant cycle, 0.5 at its crest, values in (0, 0.5) on the rising half and in "
        "(0.5, 1) on the falling half. Invariant to adding a constant (and a linear trend) "
        "and to positive rescaling of the path; NaN if any value in the window is missing."
    ),
    references=(
        "Schuster, A. (1898). On the investigation of hidden periodicities with application to "
        "a supposed 26 day period of meteorological phenomena. Terrestrial Magnetism 3(1), "
        "13-41.",
        "Bloomfield, P. (2000). Fourier Analysis of Time Series: An Introduction, 2nd ed. "
        "Wiley.",
        "Priestley, M. B. (1981). Spectral Analysis and Time Series. Academic Press.",
        "Granger, C. W. J. and Hatanaka, M. (1964). Spectral Analysis of Economic Time Series. "
        "Princeton University Press.",
    ),
    impl=_impl,
    invariances=("shift", "scale"),
)
