"""Operator contract: a typed, versioned, documented primitive of the STGP function set.

``OperatorSpec`` describes a function node (inputs are child values); ``TerminalSpec`` a leaf
computed from the sandbox bars (data streams, conventional indicators). Both carry:
name; immutable integer version; semantic types; parameters with legal grids; lookback (bars, so
output at bar t depends only on inputs at t-L+1..t) and earliest availability; missing-data
policy; mathematical definition with references; the reference used in tests; provenance;
implementation. A modified implementation must be a new version (enforced by the version lock).
"""

from __future__ import annotations

import inspect
import itertools
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

from lpstgp.types import Param, SemType

DOMAINS = (
    "data",
    "core",
    "information_theory",
    "information_geometry",
    "optimal_transport",
    "rough_paths",
    "fractal",
    "statistical_physics",
    "spectral",
    "technical",
    "directional_change",
)
CROSS_DOMAINS = DOMAINS[2:9]
INVARIANCES = ("shift", "scale")


class Missing(Enum):
    PROPAGATE = "propagate"  # any NaN in the window -> NaN
    MIN_VALID = (
        "min_valid"  # computed on the valid values if at least `min_valid` of the window is valid
    )
    ELEMENTWISE = "elementwise"  # pointwise; unknown in -> unknown out (Kleene for Bool)


class Memory(Enum):
    FINITE = "finite"  # output at t depends only on the last `lookback` bars (checked exactly)
    CUMULATIVE = "cumulative"  # a level (path); only shift-invariant consumers may use it


@dataclass(frozen=True)
class ParamSpec:
    name: str
    kind: type[Param]

    @property
    def grid(self) -> tuple:
        return self.kind.grid


@dataclass(frozen=True)
class Provenance:
    implemented_by: str
    specified_by: str
    date: str
    reviewed_by: str | None = None
    review_minutes: float | None = None


# The WP1 seed library is arm 6 (expert-specified, AI-assisted, expert-verified); see docs/decisions.md.
ARM6 = Provenance(
    implemented_by="Claude Code (claude-opus-5-5), WP1 session",
    specified_by="Research plan domain list (PI)",
    date="2026-10-30",
)

_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def _camel(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


@dataclass(frozen=True)
class OperatorSpec:
    name: str
    version: int
    domain: str
    summary: str
    inputs: tuple[type[SemType], ...]
    params: tuple[ParamSpec, ...]
    output: type[SemType]
    lookback: Callable[..., int]
    missing: Missing
    definition: str
    references: tuple[str, ...]
    reference_test: str
    impl: Callable[..., np.ndarray]
    min_valid: float = 1.0
    invariances: tuple[str, ...] = ()
    size_weight: int = 1
    memory: Memory = Memory.FINITE
    tolerance: float = 0.0
    provenance: Provenance = ARM6

    def __post_init__(self) -> None:
        if not _NAME.match(self.name):
            raise ValueError(f"operator name {self.name!r} must be snake_case")
        if self.domain not in DOMAINS or self.version < 1 or not self.inputs:
            raise ValueError(f"{self.name}: bad domain, version or inputs")
        if not set(self.invariances) <= set(INVARIANCES):
            raise ValueError(f"{self.name}: unknown invariances {self.invariances}")
        expected = [p.name for p in self.params]
        signature = list(inspect.signature(self.impl).parameters)[len(self.inputs) :]
        if signature != expected:
            raise ValueError(f"{self.name}: impl parameters {signature} != spec {expected}")

    @property
    def key(self) -> str:
        return f"{self.name}@{self.version}"

    @property
    def gp_name(self) -> str:
        return f"{_camel(self.name)}_v{self.version}"

    @property
    def arity(self) -> int:
        return len(self.inputs) + len(self.params)

    def lookback_for(self, params: Mapping[str, Any]) -> int:
        return int(self.lookback(**params))

    def earliest(self, params: Mapping[str, Any]) -> int:
        """Index of the first possibly-valid output when every input is valid from bar 0."""
        return self.lookback_for(params) - 1

    def check_params(self, params: Mapping[str, Any]) -> None:
        for p in self.params:
            if params[p.name] not in p.grid:
                raise ValueError(f"{self.key}: {p.name}={params[p.name]!r} not in {p.grid}")

    def __call__(self, *inputs: np.ndarray, **params: Any) -> np.ndarray:
        self.check_params(params)
        return self.impl(*inputs, **params)

    def param_grid(self) -> Iterator[dict[str, Any]]:
        names = [p.name for p in self.params]
        for values in itertools.product(*(p.grid for p in self.params)):
            yield dict(zip(names, values, strict=True))


@dataclass(frozen=True)
class TerminalSpec:
    """A leaf computed from the bars: ``impl(log_price, log_return) -> array``."""

    name: str
    version: int
    domain: str
    summary: str
    output: type[SemType]
    lookback: int
    missing: Missing
    definition: str
    references: tuple[str, ...]
    reference_test: str
    impl: Callable[[np.ndarray, np.ndarray], np.ndarray]
    size_weight: int = 1
    memory: Memory = Memory.FINITE
    tolerance: float = 0.0
    provenance: Provenance = ARM6

    def __post_init__(self) -> None:
        if not re.match(r"^[a-z][a-z0-9_]*$", self.name) or self.domain not in DOMAINS:
            raise ValueError(f"bad terminal {self.name!r} / {self.domain!r}")

    @property
    def key(self) -> str:
        return f"{self.name}@{self.version}"

    @property
    def gp_name(self) -> str:
        return f"{_camel(self.name)}_v{self.version}"

    def earliest(self) -> int:
        return self.lookback - 1

    def __call__(self, log_price: np.ndarray, log_return: np.ndarray) -> np.ndarray:
        return self.impl(log_price, log_return)
