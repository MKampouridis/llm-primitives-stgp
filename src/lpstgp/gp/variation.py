"""Variation of entry/exit rule pairs: homologous crossover and four mutation kinds.

Replaces DEAP's ``cxOnePoint`` (which draws the crossover type from an unordered set, so seeded runs
are not reproducible across processes, and which often just swaps parameter leaves). Crossover
points are internal nodes with probability 0.9 and never parameter leaves; the second point is
drawn among nodes of the same type, in tree order. Offspring that break a constraint (depth, size,
lookback) are replaced by an unchanged copy of the parent.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from deap import gp

from lpstgp.gp.generate import GenerationError, Generator
from lpstgp.gp.pset import PrimitiveLibrary


@dataclass(frozen=True)
class Limits:
    max_depth: int = 12
    max_nodes: int = 60
    lookback_max: int = 504


@dataclass
class Rule:
    """An individual: entry and exit Bool trees."""

    entry: gp.PrimitiveTree
    exit: gp.PrimitiveTree
    fitness: float | None = None
    info: dict = field(default_factory=dict)

    def trees(self) -> list[gp.PrimitiveTree]:
        return [self.entry, self.exit]

    def key(self) -> str:
        return f"{self.entry} | {self.exit}"

    def copy(self) -> Rule:
        return Rule(gp.PrimitiveTree(self.entry), gp.PrimitiveTree(self.exit))


def valid(tree: gp.PrimitiveTree, lib: PrimitiveLibrary, limits: Limits) -> bool:
    return (
        len(tree) <= limits.max_nodes
        and tree.height <= limits.max_depth
        and lib.lookback(tree) <= limits.lookback_max
    )


def _points(
    tree: gp.PrimitiveTree, lib: PrimitiveLibrary, ret_type: type | None = None
) -> tuple[list, list]:
    internal, leaves = [], []
    for i, node in enumerate(tree):
        if lib.is_param(node) or (ret_type is not None and node.ret is not ret_type):
            continue
        (internal if node.arity > 0 else leaves).append(i)
    return internal, leaves


def _pick(rng: random.Random, internal: list, leaves: list, p_internal: float = 0.9) -> int | None:
    if internal and (not leaves or rng.random() < p_internal):
        return internal[rng.randrange(len(internal))]
    if leaves:
        return leaves[rng.randrange(len(leaves))]
    return None


def crossover(
    a: Rule, b: Rule, lib: PrimitiveLibrary, limits: Limits, rng: random.Random
) -> tuple[Rule, Rule]:
    """Swap same-type subtrees between the entry trees, or between the exit trees, of two parents."""
    child_a, child_b = a.copy(), b.copy()
    k = rng.randrange(2)
    ta, tb = child_a.trees()[k], child_b.trees()[k]
    i = _pick(rng, *_points(ta, lib))
    if i is None:
        return child_a, child_b
    ret_type = ta[i].ret
    j = _pick(rng, *_points(tb, lib, ret_type))
    if j is None:
        return child_a, child_b
    sa, sb = ta.searchSubtree(i), tb.searchSubtree(j)
    sub_a, sub_b = ta[sa], tb[sb]
    ta[sa], tb[sb] = sub_b, sub_a
    if not valid(ta, lib, limits):
        child_a = a.copy()
    if not valid(tb, lib, limits):
        child_b = b.copy()
    return child_a, child_b


MUTATIONS = (("subtree", 0.5), ("point", 0.2), ("param", 0.2), ("shrink", 0.1))


def mutate(
    rule: Rule, lib: PrimitiveLibrary, gen: Generator, limits: Limits, rng: random.Random
) -> Rule:
    child = rule.copy()
    tree = child.trees()[rng.randrange(2)]
    r, acc, kind = rng.random(), 0.0, MUTATIONS[-1][0]
    for name, p in MUTATIONS:
        acc += p
        if r < acc:
            kind = name
            break
    changed = {"subtree": _subtree, "point": _point, "param": _param, "shrink": _shrink}[kind](
        tree, lib, gen, rng, limits
    )
    if not changed or not valid(tree, lib, limits):
        return rule.copy()
    return child


def _subtree(tree, lib, gen, rng, limits) -> bool:
    internal, leaves = _points(tree, lib)
    candidates = internal + leaves
    if not candidates:
        return False
    i = candidates[rng.randrange(len(candidates))]
    sl = tree.searchSubtree(i)
    depth_here = _depth_of(tree, i)
    # New subtrees are at most 4 deep, and fit the depth and lookback left at node i.
    room = max(0, min(4, limits.max_depth - depth_here))
    budget = limits.lookback_max - lib.ancestor_lookback(tree, i)
    try:
        new = gen.tree(tree[i].ret, room, "grow", budget)
    except GenerationError:
        return False
    tree[sl] = new[:]
    return True


def _depth_of(tree, index: int) -> int:
    stack = [0]
    for i, node in enumerate(tree):
        depth = stack.pop()
        if i == index:
            return depth
        stack.extend([depth + 1] * node.arity)
    return 0


def _point(tree, lib, gen, rng, limits) -> bool:
    internal, leaves = _points(tree, lib)
    candidates = internal + leaves
    if not candidates:
        return False
    i = candidates[rng.randrange(len(candidates))]
    node = tree[i]
    if node.arity == 0:
        options = [n for n in gen.terminals[node.ret] if n.name != node.name]
    else:
        options = [
            c.node
            for c in gen.choices[node.ret]
            if c.node.name != node.name and c.node.args == node.args
        ]
    if not options:
        return False
    tree[i] = options[rng.randrange(len(options))]
    return True


def _param(tree, lib, gen, rng, limits) -> bool:
    params = [i for i, n in enumerate(tree) if lib.is_param(n)]
    if not params:
        return False
    i = params[rng.randrange(len(params))]
    kind = lib.params[tree[i].name][0]
    options = [n for n in lib.pset.terminals[kind] if n.name != tree[i].name]
    if not options:
        return False
    tree[i] = options[rng.randrange(len(options))]
    return True


def _shrink(tree, lib, gen, rng, limits) -> bool:
    """Replace a subtree by one of its own same-type, non-parameter descendants (anti-bloat)."""
    pairs = []
    for i, node in enumerate(tree):
        if node.arity == 0:
            continue
        sl = tree.searchSubtree(i)
        for j in range(i + 1, sl.stop):
            if tree[j].ret is node.ret and not lib.is_param(tree[j]):
                pairs.append((i, j))
    if not pairs:
        return False
    i, j = pairs[rng.randrange(len(pairs))]
    tree[tree.searchSubtree(i)] = tree[tree.searchSubtree(j)]
    return True
