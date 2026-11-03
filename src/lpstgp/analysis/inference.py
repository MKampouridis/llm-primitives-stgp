"""Paired inference on portfolio Sharpe differences (D-033; protocol, confirmatory test).

``paired_bootstrap`` resamples *days* with the stationary bootstrap of Politis & Romano (1994)
(geometric block lengths, mean ``block``), applying the same resampled days to both portfolios,
so the comparison is paired and keeps short-range dependence. ``holm`` adjusts a family of
p-values (Holm 1979).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from lpstgp.backtest.metrics import sharpe


def stationary_indices(n: int, block: float, rng: np.random.Generator) -> np.ndarray:
    """One stationary-bootstrap resample of ``range(n)`` (wrapping), mean block length ``block``."""
    p = 1.0 / block
    idx = np.empty(n, dtype=np.int64)
    idx[0] = rng.integers(n)
    starts = rng.random(n) < p
    jumps = rng.integers(n, size=n)
    for t in range(1, n):
        idx[t] = jumps[t] if starts[t] else (idx[t - 1] + 1) % n
    return idx


@dataclass(frozen=True)
class PairedResult:
    difference: float  # Sharpe(a) - Sharpe(b) on the observed days
    ci_low: float
    ci_high: float
    p_value: float  # two-sided, from the bootstrap distribution centred at the observed value
    resamples: int


def paired_bootstrap(
    a: np.ndarray,
    b: np.ndarray,
    periods_per_year: float = 252,
    block: float = 10.0,
    resamples: int = 10_000,
    seed: int = 0,
    level: float = 0.95,
) -> PairedResult:
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        raise ValueError("paired series must have the same days")
    observed = float(sharpe(a, periods_per_year) - sharpe(b, periods_per_year))
    rng = np.random.default_rng(seed)
    diffs = np.empty(resamples)
    for k in range(resamples):
        idx = stationary_indices(len(a), block, rng)
        diffs[k] = sharpe(a[idx], periods_per_year) - sharpe(b[idx], periods_per_year)
    lo, hi = np.quantile(diffs, [(1 - level) / 2, (1 + level) / 2])
    centred = diffs - diffs.mean()
    p = float(np.mean(np.abs(centred) >= abs(observed)))
    return PairedResult(observed, float(lo), float(hi), p, resamples)


@dataclass(frozen=True)
class OneSidedResult:
    difference: float  # Sharpe(a) - Sharpe(b) on the observed days
    margin: float  # H0: difference <= margin; 0 for superiority, -m for non-inferiority
    ci_low: float  # one-sided lower confidence bound at ``level``
    p_value: float  # one-sided, from the bootstrap distribution centred at the observed value
    resamples: int


def one_sided_bootstrap(
    a: np.ndarray,
    b: np.ndarray,
    margin: float = 0.0,
    periods_per_year: float = 252,
    block: float = 10.0,
    resamples: int = 10_000,
    seed: int = 0,
    level: float = 0.95,
) -> OneSidedResult:
    """Paired stationary bootstrap test of H0: Sharpe(a) - Sharpe(b) <= ``margin`` against
    H1: it is larger (protocol_wp4 §7; D-078). The same resampled days are applied to both."""
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        raise ValueError("paired series must have the same days")
    observed = float(sharpe(a, periods_per_year) - sharpe(b, periods_per_year))
    rng = np.random.default_rng(seed)
    diffs = np.empty(resamples)
    for k in range(resamples):
        idx = stationary_indices(len(a), block, rng)
        diffs[k] = sharpe(a[idx], periods_per_year) - sharpe(b[idx], periods_per_year)
    centred = diffs - diffs.mean()  # the null distribution's shape, shifted to the margin
    p = float(np.mean(centred >= observed - margin))
    lower = float(observed - np.quantile(centred, level))
    return OneSidedResult(observed, margin, lower, p, resamples)


def holm(p_values: Sequence[float]) -> np.ndarray:
    """Holm-adjusted p-values (monotone, capped at 1), in the input order."""
    p = np.asarray(p_values, dtype=np.float64)
    order = np.argsort(p)
    m = len(p)
    adjusted = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * p[i])
        adjusted[i] = min(1.0, running)
    return adjusted
