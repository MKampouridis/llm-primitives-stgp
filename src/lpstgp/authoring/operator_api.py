"""operator_api: the contract a typed operator implements (pure Python + numpy).

An **operator** is one function node of a strongly typed genetic program that evolves long-only
daily trading rules. The program composes operators into an *entry* tree and an *exit* tree,
each of which returns a three-valued truth per bar. An operator takes one or more typed inputs
(per-bar arrays) and zero or more parameters (values from fixed grids), and returns one
**Real** feature per bar. Thresholds, comparisons, logic and regimes are provided by a shared
core library; your operators supply the features those act on.

Semantic types (every array is float64 and has one row per bar, T bars in total):

=========  ===================  ============================================================
Type       Array                Meaning
=========  ===================  ============================================================
Series     float64[T]           increment-like stream: log returns, or absolute log returns
Path       float64[T]           level stream (log price, or a running sum); its level is
                                arbitrary, so an operator taking a Path must not depend on it
                                (declare ``invariances=("shift",)``)
Hist       float64[T, N_BINS]   rolling empirical distribution: each row a probability vector
                                on N_BINS fixed bins of robust z-scores (edges BIN_EDGES), or
                                all NaN
Real       float64[T]           scale-free per-bar feature (NaN while it cannot be computed)
Bool       float64[T]           three-valued truth: 1 true, 0 false, NaN unknown
Regime     float64[T]           categorical state in {-1, 0, 1}, or NaN
=========  ===================  ============================================================

Rules every operator must meet (the ``check`` tool tests all of them):

* **Causal and stable:** the output at bar t uses only inputs at bars <= t, and appending later
  bars never changes outputs already computed.
* **Exact lookback:** ``lookback(**params)`` returns L such that the output at t depends only
  on bars t-L+1 .. t. Bars before that window must not matter at all. L <= 504.
* **Deterministic:** no randomness, no global state, identical results across processes.
* **Typed:** the output is a valid instance of ``output`` (shape, dtype and values).
* **Finite and informative:** after warm-up, outputs on realistic inputs are finite (NaN only
  where the missing-data policy says so) and not constant.
* **Invariances:** "scale" means the output is unchanged when Series/Path inputs are multiplied
  by a positive constant; "shift" means it is unchanged when a constant is added to Path inputs.
  Real features must be scale-free, so an operator with a Series or Path input must declare
  "scale", and one with a Path input also "shift". Declared invariances are tested.
* **Fast:** about a second at most for 1,500 bars at any grid point.
* Use only numpy, scipy, math and this module.

Missing data (``missing``): "propagate" (any NaN in the window gives NaN), "min_valid"
(computed on the valid values when at least ``min_valid`` of the window is valid), or
"elementwise" (pointwise operators: an unknown input gives an unknown output).
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

N_BINS = 16
BIN_EDGES = np.linspace(-4.0, 4.0, N_BINS + 1)  # robust z-scores; the outer bins absorb the tails
MAX_LOOKBACK = 504
MISSING = ("propagate", "min_valid", "elementwise")
INVARIANCES = ("shift", "scale")


class SemType:
    """Base class of the semantic types."""


class Series(SemType):
    """Increment-like stream."""


class Path(SemType):
    """Level stream; consumers must be shift-invariant."""


class Hist(SemType):
    """Rolling empirical distribution on N_BINS fixed bins."""


class Real(SemType):
    """Scale-free per-bar feature."""


class Bool(SemType):
    """Three-valued truth: 1, 0 or NaN."""


class Regime(SemType):
    """Categorical state in {-1, 0, 1}, or NaN."""


SEM_TYPES = (Series, Path, Hist, Real, Bool, Regime)

# --- parameter kinds --------------------------------------------------------------------------

_KIND_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*$")


@dataclass(frozen=True)
class ParamKind:
    """A parameter kind: the genetic program chooses one value from ``grid`` for each use."""

    name: str
    grid: tuple
    description: str

    def __post_init__(self) -> None:
        if not _KIND_NAME.match(self.name):
            raise ValueError(f"parameter kind {self.name!r} must be CamelCase")
        values = tuple(self.grid)
        if not 2 <= len(values) <= 9 or len(set(values)) != len(values):
            raise ValueError(f"{self.name}: a grid has 2 to 9 distinct values")
        if not (
            all(isinstance(v, int) and not isinstance(v, bool) for v in values)
            or all(isinstance(v, float) for v in values)
        ):
            raise ValueError(f"{self.name}: grid values must be all int or all float")
        if list(values) != sorted(values):
            raise ValueError(f"{self.name}: list the grid in increasing order")


Window = ParamKind("Window", (10, 15, 20, 30, 40, 60, 90, 120), "short/medium window (bars)")
LongWindow = ParamKind("LongWindow", (60, 90, 120, 180, 252), "long window (bars)")
Lag = ParamKind("Lag", (1, 2, 3, 5, 10), "lag (bars)")
Quantile = ParamKind("Quantile", (0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95), "quantile")
KSigma = ParamKind("KSigma", (-2.0, -1.0, -0.5, 0.5, 1.0, 2.0), "number of standard deviations")
STANDARD_KINDS = (Window, LongWindow, Lag, Quantile, KSigma)


def param_kind(name: str, grid: tuple, description: str) -> ParamKind:
    """Declare a new parameter kind (CamelCase name, 2 to 9 increasing values, all int or all
    float). Prefer a standard kind when one fits. A kind used by several operators must have
    the same grid everywhere."""
    if any(name == k.name for k in STANDARD_KINDS):
        raise ValueError(f"{name} is a standard kind; use it directly")
    return ParamKind(name, tuple(grid), description)


# --- the contract -----------------------------------------------------------------------------

_SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class Operator:
    """One operator. ``impl(<inputs, in order>, <params, by name>) -> np.ndarray``.

    ``params`` is a tuple of (name, kind) pairs; ``lookback`` takes the parameters as keyword
    arguments and returns an int. ``definition`` gives the mathematics (formulas welcome);
    ``references`` are real, verifiable sources.
    """

    name: str
    summary: str
    inputs: tuple[type[SemType], ...]
    params: tuple[tuple[str, ParamKind], ...]
    output: type[SemType]
    lookback: Callable[..., int]
    missing: str
    definition: str
    references: tuple[str, ...]
    impl: Callable[..., np.ndarray]
    min_valid: float = 1.0
    invariances: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _SNAKE.match(self.name):
            raise ValueError(f"operator name {self.name!r} must be snake_case")
        if not self.inputs or any(t not in SEM_TYPES for t in self.inputs):
            raise ValueError(f"{self.name}: inputs must be semantic types, at least one")
        if self.output is not Real:
            raise ValueError(f"{self.name}: the output must be Real")
        for pname, kind in self.params:
            if not _SNAKE.match(pname) or not isinstance(kind, ParamKind):
                raise ValueError(f"{self.name}: params are (snake_case name, ParamKind) pairs")
        if self.missing not in MISSING:
            raise ValueError(f"{self.name}: missing must be one of {MISSING}")
        if not 0.0 < self.min_valid <= 1.0:
            raise ValueError(f"{self.name}: min_valid must be in (0, 1]")
        if not set(self.invariances) <= set(INVARIANCES):
            raise ValueError(f"{self.name}: invariances must be among {INVARIANCES}")
        if Path in self.inputs and "shift" not in self.invariances:
            raise ValueError(f"{self.name}: an operator with a Path input must be shift-invariant")
        if {Series, Path} & set(self.inputs) and "scale" not in self.invariances:
            raise ValueError(f"{self.name}: with a Series or Path input it must be scale-invariant")
        if not self.summary or not self.definition or not self.references:
            raise ValueError(f"{self.name}: give a summary, a definition and references")
        names = list(inspect.signature(self.impl).parameters)
        if names[len(self.inputs) :] != [p for p, _ in self.params]:
            raise ValueError(
                f"{self.name}: impl must take the inputs first, then the parameters "
                f"{[p for p, _ in self.params]} in that order"
            )
        for point in self.extremes():
            value = self.lookback(**point)
            if not isinstance(value, int | np.integer) or not 1 <= value <= MAX_LOOKBACK:
                raise ValueError(f"{self.name}: lookback must be an int in [1, {MAX_LOOKBACK}]")

    def extremes(self) -> list[dict[str, Any]]:
        if not self.params:
            return [{}]
        return [
            {p: min(k.grid) for p, k in self.params},
            {p: max(k.grid) for p, k in self.params},
        ]


# --- causal helper (optional) -------------------------------------------------------------------


def trailing_windows(x: np.ndarray, window: int) -> np.ndarray:
    """``out[t] = x[t-window+1 : t+1]`` as rows of a (T, window) array; earlier rows are NaN."""
    x = np.asarray(x, dtype=np.float64)
    out = np.full((len(x), window), np.nan)
    if len(x) >= window:
        out[window - 1 :] = np.lib.stride_tricks.sliding_window_view(x, window)
    return out
