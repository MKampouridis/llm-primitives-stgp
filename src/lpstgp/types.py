"""Semantic types of the STGP and the parameter kinds.

Every node value is a per-bar array aligned with the sandbox bars:

=========  =====================  ==========================================================
Type       Array                  Meaning
=========  =====================  ==========================================================
Series     float64[T]             increment-like stream (log total return, |log return|)
Path       float64[T]             level stream (log price); operators use it shift-invariantly
Hist       float64[T, N_BINS]     rolling distribution on fixed bins (rows sum to 1, or NaN)
Real       float64[T]             scale-free per-bar feature (NaN during warm-up)
Bool       float64[T] {0,1,NaN}   Kleene three-valued truth; NaN = unknown -> no action
Regime     float64[T] {-1,0,1,NaN}  categorical state
=========  =====================  ==========================================================

Parameters are typed terminals on fixed grids (no ephemeral constants), so every parameter
value a rule can use is enumerable and reproducible. The classes double as DEAP type tags.
"""

from __future__ import annotations

import numpy as np

N_BINS = 16
BIN_EDGES = np.linspace(-4.0, 4.0, N_BINS + 1)  # robust z-scores; outer bins absorb the tails


class SemType:
    """Base class of the semantic types (used as DEAP type tags)."""

    ndim = 1


class Series(SemType):
    """Increment-like stream."""


class Path(SemType):
    """Level stream (cumulative); consumers must be shift-invariant."""


class Hist(SemType):
    """Rolling empirical distribution on ``N_BINS`` fixed bins."""

    ndim = 2


class Real(SemType):
    """Scale-free per-bar feature."""


class Bool(SemType):
    """Kleene three-valued signal: 1 true, 0 false, NaN unknown."""


class Regime(SemType):
    """Categorical state in {-1, 0, 1} (NaN unknown)."""


SEM_TYPES: tuple[type[SemType], ...] = (Series, Path, Hist, Real, Bool, Regime)


class Param:
    """Base class of parameter kinds; ``grid`` is the full set of legal values."""

    grid: tuple = ()
    description = ""


class Window(Param):
    grid = (10, 15, 20, 30, 40, 60, 90, 120)
    description = "short/medium rolling window (bars)"


class LongWindow(Param):
    grid = (60, 90, 120, 180, 252)
    description = "long rolling window (bars)"


class Lag(Param):
    grid = (1, 2, 3, 5, 10)
    description = "lag (bars)"


class Quantile(Param):
    grid = (0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95)
    description = "quantile level"


class KSigma(Param):
    grid = (-2.0, -1.0, -0.5, 0.5, 1.0, 2.0)
    description = "number of standard deviations"


class Order(Param):
    grid = (3, 4, 5)
    description = "embedding dimension of ordinal patterns"


class Levels(Param):
    grid = (2, 3, 4)
    description = "quantisation levels"


class Kmax(Param):
    grid = (4, 6, 8, 10)
    description = "largest Higuchi scale"


class Moment(Param):
    grid = (1.0, 2.0)
    description = "moment order q"


class QEnt(Param):
    grid = (0.5, 1.5, 2.0, 3.0)
    description = "Tsallis entropic index q"


class Alpha(Param):
    grid = (-0.5, 0.0, 0.5)
    description = "Amari alpha"


class Epsilon(Param):
    grid = (0.05, 0.1, 0.5)
    description = "entropic regularisation (squared z-score units)"


class PVar(Param):
    grid = (2.0, 2.5, 3.0)
    description = "p of the p-variation"


class WLevel(Param):
    grid = (1, 2, 3, 4)
    description = "wavelet detail level"


class RegimeState(Param):
    grid = (-1.0, 0.0, 1.0)
    description = "regime label"


PARAM_KINDS: tuple[type[Param], ...] = (
    Window,
    LongWindow,
    Lag,
    Quantile,
    KSigma,
    Order,
    Levels,
    Kmax,
    Moment,
    QEnt,
    Alpha,
    Epsilon,
    PVar,
    WLevel,
    RegimeState,
)


def validate(sem_type: type[SemType], value: object, length: int) -> list[str]:
    """Problems with ``value`` as an instance of ``sem_type`` for ``length`` bars (empty = valid)."""
    if not isinstance(value, np.ndarray):
        return [f"expected numpy array, got {type(value).__name__}"]
    if value.dtype != np.float64:
        return [f"expected float64, got {value.dtype}"]
    shape = (length, N_BINS) if sem_type is Hist else (length,)
    if value.shape != shape:
        return [f"expected shape {shape}, got {value.shape}"]
    problems = []
    if sem_type is Bool:
        finite = value[~np.isnan(value)]
        if not np.isin(finite, (0.0, 1.0)).all():
            problems.append("Bool values must be 0, 1 or NaN")
    elif sem_type is Regime:
        finite = value[~np.isnan(value)]
        if not np.isin(finite, (-1.0, 0.0, 1.0)).all():
            problems.append("Regime values must be -1, 0, 1 or NaN")
    elif sem_type is Hist:
        rows_nan = np.isnan(value).any(axis=1)
        if (np.isnan(value[rows_nan]).sum(axis=1) != N_BINS).any():
            problems.append("Hist rows must be all-NaN or fully defined")
        ok = value[~rows_nan]
        if (ok < 0).any() or not np.allclose(ok.sum(axis=1), 1.0, atol=1e-9):
            problems.append("Hist rows must be probability vectors")
    else:
        if np.isinf(value).any():
            problems.append("infinite values")
    return problems
