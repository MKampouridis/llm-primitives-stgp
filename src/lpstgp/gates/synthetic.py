"""Seeded synthetic inputs for the gates (CI has no market data).

Returns follow a GARCH(1,1) with Student-t shocks and a regime switch in volatility, so that
distributional, fractal and spectral operators see non-trivial structure.
"""

from __future__ import annotations

import numpy as np

from lpstgp.types import Bool, Hist, Path, Real, Regime, SemType, Series


def garch_returns(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    omega, alpha, beta = 2e-6, 0.08, 0.9
    shocks = rng.standard_t(5, n) / np.sqrt(5 / 3)
    r = np.empty(n)
    var = omega / (1 - alpha - beta)
    for t in range(n):
        regime = 2.0 if (t // 400) % 2 else 1.0
        r[t] = np.sqrt(var) * shocks[t] * regime
        var = omega + alpha * r[t] ** 2 + beta * var
    return r + 2e-4


def make_input(sem_type: type[SemType], n: int, seed: int, variant: int = 0) -> np.ndarray:
    """One synthetic input of a semantic type; ``variant`` gives distinct inputs of the same type."""
    rng = np.random.default_rng(seed + 1000 * variant)
    if sem_type is Series:
        r = garch_returns(n, seed + variant)
        return np.abs(r) if variant % 2 else r
    if sem_type is Path:
        return np.cumsum(garch_returns(n, seed + 17 * (variant + 1)))
    if sem_type is Hist:
        from lpstgp.operators.core.rolling_hist__v1 import rolling_hist  # constructor of the type

        return rolling_hist(garch_returns(n, seed + 31 * (variant + 1)), (20, 60, 120)[variant % 3])
    if sem_type is Real:
        x = np.empty(n)
        x[0] = 0.0
        e = rng.standard_normal(n)
        for t in range(1, n):
            x[t] = 0.95 * x[t - 1] + e[t]
        x[:30] = np.nan  # warm-up, like a real feature
        return x
    if sem_type is Bool:
        out = (rng.random(n) < 0.4).astype(np.float64)
        out[rng.random(n) < 0.05] = np.nan
        return out
    if sem_type is Regime:
        states = np.repeat(rng.integers(-1, 2, n // 20 + 1).astype(np.float64), 20)[:n]
        states[:25] = np.nan
        return states
    raise TypeError(sem_type)


def adversarial_tail(
    sem_type: type[SemType], tail: int, mode: int, reference: np.ndarray, seed: int
) -> np.ndarray:
    """Bars appended after a cut: spikes, NaN blocks, constants, sharp reversals or regime shifts."""
    rng = np.random.default_rng(seed + mode)
    if sem_type is Hist:
        out = np.zeros((tail, reference.shape[1]))
        if mode % 3 == 0:
            out[:, 0] = 1.0  # all mass in one bin
        elif mode % 3 == 1:
            out[:] = np.nan
        else:
            out[:] = 1.0 / reference.shape[1]
        return out
    scale = np.nanstd(reference) or 1.0
    last = reference[np.isfinite(reference)][-1] if np.isfinite(reference).any() else 0.0
    if sem_type in (Bool, Regime):
        choices = (0.0, 1.0) if sem_type is Bool else (-1.0, 0.0, 1.0)
        return [np.full(tail, choices[-1]), np.full(tail, np.nan), rng.choice(choices, tail)][
            mode % 3
        ]
    if mode % 5 == 0:
        return rng.standard_normal(tail) * 50 * scale + (last if sem_type is Path else 0.0)
    if mode % 5 == 1:
        return np.full(tail, np.nan)
    if mode % 5 == 2:
        return np.full(tail, last)
    if mode % 5 == 3:  # sharp reversal: larger than any DC threshold
        steps = np.where(np.arange(tail) % 2, -0.3, 0.3)
        return last + np.cumsum(steps) if sem_type is Path else steps
    return reference[-tail:] * 10.0 if len(reference) >= tail else np.full(tail, 10.0 * last)
