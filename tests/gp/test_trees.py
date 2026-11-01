"""Primitive sets, tree generation and variation."""

import random

import pytest

from lpstgp.gp.generate import INF, GenerationError, Generator
from lpstgp.gp.variation import Limits, Rule, crossover, mutate, valid
from lpstgp.types import Bool, Hist, Path, Real, Series

LIMITS = Limits()


def well_typed(tree, lib) -> bool:
    """Every primitive's children have the argument types it declares."""
    for i, node in enumerate(tree):
        if node.arity == 0:
            continue
        j = i + 1
        for arg_type in node.args:
            if tree[j].ret is not arg_type:
                return False
            j = tree.searchSubtree(j).stop
    return tree[0].ret is Bool


@pytest.mark.parametrize("name", ["seed_lib", "conventional_lib"])
def test_every_type_is_producible(request, name):
    lib = request.getfixturevalue(name)
    gen = Generator(lib, 504, random.Random(0))
    assert gen.min_depth[Bool] < INF
    for t in lib.data_types:
        assert gen.min_depth[t] < INF, t
        assert gen.min_lookback[t] <= 504, t


def test_parameter_terminals_and_names(seed_lib):
    names = [n.name for nodes in seed_lib.pset.terminals.values() for n in nodes]
    names += [n.name for nodes in seed_lib.pset.primitives.values() for n in nodes]
    assert len(names) == len(set(names))
    assert seed_lib.params["Window_20"][1] == 20
    assert seed_lib.params["KSigma_m0p5"][1] == -0.5


def test_lookback_of_a_hand_built_tree(seed_lib):
    names = [
        "ExceedsQuantile_v1",
        "ShannonEntropy_v1",
        "RollingHist_v1",
        "Ret_v1",
        "Window_20",
        "LongWindow_60",
        "Quantile_0p8",
    ]
    tree = seed_lib.from_names(names)
    # RollingHist: 252 bars (robust scale) on Ret (2 bars) -> 253; ExceedsQuantile adds 60 - 1
    assert seed_lib.lookback(tree) == 252 - 1 + 2 + 60 - 1
    assert seed_lib.weighted_size(tree) == 2  # constructors, data terminals and parameters weigh 0


@pytest.mark.parametrize("name", ["seed_lib", "conventional_lib"])
def test_generated_trees_are_valid_and_reproducible(request, name):
    lib = request.getfixturevalue(name)
    trees = []
    for seed in (1, 1, 2):
        gen = Generator(lib, 504, random.Random(seed))
        trees.append([str(gen.ramped(Bool, 2, 6)) for _ in range(60)])
    assert trees[0] == trees[1]
    assert trees[0] != trees[2]
    gen = Generator(lib, 504, random.Random(3))
    for _ in range(300):
        tree = gen.ramped(Bool, 2, 6)
        assert well_typed(tree, lib)
        assert tree.height <= 6
        assert lib.lookback(tree) <= 504


def test_generation_respects_a_tight_lookback_budget(seed_lib):
    gen = Generator(seed_lib, 504, random.Random(4))
    for _ in range(100):
        tree = gen.tree(Real, 4, "grow", budget=130)
        assert seed_lib.lookback(tree) <= 130
    with pytest.raises(GenerationError):
        gen.tree(Hist, 3, "full", budget=10)  # a histogram needs 252 bars of scale


def test_full_method_reaches_the_depth_when_possible(seed_lib):
    gen = Generator(seed_lib, 504, random.Random(5))
    heights = [gen.tree(Bool, 4, "full").height for _ in range(50)]
    assert max(heights) == 4


@pytest.mark.parametrize("name", ["seed_lib", "conventional_lib"])
def test_variation_keeps_offspring_valid_and_is_reproducible(request, name):
    lib = request.getfixturevalue(name)

    def offspring(seed):
        rng = random.Random(seed)
        gen = Generator(lib, 504, rng)
        rules = [Rule(gen.ramped(Bool, 2, 5), gen.ramped(Bool, 2, 5)) for _ in range(40)]
        out = []
        for k in range(0, 40, 2):
            a, b = crossover(rules[k], rules[k + 1], lib, LIMITS, rng)
            out += [mutate(a, lib, gen, LIMITS, rng), mutate(b, lib, gen, LIMITS, rng)]
        return out

    first, again = offspring(7), offspring(7)
    assert [r.key() for r in first] == [r.key() for r in again]
    for rule in first:
        for tree in rule.trees():
            assert well_typed(tree, lib)
            assert valid(tree, lib, LIMITS)


def test_crossover_is_homologous(seed_lib):
    rng = random.Random(11)
    gen = Generator(seed_lib, 504, rng)
    for _ in range(50):
        a = Rule(gen.ramped(Bool, 2, 4), gen.ramped(Bool, 2, 4))
        b = Rule(gen.ramped(Bool, 2, 4), gen.ramped(Bool, 2, 4))
        child, _ = crossover(a, b, seed_lib, LIMITS, rng)
        # only one of the two trees changes, and it changes into a mix of the same tree of both parents
        assert str(child.entry) == str(a.entry) or str(child.exit) == str(a.exit)


def test_types_used_by_the_seed_library(seed_lib):
    assert {Series, Path, Hist, Real, Bool} <= set(seed_lib.data_types)


def test_subtree_mutation_respects_the_lookback_left_by_ancestors(seed_lib):
    """A replacement subtree fits the depth and lookback left at its node, so depth and lookback
    never make a subtree mutation invalid (only the node count can)."""
    from deap import gp

    from lpstgp.gp.variation import _subtree

    limits = Limits()
    rng = random.Random(3)
    gen = Generator(seed_lib, limits.lookback_max, rng)
    mutated = 0
    for _ in range(400):
        tree = gen.ramped(Bool, 9, 12)
        assert seed_lib.ancestor_lookback(tree, 0) == 0
        for i, node in enumerate(tree):
            if not seed_lib.is_param(node):
                assert 0 <= seed_lib.ancestor_lookback(tree, i) <= seed_lib.lookback(tree)
        child = Rule(tree, gp.PrimitiveTree(tree)).copy()
        if _subtree(child.entry, seed_lib, gen, rng, limits):
            mutated += 1
            assert child.entry.height <= limits.max_depth
            assert seed_lib.lookback(child.entry) <= limits.lookback_max
    assert mutated > 300
