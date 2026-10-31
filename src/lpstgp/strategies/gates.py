"""Behavioural admission gates for whole strategies (run inside the sandboxed worker).

The source policy and the contract's structural checks run first (``loader.load_file``). These
gates then check, for every signal at sampled grid points and for the whole strategy at its
defaults: output types and domains, determinism, prefix invariance under adversarial appends
(price and return appended consistently), that nothing older than the declared lookback
matters, shift invariance of price-based signals, runtime, and, on development data, finiteness
and non-degenerate entries and exits.
"""

from __future__ import annotations

import itertools
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np

from lpstgp.gates.checks import same
from lpstgp.gates.synthetic import adversarial_tail, garch_returns
from lpstgp.strategies.api import MAX_LOOKBACK, Signal, Strategy
from lpstgp.types import Series

SYNTHETIC_BARS = 1500
CUTS = (700, 1100)
TAILS = (1, 7, 63)
MODES = (0, 1, 2, 3, 4)
MAX_SECONDS = 2.0  # per signal call on SYNTHETIC_BARS bars
MIN_FINITE = 0.99
MIN_INSTRUMENT_SHARE = 0.5

Inputs = tuple[np.ndarray, np.ndarray]  # (log_price, log_return)
Fn = Callable[[np.ndarray, np.ndarray], tuple[np.ndarray, ...]]


def synthetic_inputs(n: int = SYNTHETIC_BARS, seed: int = 11) -> Inputs:
    r = garch_returns(n, seed)
    return 4.6 + np.cumsum(r), r


def _append(inputs: Inputs, n: int, tail: int, mode: int, seed: int) -> Inputs:
    lp, lr = inputs[0][:n], inputs[1][:n]
    rt = np.asarray(adversarial_tail(Series, tail, mode, lr, seed), dtype=np.float64)
    lpt = lp[-1] + np.cumsum(np.nan_to_num(rt))
    lpt[np.isnan(rt)] = np.nan
    return np.concatenate([lp, lpt]), np.concatenate([lr, rt])


def _all_same(a: Sequence[np.ndarray], b: Sequence[np.ndarray]) -> bool:
    return all(same(x, y) for x, y in zip(a, b, strict=True))


def prefix_problems(fn: Fn, inputs: Inputs, seed: int = 0) -> list[str]:
    problems = []
    for n in CUTS:
        base = fn(inputs[0][:n], inputs[1][:n])
        for tail, mode in itertools.product(TAILS, MODES):
            lp, lr = _append(inputs, n, tail, mode, seed)
            if not _all_same(base, [x[:n] for x in fn(lp, lr)]):
                problems.append(
                    f"values before bar {n} change when {tail} bars (mode {mode}) are appended"
                )
                return problems
        lp, lr = inputs[0][:n].copy(), inputs[1][:n].copy()
        lp[-1] = lr[-1] = np.nan  # NaN at the cut
        base = fn(lp, lr)
        ext = fn(
            np.concatenate([lp, inputs[0][n : n + 10]]), np.concatenate([lr, inputs[1][n : n + 10]])
        )
        if not _all_same(base, [x[:n] for x in ext]):
            problems.append(f"values before bar {n} change after a NaN bar is followed by data")
            return problems
    return problems


