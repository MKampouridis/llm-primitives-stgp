"""Shared helpers: per-window spectra computed independently for every bar (prefix-safe)."""

import numpy as np


def windows(x: np.ndarray, window: int) -> np.ndarray:
    """Read-only (n - window + 1, window) view: row i is the window ending at bar i + window - 1."""
    return np.lib.stride_tricks.sliding_window_view(x, window)


def periodogram_rows(rows: np.ndarray) -> np.ndarray:
    """One-sided periodogram (scipy 'density' weights up to a constant) of each demeaned row."""
    n = rows.shape[1]
    spec = np.abs(np.fft.rfft(rows - rows.mean(axis=1, keepdims=True), axis=1)) ** 2
    if n % 2 == 0:
        spec[:, 1:-1] *= 2.0
    else:
        spec[:, 1:] *= 2.0
    return spec


def place(values: np.ndarray, rows: np.ndarray, n: int, window: int) -> np.ndarray:
    """Full-length output with NaN warm-up and NaN where a window contains NaN."""
    out = np.full(n, np.nan)
    values = np.asarray(values, dtype=np.float64)
    values[np.isnan(rows).any(axis=1)] = np.nan
    out[window - 1 :] = values
    return out
