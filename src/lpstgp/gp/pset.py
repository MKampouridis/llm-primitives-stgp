"""DEAP strongly typed primitive set built from operator contracts, plus the tree bookkeeping.

DEAP supplies the typed registry and the prefix-list trees. Trees are never compiled with DEAP's
string ``eval``: ``evaluate.py`` interprets them. Parameters are typed terminals on their fixed grids
(no ephemeral constants), named ``<Kind>_<value>``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from deap import gp

from lpstgp.operators.contract import OperatorSpec, TerminalSpec
from lpstgp.types import Bool, Param, SemType


def param_name(kind: type[Param], value: float) -> str:
    text = f"{value:g}".replace("-", "m").replace(".", "p")
    return f"{kind.__name__}_{text}"


def _not_compiled(*args: Any) -> None:
    raise RuntimeError("STGP trees are interpreted by lpstgp.gp.evaluate, not compiled")


@dataclass
class PrimitiveLibrary:
    """A primitive set and lookup tables keyed by node name."""

    name: str
    pset: gp.PrimitiveSetTyped
    operators: dict[str, OperatorSpec]
    terminals: dict[str, TerminalSpec]
    params: dict[str, tuple[type[Param], Any]]
    data_types: tuple[type[SemType], ...] = field(default=())

    def node(self, name: str) -> gp.Primitive | gp.Terminal:
        return self.pset.mapping[name]

    def is_param(self, node: gp.Primitive | gp.Terminal) -> bool:
        return node.arity == 0 and node.name in self.params

    def size_weight(self, node: gp.Primitive | gp.Terminal) -> int:
        if node.name in self.params:
            return 0
        if node.name in self.operators:
            return self.operators[node.name].size_weight
        return self.terminals[node.name].size_weight

    def weighted_size(self, tree: Sequence) -> int:
        return sum(self.size_weight(n) for n in tree)

    def lookback(self, tree: Sequence, begin: int = 0) -> int:
        """Bars of history the subtree at ``begin`` needs (its output at t uses t-L+1..t)."""
        value, _ = self._lookback(tree, begin)
        return value

    def _lookback(self, tree: Sequence, i: int) -> tuple[int, int]:
        node = tree[i]
        if node.arity == 0:
            if node.name in self.params:
                return 0, i + 1
            return self.terminals[node.name].lookback, i + 1
        spec = self.operators[node.name]
        j = i + 1
        child = 0
        values = []
        for k in range(node.arity):
            if k < len(spec.inputs):
                lb, j = self._lookback(tree, j)
                child = max(child, lb)
            else:
                values.append(self.params[tree[j].name][1])
                j += 1
        params = dict(zip((p.name for p in spec.params), values, strict=True))
        return spec.lookback_for(params) - 1 + child, j

    def to_names(self, tree: Sequence) -> list[str]:
        return [n.name for n in tree]

    def from_names(self, names: Iterable[str]) -> gp.PrimitiveTree:
        return gp.PrimitiveTree([self.node(n) for n in names])


def build(specs: Iterable[OperatorSpec | TerminalSpec], name: str = "rule") -> PrimitiveLibrary:
    """Primitive set over the given contracts; insertion order is sorted, so it is deterministic."""
    pset = gp.PrimitiveSetTyped(name, [], Bool)
    operators: dict[str, OperatorSpec] = {}
    terminals: dict[str, TerminalSpec] = {}
    kinds: list[type[Param]] = []
    data_types: list[type[SemType]] = []
    for spec in sorted(specs, key=lambda s: s.key):
        if isinstance(spec, OperatorSpec):
            in_types = list(spec.inputs) + [p.kind for p in spec.params]
            pset.addPrimitive(_not_compiled, in_types, spec.output, name=spec.gp_name)
            operators[spec.gp_name] = spec
            for t in (*spec.inputs, spec.output):
                if t not in data_types:
                    data_types.append(t)
            for p in spec.params:
                if p.kind not in kinds:
                    kinds.append(p.kind)
        else:
            pset.addTerminal(spec.gp_name, spec.output, name=spec.gp_name)
            terminals[spec.gp_name] = spec
            if spec.output not in data_types:
                data_types.append(spec.output)
    params: dict[str, tuple[type[Param], Any]] = {}
    for kind in kinds:
        for value in kind.grid:
            label = param_name(kind, value)
            pset.addTerminal(value, kind, name=label)
            params[label] = (kind, value)
    return PrimitiveLibrary(name, pset, operators, terminals, params, tuple(data_types))
