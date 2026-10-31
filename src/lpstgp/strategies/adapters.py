"""Primitive sets for arms 2a, 2b and 2c built from frozen whole strategies (D-037).

* 2a: each strategy's entry and exit as Bool terminals, combined with Kleene And/Or/Not.
* 2b: each signal at the strategy's own parameters as a Real terminal, plus the core glue
  (adaptive thresholds, comparators, logic, regimes).
* 2c: each signal as a typed operator whose grid parameters the GP chooses, applied to the data
  terminals (log price, return, |return|), plus the same core glue.

Terminals compute from the sandbox arrays inside the evaluator, so values are cached per
instrument and stage and stay leakage-safe. Lookbacks are counted in price bars: a strategy's
declared lookback is over its inputs, and a return needs one more price bar.
"""

from __future__ import annotations

import inspect
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from lpstgp import types
from lpstgp.operators.contract import (
    Memory,
    Missing,
    OperatorSpec,
    ParamSpec,
    Provenance,
    TerminalSpec,
)
from lpstgp.operators.registry import discover
from lpstgp.strategies.api import Signal, Strategy

INPUT_TYPES = {"log_price": types.Path, "log_return": types.Series, "abs_return": types.Series}
LOGIC = ("and", "or", "not")
GLUE = (
    *LOGIC,
    "rolling_percentile",
    "mean_ksd",
    "exceeds_quantile",
    "exceeds_ksd",
    "gt",
    "lt",
    "cross_above",
    "cross_below",
    "quantile_regime",
    "regime_is",
)
DATA = ("log_price", "ret", "abs_ret")


@dataclass(frozen=True)
class Frozen:
    """A strategy admitted to the library: id (s01…), file hash and provenance."""

    sid: str
    strategy: Strategy
    sha256: str
    provenance: Provenance


def _core(names: Sequence[str]) -> list[OperatorSpec | TerminalSpec]:
    registry = discover()
    by_name = {spec.name: spec for spec in registry.all().values()}
    return [by_name[name] for name in names]


def _doc(frozen: Frozen) -> tuple[str, tuple[str, ...]]:
    s = frozen.strategy
    return f"{s.name}: {s.definition}", tuple(s.references) or ("(none given)",)


def library_2a(strategies: Sequence[Frozen]) -> list[OperatorSpec | TerminalSpec]:
    specs: list[OperatorSpec | TerminalSpec] = []
    for f in strategies:
        definition, refs = _doc(f)
        for k, side in enumerate(("entry", "exit")):

            def impl(
                lp: np.ndarray, lr: np.ndarray, _s: Strategy = f.strategy, _k: int = k
            ) -> np.ndarray:
                return _s.run(lp, lr)[_k]

            specs.append(
                TerminalSpec(
                    name=f"{f.sid}_{side}",
                    version=1,
                    domain=f.strategy.domain,
                    summary=f"{side} condition of whole strategy {f.sid} ({f.strategy.name})",
                    output=types.Bool,
                    lookback=f.strategy.lookback + 1,
                    missing=Missing.PROPAGATE,
                    definition=definition,
                    references=refs,
                    reference_test="tests/strategies (admission gates)",
                    impl=impl,
                    provenance=f.provenance,
                )
            )
    return specs + _core(LOGIC)


def _terminal(f: Frozen, signal: Signal) -> TerminalSpec:
    def impl(lp: np.ndarray, lr: np.ndarray, _sig: Signal = signal) -> np.ndarray:
        return _sig({"log_price": lp, "log_return": lr, "abs_return": np.abs(lr)})

    definition, refs = _doc(f)
    return TerminalSpec(
        name=f"{f.sid}_{signal.name}",
        version=1,
        domain=f.strategy.domain,
        summary=f"signal {signal.name} of strategy {f.sid} at its own parameters {signal.defaults}",
        output=types.Real,
        lookback=signal.lookback_for(signal.defaults) + 1,
        missing=Missing.PROPAGATE,
        definition=definition,
        references=refs,
        reference_test="tests/strategies (admission gates)",
        impl=impl,
        provenance=f.provenance,
    )


def library_2b(strategies: Sequence[Frozen]) -> list[OperatorSpec | TerminalSpec]:
    terminals = [_terminal(f, s) for f in strategies for s in f.strategy.signals]
    return terminals + _core(GLUE)


def _operator(f: Frozen, signal: Signal) -> OperatorSpec:
    definition, refs = _doc(f)
    order = list(inspect.signature(signal.fn).parameters)[len(signal.inputs) :]  # impl order
    return OperatorSpec(
        name=f"{f.sid}_{signal.name}",
        version=1,
        domain=f.strategy.domain,
        summary=f"signal {signal.name} of strategy {f.sid}, parameters chosen by the GP",
        inputs=tuple(INPUT_TYPES[i] for i in signal.inputs),
        params=tuple(ParamSpec(name, getattr(types, signal.params[name].kind)) for name in order),
        output=types.Real,
        lookback=signal.lookback,
        missing=Missing.PROPAGATE,
        definition=definition,
        references=refs,
        reference_test="tests/strategies (admission gates)",
        impl=signal.fn,
        memory=Memory.FINITE,
        provenance=f.provenance,
    )


def library_2c(strategies: Sequence[Frozen]) -> list[OperatorSpec | TerminalSpec]:
    operators = [_operator(f, s) for f in strategies for s in f.strategy.signals]
    return operators + _core(DATA + GLUE)