def lookback_problems(fn: Fn, inputs: Inputs, lookback: int, seed: int = 0) -> list[str]:
    """Perturb every bar older than the last ``lookback`` bars; values at ``t`` must not move."""
    rng = np.random.default_rng(seed)
    n = len(inputs[0])
    base = fn(*inputs)
    for t in sorted({lookback + 40, n // 2, n - 1}):
        if t - lookback < 1 or t >= n:
            continue
        lp, lr = inputs[0].copy(), inputs[1].copy()
        old = slice(0, t - lookback + 1)
        lp[old] += rng.normal(0, 0.5, old.stop)
        lr[old] = rng.normal(0, 0.05, old.stop)
        for b, p in zip(base, fn(lp, lr), strict=True):
            if not same(b[t : t + 1], p[t : t + 1]):
                return [
                    f"value at bar {t} depends on bars older than the declared lookback of "
                    f"{lookback} (lookback counts bars t-lookback+1 .. t)"
                ]
    return []


def _signal_fn(signal: Signal, params: Mapping[str, Any]) -> Fn:
    def fn(lp: np.ndarray, lr: np.ndarray) -> tuple[np.ndarray, ...]:
        data = {"log_price": lp, "log_return": lr, "abs_return": np.abs(lr)}
        return (signal(data, **params),)

    return fn


def _strategy_fn(strategy: Strategy) -> Fn:
    def fn(lp: np.ndarray, lr: np.ndarray) -> tuple[np.ndarray, ...]:
        signals = strategy.compute(lp, lr)
        return (*strategy.entry_exit(signals), *signals.values())

    return fn


def param_points(signal: Signal, seed: int = 7, n_random: int = 2) -> list[dict[str, Any]]:
    """Defaults, all-minimum, all-maximum and seeded random grid points."""
    if not signal.params:
        return [{}]
    rng = np.random.default_rng(seed)
    points = [
        signal.defaults,
        {k: min(p.grid) for k, p in signal.params.items()},
        {k: max(p.grid) for k, p in signal.params.items()},
    ]
    points += [
        {k: p.grid[rng.integers(len(p.grid))] for k, p in signal.params.items()}
        for _ in range(n_random)
    ]
    unique = []
    for point in points:
        if point not in unique:
            unique.append(point)
    return unique


def _check(results: list[dict], name: str, problems: list[str]) -> None:
    results.append({"check": name, "passed": not problems, "detail": problems[:3]})


def behaviour(strategy: Strategy, inputs: Inputs | None = None) -> list[dict]:
    """All synthetic-data gates; each result is ``{check, passed, detail}``."""
    inputs = inputs or synthetic_inputs()
    n = len(inputs[0])
    results: list[dict] = []
    for signal in strategy.signals:
        for params in param_points(signal):
            label = f"{signal.name}{params}"
            fn = _signal_fn(signal, params)
            try:
                lookback = signal.lookback_for(params)
                started = time.perf_counter()
                (out,) = fn(*inputs)
                seconds = time.perf_counter() - started
            except Exception as exc:
                _check(results, f"runs {label}", [f"{type(exc).__name__}: {exc}"])
                continue
            problems = []
            if out.shape != (n,) or out.dtype != np.float64:
                problems.append(
                    f"returns shape {out.shape}, dtype {out.dtype}; need ({n},) float64"
                )
            elif np.isinf(out).any():
                problems.append("returns inf")
            _check(results, f"type {label}", problems)
            if problems:
                continue
            _check(
                results,
                f"lookback <= {MAX_LOOKBACK} {label}",
                [] if lookback <= MAX_LOOKBACK else [f"lookback {lookback}"],
            )
            _check(
                results,
                f"runtime {label}",
                [] if seconds <= MAX_SECONDS else [f"{seconds:.2f} s for {n} bars"],
            )
            _check(
                results,
                f"deterministic {label}",
                [] if same(out, fn(*inputs)[0]) else ["two calls differ"],
            )
            _check(results, f"prefix-invariant {label}", prefix_problems(fn, inputs))
            _check(results, f"lookback {label}", lookback_problems(fn, inputs, lookback))
            if "log_price" in signal.inputs:
                (shifted,) = fn(inputs[0] + 3.7, inputs[1])
                _check(
                    results,
                    f"shift-invariant {label}",
                    []
                    if same(out, shifted, 1e-9)
                    else ["changes when log price is shifted by a constant"],
                )
    fn = _strategy_fn(strategy)
    try:
        entry, exit_, *_ = fn(*inputs)
    except Exception as exc:
        _check(results, "strategy runs", [f"{type(exc).__name__}: {exc}"])
        return results
    problems = [
        f"{name} has values outside {{0, 1, NaN}}"
        for name, arr in (("entry", entry), ("exit", exit_))
        if arr.shape != (n,)
        or not np.isin(arr[np.isfinite(arr)], (0.0, 1.0)).all()
        or np.isinf(arr).any()
    ]
    _check(results, "strategy entry/exit domain", problems)
    if problems:
        return results
    _check(
        results,
        "strategy deterministic",
        [] if _all_same(fn(*inputs), fn(*inputs)) else ["two runs differ"],
    )
    _check(results, "strategy prefix-invariant", prefix_problems(fn, inputs))
    _check(results, "strategy lookback", lookback_problems(fn, inputs, strategy.lookback))
    return results


def on_development_data(
    strategy: Strategy, data: Mapping[str, tuple[np.ndarray, np.ndarray, int]]
) -> list[dict]:
    """``data`` maps an instrument to (log_price, log_return, first scored bar)."""
    finite_bad, constant_bad, fire_bad = [], [], []
    for name, (lp, lr, start) in data.items():
        signals = strategy.compute(lp, lr)
        entry, exit_ = strategy.entry_exit(signals)
        lo = max(start, strategy.lookback)
        for sname, values in signals.items():
            window = values[lo:]
            if len(window) and np.isfinite(window).mean() < MIN_FINITE:
                finite_bad.append(f"{name}:{sname} finite share {np.isfinite(window).mean():.3f}")
            finite = window[np.isfinite(window)]
            if len(finite) and np.ptp(finite) == 0:
                constant_bad.append(f"{name}:{sname}")
        e, x = entry[lo:], exit_[lo:]
        fires = (e == 1).any() and (x == 1).any() and (e == 0).any()
        if not fires:
            fire_bad.append(name)
    total = max(len(data), 1)
    results: list[dict] = []
    _check(results, f"dev finite share >= {MIN_FINITE}", finite_bad)
    _check(
        results,
        "dev signals not constant",
        constant_bad if len({c.split(":")[0] for c in constant_bad}) > (1 - 0.9) * total else [],
    )
    _check(
        results,
        f"dev entry and exit fire on >= {MIN_INSTRUMENT_SHARE:.0%} of instruments",
        [f"no entry/exit activity on {len(fire_bad)} of {total}: {fire_bad[:5]}"]
        if len(fire_bad) > (1 - MIN_INSTRUMENT_SHARE) * total
        else [],
    )
    return results


def passed(results: Sequence[Mapping[str, Any]]) -> bool:
    return all(r["passed"] for r in results)
