"""strategy_api: the contract a whole trading strategy implements (pure Python + numpy).

A strategy is a long-only daily rule built from 1 to 4 *signals*:

* A **signal** is a function of the instrument's past data that returns one float per bar
  (``np.float64`` array, same length as the input, ``NaN`` while it cannot be computed yet).
  Its inputs are chosen from ``log_price`` (log of the adjusted close), ``log_return``
  (daily log total return) and ``abs_return`` (``|log_return|``). Its tunable parameters take
  values only from the fixed grids below (``Window(20)`` means "a Window, default 20").
* The **rule** turns the signal arrays into two arrays, ``entry`` and ``exit``, with values in
  {0.0, 1.0, NaN}: 1 = condition true, 0 = false, NaN = unknown (no action). The harness holds a
  long position from an entry until an exit (exit wins when both are 1), trades after the bar's
  close with its own execution delay, and charges per-instrument costs. Do **not** shift signals
  yourself and do not track the position: the rule only states conditions.

Every value at bar ``t`` may depend only on bars ``<= t`` (no look-ahead), must be identical
whatever data follow ``t``, and must not depend on more than ``lookback`` bars of history.
Signals and rule must be deterministic and use only numpy, scipy, math and this module.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

DOMAINS = (
    "information_theory",
    "information_geometry",
    "optimal_transport",
    "rough_paths",
    "fractal",
    "statistical_physics",
    "spectral",
)
INPUTS = ("log_price", "log_return", "abs_return")
MAX_SIGNALS = 4
MAX_LOOKBACK = 504  # bars, signal lookback + rule lookback


# --- parameter grids (identical to the GP's parameter types) -------------------------------------


@dataclass(frozen=True)
class Param:
    """A tunable parameter: one value from ``grid``; ``default`` is the strategy's own choice."""

    default: Any
    grid: tuple = field(default=(), repr=False)
    kind: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if self.default not in self.grid:
            raise ValueError(f"{self.kind}({self.default!r}) is not on its grid {self.grid}")


def _kind(name: str, grid: tuple, description: str) -> Callable[[Any], Param]:
    def make(default: Any) -> Param:
        return Param(default, grid, name)

    make.__name__ = make.__qualname__ = name
    make.grid = grid  # type: ignore[attr-defined]
    make.__doc__ = f"{description}; grid {grid}"
    return make


Window = _kind("Window", (10, 15, 20, 30, 40, 60, 90, 120), "short/medium window (bars)")
LongWindow = _kind("LongWindow", (60, 90, 120, 180, 252), "long window (bars)")
Lag = _kind("Lag", (1, 2, 3, 5, 10), "lag (bars)")
Quantile = _kind("Quantile", (0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95), "quantile level")
KSigma = _kind("KSigma", (-2.0, -1.0, -0.5, 0.5, 1.0, 2.0), "number of standard deviations")
Order = _kind("Order", (3, 4, 5), "embedding dimension / pattern order")
Levels = _kind("Levels", (2, 3, 4), "quantisation levels")
Kmax = _kind("Kmax", (4, 6, 8, 10), "largest scale")
Moment = _kind("Moment", (1.0, 2.0), "moment order q")
QEnt = _kind("QEnt", (0.5, 1.5, 2.0, 3.0), "entropic index q")
Alpha = _kind("Alpha", (-0.5, 0.0, 0.5), "alpha (divergence family)")
Epsilon = _kind("Epsilon", (0.25, 0.5, 1.0), "regularisation strength")
PVar = _kind("PVar", (2.0, 2.5, 3.0), "p of a p-variation")
WLevel = _kind("WLevel", (1, 2, 3, 4), "wavelet detail level")
_ALL_KINDS = (Window, LongWindow, Lag, Quantile, KSigma, Order, Levels, Kmax, Moment, QEnt)
KINDS = {k.__name__: k for k in (*_ALL_KINDS, Alpha, Epsilon, PVar, WLevel)}


# --- the contract ----------------------------------------------------------------------------------

_SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class Signal:
    """``fn(<inputs in order>, *, <params>) -> np.ndarray``; ``lookback(**params) -> int`` bars."""

    name: str
    fn: Callable[..., np.ndarray]
    inputs: tuple[str, ...]
    params: Mapping[str, Param]
    lookback: Callable[..., int]
    description: str = ""

    def __post_init__(self) -> None:
        if not _SNAKE.match(self.name):
            raise ValueError(f"signal name {self.name!r} must be snake_case")
        if not self.inputs or any(i not in INPUTS for i in self.inputs):
            raise ValueError(f"{self.name}: inputs must be a non-empty subset of {INPUTS}")
        if len(set(self.inputs)) != len(self.inputs):
            raise ValueError(f"{self.name}: repeated input")
        for pname, param in self.params.items():
            if not isinstance(param, Param) or not _SNAKE.match(pname):
                raise ValueError(
                    f"{self.name}: parameter {pname!r} must be a grid kind, e.g. Window(20)"
                )
        sig = inspect.signature(self.fn)
        positional = [
            p.name
            for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        keyword = [p.name for p in sig.parameters.values() if p.kind is p.KEYWORD_ONLY]
        if len(positional) != len(self.inputs) or sorted(keyword) != sorted(self.params):
            raise ValueError(
                f"{self.name}: fn must be fn({', '.join(self.inputs)}, *, "
                f"{', '.join(self.params)}) (inputs positional, parameters keyword-only)"
            )
        self.lookback_for(self.defaults)

    @property
    def defaults(self) -> dict[str, Any]:
        return {k: p.default for k, p in self.params.items()}

    def lookback_for(self, params: Mapping[str, Any]) -> int:
        value = self.lookback(**params)
        if not isinstance(value, int | np.integer) or not 0 <= value <= MAX_LOOKBACK:
            raise ValueError(f"{self.name}: lookback must be an int in [0, {MAX_LOOKBACK}]")
        return int(value)

    def __call__(self, data: Mapping[str, np.ndarray], **params: Any) -> np.ndarray:
        values = {**self.defaults, **params}
        for key, value in values.items():
            if value not in self.params[key].grid:
                raise ValueError(f"{self.name}: {key}={value!r} is not on its grid")
        out = self.fn(*(data[i] for i in self.inputs), **values)
        return np.asarray(out, dtype=np.float64)


@dataclass(frozen=True)
class Strategy:
    name: str
    domain: str
    hypothesis: str
    definition: str
    references: tuple[str, ...]
    signals: tuple[Signal, ...]
    rule: Callable[[Mapping[str, np.ndarray]], tuple[np.ndarray, np.ndarray]]
    rule_lookback: int
    novelty: str = ""
    limitations: str = ""

    def __post_init__(self) -> None:
        if not _SNAKE.match(self.name):
            raise ValueError(f"strategy name {self.name!r} must be snake_case")
        if self.domain not in DOMAINS:
            raise ValueError(f"domain must be one of {DOMAINS}")
        if not 1 <= len(self.signals) <= MAX_SIGNALS:
            raise ValueError(f"a strategy has 1 to {MAX_SIGNALS} signals")
        names = [s.name for s in self.signals]
        if len(set(names)) != len(names):
            raise ValueError("signal names must be unique")
        if not isinstance(self.rule_lookback, int) or self.rule_lookback < 0:
            raise ValueError("rule_lookback must be a non-negative int")
        if self.lookback > MAX_LOOKBACK:
            raise ValueError(f"total lookback {self.lookback} exceeds {MAX_LOOKBACK} bars")

    @property
    def lookback(self) -> int:
        """Bars of history the entry/exit at ``t`` may depend on (defaults)."""
        return max(s.lookback_for(s.defaults) for s in self.signals) + self.rule_lookback

    def compute(self, log_price: np.ndarray, log_return: np.ndarray) -> dict[str, np.ndarray]:
        data = {"log_price": log_price, "log_return": log_return, "abs_return": np.abs(log_return)}
        return {s.name: s(data) for s in self.signals}

    def entry_exit(self, signals: Mapping[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
        entry, exit_ = self.rule(signals)
        return np.asarray(entry, dtype=np.float64), np.asarray(exit_, dtype=np.float64)

    def run(self, log_price: np.ndarray, log_return: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return self.entry_exit(self.compute(log_price, log_return))


# --- causal helpers (optional) -------------------------------------------------------------------


def trailing_windows(x: np.ndarray, window: int) -> np.ndarray:
    """``out[t] = x[t-window+1 : t+1]`` as rows of a (T, window) array; rows before ``window-1``
    are NaN. Strictly causal."""
    x = np.asarray(x, dtype=np.float64)
    out = np.full((len(x), window), np.nan)
    if len(x) >= window:
        out[window - 1 :] = np.lib.stride_tricks.sliding_window_view(x, window)
    return out


def rolling_apply(x: np.ndarray, window: int, func: Callable[[np.ndarray], float]) -> np.ndarray:
    """``func`` on each trailing window of ``window`` bars; NaN if the window contains NaN."""
    rows = trailing_windows(x, window)
    out = np.full(len(rows), np.nan)
    for t in range(window - 1, len(rows)):
        row = rows[t]
        if np.all(np.isfinite(row)):
            out[t] = func(row)
    return out


def rolling_mean(x: np.ndarray, window: int) -> np.ndarray:
    return np.mean(trailing_windows(x, window), axis=1)


def rolling_std(x: np.ndarray, window: int) -> np.ndarray:
    """Sample standard deviation (ddof=1) of each trailing window."""
    return np.std(trailing_windows(x, window), axis=1, ddof=1)


def rolling_quantile(x: np.ndarray, window: int, q: float) -> np.ndarray:
    """``q``-quantile of each trailing window (linear interpolation); NaN if any value is NaN."""
    rows = trailing_windows(x, window)
    out = np.full(len(rows), np.nan)
    ok = np.all(np.isfinite(rows), axis=1)
    if ok.any():
        out[ok] = np.quantile(rows[ok], q, axis=1)
    return out
