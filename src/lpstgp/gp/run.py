"""The STGP run: generational GP over entry/exit rule pairs with elitism and a hall of fame.

All randomness comes from one ``random.Random(seed)``; selection, variation and generation iterate
over ordered lists only, so a seed reproduces a run bit for bit across processes. The hall of fame
keeps the best rules with distinct fit-period signals (rules that trade identically are duplicates).
The final rule is the hall-of-fame member with the best validation score (``final_selection =
"validation"``) or the best fit score (``"fit"``); one rule per run.
"""

from __future__ import annotations

import math
import random
import statistics
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import date

import numpy as np

from lpstgp.backtest.costs import CostModel
from lpstgp.gp import fitness as fit
from lpstgp.gp.evaluate import TreeEvaluator
from lpstgp.gp.generate import GenerationError, Generator
from lpstgp.gp.pset import PrimitiveLibrary
from lpstgp.gp.variation import Limits, Rule, crossover, mutate, valid
from lpstgp.types import Bool


@dataclass(frozen=True)
class GPConfig:
    population: int = 500
    generations: int = 50
    tournament: int = 5
    elitism: int = 5
    p_crossover: float = 0.8
    p_mutation: float = 0.2
    init_depth: tuple[int, int] = (2, 5)
    limits: Limits = field(default_factory=Limits)
    hof_size: int = 10
    final_selection: str = "validation"
    cache_bytes: int = 512 * 2**20
    elite_fraction: float = 0.1
    # Budget unit (D-033): "requested" runs `generations` generations; "unique" stops after the
    # generation in which `max_unique_evaluations` distinct rules have been scored.
    budget_unit: str = "requested"
    max_unique_evaluations: int = 0
    # Every `checkpoint_every` generations, record the fit-best rule's validation score. Recorded
    # only: checkpoints never influence selection (validation stays out of the search).
    checkpoint_every: int = 10


