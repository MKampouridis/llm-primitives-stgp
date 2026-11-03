"""Knock-out contributions of operators to hall-of-fame rules, on the FIT stage only (§4.1).

For a rule that uses operator ``op``, every node of ``op`` in the entry and exit trees is replaced
by its neutral value: for a Real output, the median of that node's own output over the scored FIT
window (a constant series); for a Bool output, "unknown" (NaN, Kleene logic). The rule is scored
again on FIT; the contribution is the drop in fitness F, and per half-year segment the drop in
segment Sharpe. Knocked-out values never enter the run's cache: subtrees containing the operator are computed
in a fresh evaluator; the others are read from the run's evaluator. Computed in the run's worker, right after the GP, so no extra process reads data.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from lpstgp.gp import fitness as fit
from lpstgp.gp.evaluate import TreeEvaluator
from lpstgp.gp.run import Problem
from lpstgp.gp.variation import Rule
from lpstgp.types import Bool

KNOCKOUT_CACHE_BYTES = 64 * 2**20


class KnockoutEvaluator(TreeEvaluator):
    """Evaluates trees with every node named ``target`` replaced by its neutral value."""

    def __init__(self, base: TreeEvaluator, target: str, window: tuple[int, int]) -> None:
        super().__init__(base.lib, base.log_price, base.log_return, KNOCKOUT_CACHE_BYTES)
        self.base = base
        self.target = target
        self.window = window

    def _value(self, tree, i):
        node = tree[i]
        span = tree.searchSubtree(i)
        if all(n.name != self.target for n in tree[span]):
            return self.base._value(tree, i)  # untouched subtree: the run's own (true) values
        out = super()._value(tree, i)
        if node.name != self.target:
            return out
        if self.lib.operators[node.name].output is Bool:
            neutral = np.full(out.shape, np.nan)
        else:
            lo, hi = self.window
            scored = out[lo:hi]
            finite = scored[np.isfinite(scored)]
            median = float(np.median(finite)) if finite.size else np.nan
            neutral = np.where(np.isnan(out), np.nan, median)  # warm-up stays missing
        neutral.setflags(write=False)
        return neutral


def operators_in(rule: Rule, problem: Problem) -> list[str]:
    names = {n.name for tree in rule.trees() for n in tree}
    return sorted(n for n in names if n in problem.lib.operators)


def _segment_sharpes(score: fit.Score, problem: Problem) -> dict[str, list[float]]:
    """Segment Sharpes per instrument; a rule that does not trade there scores 0 in each."""
    out = {}
    for name, c in score.components["instruments"].items():
        n = sum(1 for lo, hi in problem.data[name].segments if hi - lo >= 2)
        values = list(c.get("segment_sharpes", []))
        out[name] = values if len(values) == n else [0.0] * n
    return out


def contributions(
    problem: Problem, rules: Sequence[Rule], targets: Sequence[str] | None = None
) -> list[dict[str, Any]]:
    """Per rule and per operator it uses (restricted to ``targets`` if given): the drop in F and
    in each instrument's segment Sharpes when the operator is knocked out (FIT stage)."""
    out = []
    for rank, rule in enumerate(rules):
        base = problem.score(rule)
        base_seg = _segment_sharpes(base, problem)
        size_w = problem.lib.weighted_size(rule.entry) + problem.lib.weighted_size(rule.exit)
        per_op = {}
        for op in operators_in(rule, problem):
            if targets is not None and op not in targets:
                continue
            signals = {}
            for name, ev in problem.evaluators.items():
                d = problem.data[name]
                ko = KnockoutEvaluator(ev, op, (d.active_from, d.stop))
                signals[name] = (ko(rule.entry), ko(rule.exit))
            knocked = fit.score(signals, problem.data, size_w, problem.cfg)
            seg = _segment_sharpes(knocked, problem)
            per_op[op] = {
                "delta_f": base.fitness - knocked.fitness,
                "delta_segment_sharpe": {
                    name: [a - b for a, b in zip(base_seg[name], seg[name], strict=True)]
                    for name in base_seg
                },
            }
        out.append({"rank": rank, "fitness": base.fitness, "operators": per_op})
    return out
