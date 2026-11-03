"""Admission gates for LLM-authored operators (run inside the sandboxed worker).

The WP1 gates (:mod:`lpstgp.gates.checks`) at sampled grid points on seeded synthetic inputs:
type, finite and non-constant, deterministic, prefix-invariant under adversarial appends, exact
declared lookback and declared invariances; plus a runtime limit, and finiteness and
non-constancy on anonymised development data, with inputs built by the shared core library as
in the WP1 real-data gate. Each result is ``{check, passed, detail}``.
"""

from __future__ import annotations

import time
import traceback
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from lpstgp.gates import checks
from lpstgp.gates.synthetic import make_input
from lpstgp.operators.contract import OperatorSpec
from lpstgp.types import Bool, Hist, Path, Real, Regime, Series

N = 1200
SEED = 20261102
CUTS = (600, 1000)
MAX_SECONDS = 2.0  # per call on N bars
MIN_FINITE = 0.99
MIN_NONCONSTANT_SHARE = 0.9  # of development instruments (as the WP1 real-data gate)

DevInputs = Mapping[str, tuple[np.ndarray, np.ndarray, int]]  # id -> (log_price, log_return, start)


def synthetic_inputs(spec: OperatorSpec, seed: int = SEED) -> list[np.ndarray]:
    counts: dict[type, int] = {}
    values = []
    for sem_type in spec.inputs:
        variant = counts.get(sem_type, 0)
        counts[sem_type] = variant + 1
        values.append(make_input(sem_type, N, seed, variant))
    return values


def _core():
    from lpstgp.operators.core import (
        gt__v1,
        mean_ksd__v1,
        quantile_regime__v1,
        rolling_hist__v1,
        rolling_percentile__v1,
        to_path__v1,
    )

    return {
        "gt": gt__v1.SPEC,
        "mean_ksd": mean_ksd__v1.SPEC,
        "quantile_regime": quantile_regime__v1.SPEC,
        "rolling_hist": rolling_hist__v1.SPEC,
        "rolling_percentile": rolling_percentile__v1.SPEC,
        "to_path": to_path__v1.SPEC,
    }


def real_inputs(spec: OperatorSpec, log_price: np.ndarray, log_return: np.ndarray) -> list:
    """Realistic inputs of each type from one instrument, built with the shared core."""
    core = _core()
    ret, price = np.asarray(log_return), np.asarray(log_price)
    feature = core["mean_ksd"].impl(ret, 60, 0.0)  # rolling mean return (test input only)
    makers = {
        Series: [lambda: ret, lambda: np.abs(ret)],
        Path: [lambda: price, lambda: core["to_path"](np.abs(ret))],
        Hist: [
            lambda: core["rolling_hist"](ret, window=20),
            lambda: core["rolling_hist"](ret, window=120),
        ],
        Real: [lambda: feature, lambda: core["rolling_percentile"](feature, window=120, q=0.5)],
        Bool: [
            lambda: core["gt"](ret, np.zeros_like(ret)),
            lambda: core["gt"](feature, np.zeros_like(feature)),
        ],
        Regime: [lambda: core["quantile_regime"](feature, window=120)] * 2,
    }
    counts: dict = {}
    values = []
    for sem_type in spec.inputs:
        k = counts.get(sem_type, 0)
        counts[sem_type] = k + 1
        values.append(makers[sem_type][k % 2]())
    return values


def _result(results: list[dict], name: str, problems: Sequence[str]) -> None:
    results.append({"check": name, "passed": not problems, "detail": list(problems)[:3]})


def _guard(results: list[dict], name: str, fn, *args, **kwargs) -> Any:
    try:
        problems = fn(*args, **kwargs)
    except Exception as exc:  # the operator's own code failed
        problems = [f"{type(exc).__name__}: {exc}"]
    _result(results, name, problems)
    return problems


def synthetic_gates(spec: OperatorSpec) -> list[dict]:
    results: list[dict] = []
    for params in checks.sample_params(spec, SEED, n_random=2):
        label = f"{spec.name}{params}"
        inputs = synthetic_inputs(spec)
        try:
            started = time.perf_counter()
            out = checks.run(spec, inputs, params)
            seconds = time.perf_counter() - started
        except Exception as exc:
            _result(results, f"runs {label}", [f"{type(exc).__name__}: {exc}"])
            continue
        if _guard(results, f"type {label}", checks.check_type, spec, inputs, params):
            continue
        _result(
            results,
            f"runtime {label}",
            [] if seconds <= MAX_SECONDS else [f"{seconds:.2f} s for {N} bars"],
        )

        mask = checks.inputs_defined(inputs)
        mask[: max(spec.earliest(params) + 30, 300)] = False
        _guard(
            results,
            f"finite and non-constant {label}",
            checks.check_finite_nonconstant,
            spec,
            out,
            mask,
            min_finite=MIN_FINITE,
        )
        _guard(results, f"deterministic {label}", checks.check_deterministic, spec, inputs, params)
        _guard(
            results,
            f"prefix-invariant {label}",
            checks.check_prefix,
            spec,
            inputs,
            params,
            cuts=CUTS,
            seed=SEED,
        )
        _guard(
            results,
            f"exact lookback {label}",
            checks.check_locality,
            spec,
            inputs,
            params,
            positions=(700, 1100),
            seed=SEED,
        )
        _guard(
            results, f"declared invariances {label}", checks.check_invariance, spec, inputs, params
        )
    return results


def withheld(exc: BaseException) -> str:
    """An error raised on development data, without its message, which could quote data values
    (D-074): the exception type and the lines of the operator's own code where it was raised."""
    import sys

    system = tuple({sys.prefix, sys.base_prefix})
    own = [
        f
        for f in traceback.extract_tb(exc.__traceback__)
        if "/lpstgp/" not in f.filename and not f.filename.startswith(system)
    ]
    where = "; ".join(f"line {f.lineno}: {(f.line or '').strip()}" for f in own[-3:])
    return f"{type(exc).__name__} raised on development data (message withheld)" + (
        f" at {where}" if where else ""
    )


def development_gates(spec: OperatorSpec, data: DevInputs) -> list[dict]:
    """Finite and non-constant on the development instruments, at every sampled grid point."""
    results: list[dict] = []
    for params in checks.sample_params(spec, SEED, n_random=2):
        finite_bad, constant = [], 0
        try:
            for anon, (lp, lr, start) in data.items():
                inputs = real_inputs(spec, lp, lr)
                out = checks.run(spec, inputs, params)
                scored = checks.inputs_defined(inputs)
                scored[: max(start, spec.earliest(params) + 1)] = False
                problems = checks.check_finite_nonconstant(spec, out, scored, MIN_FINITE)
                finite_bad += [f"{anon}: {p}" for p in problems if "finite" in p]
                constant += any("constant" in p for p in problems)
        except Exception as exc:
            _result(results, f"development data {spec.name}{params}", [withheld(exc)])
            continue
        _result(results, f"development data finite {spec.name}{params}", finite_bad)
        share = 1 - constant / max(len(data), 1)
        _result(
            results,
            f"development data non-constant {spec.name}{params}",
            []
            if share >= MIN_NONCONSTANT_SHARE
            else [f"constant on {constant} of {len(data)} instruments"],
        )
    return results


def passed(results: Sequence[Mapping[str, Any]]) -> bool:
    return all(r["passed"] for r in results)