class Problem:
    """Signals and fitness of rules on every instrument of one stage (FIT or VALIDATE)."""

    def __init__(
        self,
        lib: PrimitiveLibrary,
        bars: Mapping[str, object],
        window: tuple[date, date],
        costs: Mapping[str, CostModel],
        cfg: fit.FitnessConfig,
        cache_bytes: int,
    ) -> None:
        self.lib = lib
        self.cfg = cfg
        share = max(1, cache_bytes // max(1, len(bars)))
        self.evaluators = {
            name: TreeEvaluator(lib, b.log_price, b.log_return, share)
            for name, b in sorted(bars.items())
        }
        self.data = {
            name: fit.prepare(
                b.dates, b.log_return, b.calendar, window, costs[name], cfg.segment_months
            )
            for name, b in sorted(bars.items())
        }

    def signals(self, rule: Rule) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        return {name: (ev(rule.entry), ev(rule.exit)) for name, ev in self.evaluators.items()}

    def score(self, rule: Rule) -> fit.Score:
        size_w = self.lib.weighted_size(rule.entry) + self.lib.weighted_size(rule.exit)
        return fit.score(self.signals(rule), self.data, size_w, self.cfg)

    def cache_stats(self) -> dict[str, float]:
        hits = sum(ev.cache.hits for ev in self.evaluators.values())
        misses = sum(ev.cache.misses for ev in self.evaluators.values())
        return {
            "hits": hits,
            "misses": misses,
            "hit_rate": hits / (hits + misses) if hits + misses else 0.0,
            "bytes": sum(ev.cache.bytes for ev in self.evaluators.values()),
        }

    def operator_seconds(self) -> dict[str, dict[str, float]]:
        totals: dict[str, dict[str, float]] = {}
        for ev in self.evaluators.values():
            for name, seconds in ev.op_seconds.items():
                entry = totals.setdefault(name, {"calls": 0, "seconds": 0.0})
                entry["calls"] += ev.op_calls[name]
                entry["seconds"] += seconds
        return totals


def _initial(lib: PrimitiveLibrary, gen: Generator, cfg: GPConfig) -> list[Rule]:
    population: list[Rule] = []
    seen: set[str] = set()
    attempts = 0
    while len(population) < cfg.population:
        attempts += 1
        if attempts > 50 * cfg.population:
            raise RuntimeError("could not initialise a population of unique valid rules")
        try:
            rule = Rule(gen.ramped(Bool, *cfg.init_depth), gen.ramped(Bool, *cfg.init_depth))
        except GenerationError:
            continue
        if not (valid(rule.entry, lib, cfg.limits) and valid(rule.exit, lib, cfg.limits)):
            continue
        if rule.key() in seen:
            continue
        seen.add(rule.key())
        population.append(rule)
    return population


def _better(a: Rule, b: Rule, lib: PrimitiveLibrary) -> bool:
    """Total order: fitness, then smaller weighted size, then key (deterministic ties)."""
    ka = (-a.fitness, lib.weighted_size(a.entry) + lib.weighted_size(a.exit), a.key())
    kb = (-b.fitness, lib.weighted_size(b.entry) + lib.weighted_size(b.exit), b.key())
    return ka < kb


def _ranked(population: list[Rule], lib: PrimitiveLibrary) -> list[Rule]:
    return sorted(
        population,
        key=lambda r: (-r.fitness, lib.weighted_size(r.entry) + lib.weighted_size(r.exit), r.key()),
    )


def _tournament(population: list[Rule], k: int, lib: PrimitiveLibrary, rng: random.Random) -> Rule:
    best = population[rng.randrange(len(population))]
    for _ in range(k - 1):
        challenger = population[rng.randrange(len(population))]
        if _better(challenger, best, lib):
            best = challenger
    return best


def _quantiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    q = np.percentile(values, [50, 90, 99])
    return {
        "mean": float(np.mean(values)),
        "p50": float(q[0]),
        "p90": float(q[1]),
        "p99": float(q[2]),
        "max": float(max(values)),
    }


def _usage(rules: list[Rule], lib: PrimitiveLibrary) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for rule in rules:
        for tree in rule.trees():
            for node in tree:
                if not lib.is_param(node):
                    counts[node.name] += 1
    return dict(sorted(counts.items()))


def run_gp(
    lib: PrimitiveLibrary,
    fit_problem: Problem,
    val_problem: Problem | None,
    cfg: GPConfig,
    seed: int,
    progress: Callable[[dict], None] | None = None,
) -> dict:
    """Evolve one rule. Returns a JSON-serialisable summary (no populations)."""
    started = time.perf_counter()
    rng = random.Random(seed)
    gen = Generator(lib, cfg.limits.lookback_max, rng)
    scores: dict[str, fit.Score] = {}
    eval_seconds = 0.0
    requested = 0
    eval_ms: list[float] = []  # time of every unique (cache-miss) evaluation

    if cfg.budget_unit not in ("requested", "unique"):
        raise ValueError(f"budget_unit must be 'requested' or 'unique', not {cfg.budget_unit!r}")
    unique_cap = cfg.max_unique_evaluations if cfg.budget_unit == "unique" else 0

    def evaluate(population: list[Rule]) -> float:
        nonlocal eval_seconds, requested
        spent = 0.0
        for rule in population:
            key = rule.key()
            if unique_cap and key not in scores and len(scores) >= unique_cap:
                rule.fitness = -math.inf  # budget spent: never scored, never selected (D-049)
                continue
            requested += 1
            if key not in scores:
                t0 = time.perf_counter()
                scores[key] = fit_problem.score(rule)
                dt = time.perf_counter() - t0
                spent += dt
                eval_ms.append(1000 * dt)
            rule.fitness = scores[key].fitness
        eval_seconds += spent
        return spent

    population = _initial(lib, gen, cfg)
    spent = evaluate(population)
    hof: dict[str, tuple[float, int, str, Rule]] = {}
    generations = []

    def rank_key(e: tuple[float, int, str, Rule]) -> tuple[float, int, str]:
        return (-e[0], e[1], e[2])  # higher fitness, then smaller size, then key

    def update(population: list[Rule], g: int, spent: float, before: int) -> None:
        population = [r for r in population if r.key() in scores]  # unscored: past the cap
        for rule in population:
            s = scores[rule.key()]
            size_w = lib.weighted_size(rule.entry) + lib.weighted_size(rule.exit)
            entry = (rule.fitness, size_w, rule.key(), rule)
            current = hof.get(
                s.signal_hash
            )  # rules that trade identically on the fit are one entry
            if current is None or rank_key(entry) < rank_key(current):
                hof[s.signal_hash] = entry
        ranked = sorted(hof.values(), key=rank_key)[: cfg.hof_size]
        hof.clear()
        hof.update({scores[e[2]].signal_hash: e for e in ranked})
        fitnesses = [r.fitness for r in population]
        elite = _ranked(population, lib)[: max(1, int(cfg.elite_fraction * len(population)))]
        stats = fit_problem.cache_stats()
        generations.append(
            {
                "gen": g,
                "best": max(fitnesses),
                "median": statistics.median(fitnesses),
                "mean": statistics.fmean(fitnesses),
                "mean_nodes": statistics.fmean(len(r.entry) + len(r.exit) for r in population),
                "mean_size_w": statistics.fmean(
                    lib.weighted_size(r.entry) + lib.weighted_size(r.exit) for r in population
                ),
                "unique_share": len({r.key() for r in population}) / len(population),
                "evaluations": requested,
                "unique_evaluations": len(scores),
                "new_unique": len(scores) - before,
                "eval_s": spent,
                "cache_hit_rate": stats["hit_rate"],
                "elapsed_s": time.perf_counter() - started,
                "elite_usage": _usage(elite, lib),
            }
        )
        if progress:
            progress(generations[-1])

    checkpoints: list[dict] = []

    def checkpoint(g: int) -> None:
        if val_problem is None or not cfg.checkpoint_every:
            return
        value, _, _, rule = sorted(hof.values(), key=rank_key)[0]
        v = val_problem.score(rule)
        per = v.components["instruments"].values()
        checkpoints.append(
            {
                "gen": g,
                "fit": value,
                "validation": v.fitness,
                "validation_sharpe": fit.mean_sharpe(v),
                "validation_trades": sum(c.get("trades", 0) for c in per),
                "unique_evaluations": len(scores),
            }
        )

    update(population, 0, spent, 0)
    checkpoint(0)
    for g in range(1, cfg.generations + 1):
        if unique_cap and len(scores) >= unique_cap:
            break
        ranked = _ranked(population, lib)
        offspring = [r.copy() for r in ranked[: cfg.elitism]]
        while len(offspring) < cfg.population:
            a = _tournament(population, cfg.tournament, lib, rng)
            b = _tournament(population, cfg.tournament, lib, rng)
            if rng.random() < cfg.p_crossover:
                a, b = crossover(a, b, lib, cfg.limits, rng)
            else:
                a, b = a.copy(), b.copy()
            if rng.random() < cfg.p_mutation:
                a = mutate(a, lib, gen, cfg.limits, rng)
            if rng.random() < cfg.p_mutation:
                b = mutate(b, lib, gen, cfg.limits, rng)
            offspring.extend([a, b])
        population = offspring[: cfg.population]
        before = len(scores)
        spent = evaluate(population)
        update(population, g, spent, before)
        if g % max(cfg.checkpoint_every, 1) == 0:
            checkpoint(g)
    if cfg.checkpoint_every and (
        not checkpoints or checkpoints[-1]["gen"] != generations[-1]["gen"]
    ):
        checkpoint(generations[-1]["gen"])

    members = sorted(hof.values(), key=rank_key)
    hall = []
    for rank, (value, size_w, key, rule) in enumerate(members):
        entry = {
            "rank": rank,
            "entry": lib.to_names(rule.entry),
            "exit": lib.to_names(rule.exit),
            "entry_str": str(rule.entry),
            "exit_str": str(rule.exit),
            "lookback": max(lib.lookback(rule.entry), lib.lookback(rule.exit)),
            "size_w": size_w,
            "fit": {"fitness": value, **scores[key].components},
        }
        if val_problem is not None:
            v = val_problem.score(rule)
            entry["validation"] = {"fitness": v.fitness, **v.components}
        hall.append(entry)
    if cfg.final_selection == "validation" and val_problem is not None:
        selected = max(range(len(hall)), key=lambda k: (hall[k]["validation"]["fitness"], -k))
    else:
        selected = 0
    total = time.perf_counter() - started
    unique = len(scores)
    return {
        "seed": seed,
        "config": asdict(cfg),
        "fitness_config": asdict(fit_problem.cfg),
        "budget": {
            "unit": cfg.budget_unit,
            "requested_evaluations": requested,
            "unique_evaluations": unique,
            "generations_run": generations[-1]["gen"],
            # Under a unique budget: did the cap end the run, or the generation ceiling?
            "cap_reached": bool(unique_cap) and unique >= unique_cap,
            "overshoot": max(unique - unique_cap, 0) if unique_cap else 0,  # 0 by construction
        },
        "timings": {
            "total_s": total,
            "evaluation_s": eval_seconds,
            "per_unique_evaluation_ms": 1000 * eval_seconds / max(unique, 1),
            "per_requested_evaluation_ms": 1000 * total / max(requested, 1),
            "unique_evaluation_ms": _quantiles(eval_ms),
        },
        "cache": fit_problem.cache_stats(),
        "operator_seconds": fit_problem.operator_seconds(),
        "generations": generations,
        "validation_checkpoints": checkpoints,
        "hall_of_fame": hall,
        "selected": selected,
    }
