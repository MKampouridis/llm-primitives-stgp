"""Named primitive sets for GP runs: the WP1 registry libraries and the WP2 strategy arms."""

from __future__ import annotations

from collections.abc import Sequence

from lpstgp.operators.contract import OperatorSpec, TerminalSpec
from lpstgp.operators.registry import LIBRARIES, discover
from lpstgp.strategies import adapters
from lpstgp.strategies.adapters import Frozen

STRATEGY_LIBRARIES = {
    "s2a": adapters.library_2a,
    "s2b": adapters.library_2b,
    "s2c": adapters.library_2c,
}
NAMES = (*LIBRARIES, *STRATEGY_LIBRARIES)


def resolve(name: str, frozen: Sequence[Frozen] | None = None) -> list[OperatorSpec | TerminalSpec]:
    """Specs of a named library; strategy arms use ``frozen`` (default: the locked set)."""
    if name in LIBRARIES:
        return discover().library(name)
    if name in STRATEGY_LIBRARIES:
        if frozen is None:
            from lpstgp.strategies.registry import load_frozen

            frozen = load_frozen()
        if not frozen:
            raise ValueError(f"library {name} needs frozen strategies; none are locked yet")
        return STRATEGY_LIBRARIES[name](frozen)
    raise KeyError(f"unknown library {name!r}; known: {NAMES}")
