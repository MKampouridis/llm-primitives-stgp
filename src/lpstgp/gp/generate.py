"""Type-, depth- and lookback-aware random tree generation (replaces DEAP's typed generators).

DEAP's typed ``generate`` fails when a type has no terminal at the depth limit and draws from
unordered type sets. Here every choice is made from ordered lists with a seeded ``random.Random``,
and a node is only chosen if its subtree can still be completed within the remaining depth and the
remaining lookback budget (so every tree fits the global cap L_max).
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass

from deap import gp

from lpstgp.gp.pset import PrimitiveLibrary, param_name
from lpstgp.operators.contract import OperatorSpec

INF = 10**9


class GenerationError(RuntimeError):
    """No tree satisfies the constraints from this position."""


@dataclass(frozen=True)
class Choice:
    node: gp.Primitive
    spec: OperatorSpec
    combos: tuple[tuple[tuple, int], ...]  # (param values in order, lookback)


class Generator:
    def __init__(self, library: PrimitiveLibrary, lookback_max: int, rng: random.Random) -> None:
        self.lib = library
        self.lookback_max = lookback_max
        self.rng = rng
        pset = library.pset
        self.choices: dict[type, list[Choice]] = {}
        self.terminals: dict[type, list[gp.Terminal]] = {}
        for t in library.data_types:
            self.terminals[t] = [n for n in pset.terminals.get(t, []) if not library.is_param(n)]
            options = []
            for node in pset.primitives.get(t, []):
                spec = library.operators[node.name]
                combos = []
                for values in itertools.product(*(p.grid for p in spec.params)):
                    params = dict(zip((p.name for p in spec.params), values, strict=True))
                    combos.append((values, spec.lookback_for(params)))
                options.append(Choice(node, spec, tuple(combos)))
            self.choices[t] = options
        self.min_depth, self.min_lookback = self._minima()

    def _minima(self) -> tuple[dict[type, int], dict[type, int]]:
        depth = {t: (0 if self.terminals[t] else INF) for t in self.lib.data_types}
        look = {
            t: min((n_lb for n_lb in self._terminal_lookbacks(t)), default=INF)
            for t in self.lib.data_types
        }
        changed = True
        while changed:
            changed = False
            for t, options in self.choices.items():
                for c in options:
                    kids = c.spec.inputs
                    d = 1 + max([depth[k] for k in kids] + [0])
                    lb = min(lookback for _, lookback in c.combos) - 1 + max(look[k] for k in kids)
                    if d < depth[t]:
                        depth[t], changed = d, True
                    if lb < look[t]:
                        look[t], changed = lb, True
        return depth, look

    def _terminal_lookbacks(self, t: type) -> list[int]:
        return [self.lib.terminals[n.name].lookback for n in self.terminals[t]]

    # ------------------------------------------------------------------ generation
    def tree(
        self, ret_type: type, max_depth: int, method: str, budget: int | None = None
    ) -> gp.PrimitiveTree:
        nodes: list = []
        self._node(
            nodes, ret_type, 0, max_depth, method, self.lookback_max if budget is None else budget
        )
        return gp.PrimitiveTree(nodes)

    def _feasible(self, ret_type: type, depth: int, max_depth: int, budget: int):
        terms = [
            n for n in self.terminals[ret_type] if self.lib.terminals[n.name].lookback <= budget
        ]
        prims = []
        if depth < max_depth:
            for c in self.choices.get(ret_type, []):
                if depth + 1 + max([self.min_depth[k] for k in c.spec.inputs] + [0]) > max_depth:
                    continue
                child = max(self.min_lookback[k] for k in c.spec.inputs)
                combos = [combo for combo in c.combos if combo[1] - 1 + child <= budget]
                if combos:
                    prims.append((c, combos))
        return terms, prims

    def _node(
        self, out: list, ret_type: type, depth: int, max_depth: int, method: str, budget: int
    ) -> None:
        terms, prims = self._feasible(ret_type, depth, max_depth, budget)
        if not terms and not prims:
            raise GenerationError(
                f"cannot build {ret_type.__name__} at depth {depth} with budget {budget}"
            )
        if method == "full":
            use_prim = bool(prims)
        else:  # grow: terminals and primitives in proportion to how many there are
            use_prim = bool(prims) and (
                not terms or self.rng.random() >= len(terms) / (len(terms) + len(prims))
            )
        if not use_prim:
            out.append(terms[self.rng.randrange(len(terms))])
            return
        choice, combos = prims[self.rng.randrange(len(prims))]
        values, lookback = combos[self.rng.randrange(len(combos))]
        out.append(choice.node)
        child_budget = budget - (lookback - 1)
        for kind in choice.spec.inputs:
            self._node(out, kind, depth + 1, max_depth, method, child_budget)
        for p, value in zip(choice.spec.params, values, strict=True):
            out.append(self.lib.node(param_name(p.kind, value)))

    def ramped(self, ret_type: type, min_depth: int, max_depth: int) -> gp.PrimitiveTree:
        """Ramped half-and-half: a random depth limit and either the full or the grow method."""
        depth = self.rng.randint(min_depth, max_depth)
        method = "full" if self.rng.random() < 0.5 else "grow"
        return self.tree(ret_type, depth, method)
