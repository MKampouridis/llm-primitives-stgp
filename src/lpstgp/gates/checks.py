"""Dynamic admission checks: type, finiteness, determinism, prefix invariance, locality, invariance.

Each check returns a list of problems (empty = pass). Arrays are compared NaN-aware; the default
tolerance is zero (bitwise), an operator may declare a small tolerance in its contract.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from lpstgp.gates.synthetic import adversarial_tail
from lpstgp.operators.contract import Memory, OperatorSpec
from lpstgp.types import Bool, Hist, Path, Regime, Series, validate


def same(a: np.ndarray, b: np.ndarray, tolerance: float = 0.0) -> bool:
    if a.shape != b.shape:
        return False
    nan_a, nan_b = np.isnan(a), np.isnan(b)
    if not np.array_equal(nan_a, nan_b):
        return False
    if tolerance == 0.0:
        return bool(np.array_equal(a[~nan_a], b[~nan_b]))
    return bool(np.allclose(a[~nan_a], b[~nan_b], rtol=tolerance, atol=tolerance))


def run(spec: OperatorSpec, inputs: Sequence[np.ndarray], params: Mapping[str, Any]) -> np.ndarray:
    return spec(*inputs, **params)


def check_type(
    spec: OperatorSpec, inputs: Sequence[np.ndarray], params: Mapping[str, Any]
) -> list[str]:
    for sem_type, value in zip(spec.inputs, inputs, strict=True):
        problems = validate(sem_type, value, len(inputs[0]))
        if problems:
            return [f"bad test input {sem_type.__name__}: {problems}"]
    out = run(spec, inputs, params)
    return [
        f"output {spec.output.__name__}: {p}" for p in validate(spec.output, out, len(inputs[0]))
    ]


def inputs_defined(inputs: Sequence[np.ndarray]) -> np.ndarray:
    """Bars at which every input is defined (Hist: the whole row)."""
    mask = np.ones(len(inputs[0]), dtype=bool)
    for x in inputs:
        mask &= ~np.isnan(x).any(axis=1) if x.ndim == 2 else ~np.isnan(x)
    return mask


def check_finite_nonconstant(
    spec: OperatorSpec, out: np.ndarray, scored: np.ndarray, min_finite: float
) -> list[str]:
    """``scored`` selects the bars judged: after warm-up, with defined inputs."""
    values = out[scored]
    rows = values if values.ndim == 1 else values[:, 0]
    if len(rows) == 0:
        return ["no scored bars"]
    share = float(np.mean(np.isfinite(rows)))
    problems = []
    if share < min_finite:
        problems.append(f"finite share {share:.3f} < {min_finite}")
    finite = values[np.isfinite(rows)]
    if spec.output in (Bool, Regime):
        if len(np.unique(finite)) < 2:
            problems.append("constant output")
    elif finite.size == 0 or np.all(finite == finite.flat[0]) or np.nanstd(finite) <= 1e-12:
        problems.append("constant output")
    return problems


def check_deterministic(
    spec: OperatorSpec, inputs: Sequence[np.ndarray], params: Mapping[str, Any]
) -> list[str]:
    first = run(spec, inputs, params)
    # Perturb the legacy global RNG on purpose: operators must not depend on it.
    np.random.seed(12345)  # noqa: NPY002
    _ = np.random.random(100)  # noqa: NPY002
    second = run(spec, [x.copy() for x in inputs], params)
    return [] if same(first, second) else ["repeated calls differ"]


def check_prefix(
    spec: OperatorSpec,
    inputs: Sequence[np.ndarray],
    params: Mapping[str, Any],
    cuts: Sequence[int],
    tails: Sequence[int] = (1, 7, 63),
    modes: Sequence[int] = (0, 1, 2, 3, 4),
    seed: int = 0,
) -> list[str]:
    """Appending future bars (adversarial) never changes values already computed."""
    problems = []
    for cut in cuts:
        prefix = [x[:cut] for x in inputs]
        base = run(spec, prefix, params)
        for tail in tails:
            for mode in modes:
                extended = [
                    np.concatenate([x[:cut], adversarial_tail(t, tail, mode, x[:cut], seed)])
                    for t, x in zip(spec.inputs, inputs, strict=True)
                ]
                longer = run(spec, extended, params)[:cut]
                if not same(base, longer, spec.tolerance):
                    problems.append(f"cut {cut}, +{tail} bars (mode {mode}) changed past values")
    # a NaN exactly at the cut point
    prefix = [x[:cut].copy() for x in inputs for cut in cuts[:1]]
    for x in prefix:
        if x.ndim == 1:
            x[-1] = np.nan
        else:
            x[-1, :] = np.nan
    a = run(spec, prefix, params)
    b = run(spec, [np.concatenate([x, x[-5:]]) for x in prefix], params)[: len(prefix[0])]
    if not same(a, b, spec.tolerance):
        problems.append("NaN at the cut point: appending bars changed past values")
    return problems


def check_locality(
    spec: OperatorSpec,
    inputs: Sequence[np.ndarray],
    params: Mapping[str, Any],
    positions: Sequence[int],
    seed: int = 0,
) -> list[str]:
    """Output at t depends only on bars t-L+1..t: garbage before the window changes nothing."""
    if spec.memory is not Memory.FINITE:
        return []
    lookback = spec.lookback_for(params)
    rng = np.random.default_rng(seed)
    reference = run(spec, inputs, params)
    problems = []
    for t in positions:
        start = t - lookback + 1
        if start <= 0:
            continue
        garbled = []
        for sem_type, x in zip(spec.inputs, inputs, strict=True):
            y = x.copy()
            if sem_type is Hist:
                rows = rng.dirichlet(np.ones(x.shape[1]), start)
                rows[rng.random(start) < 0.3] = np.nan
                y[:start] = rows
            elif sem_type in (Bool, Regime):
                y[:start] = rng.choice((0.0, 1.0, np.nan), start)
            else:
                y[:start] = rng.standard_normal(start) * 100 * (np.nanstd(x) or 1.0)
                y[:start][rng.random(start) < 0.2] = np.nan
            garbled.append(y)
        out = run(spec, garbled, params)
        if not same(reference[t : t + 1], out[t : t + 1], spec.tolerance):
            problems.append(f"output at {t} depends on bars before its {lookback}-bar window")
    return problems


def check_invariance(
    spec: OperatorSpec,
    inputs: Sequence[np.ndarray],
    params: Mapping[str, Any],
    tolerance: float = 1e-9,
) -> list[str]:
    """Declared invariances: 'shift' adds a constant to Path inputs; 'scale' rescales Series/Path inputs."""
    reference = run(spec, inputs, params)
    tol = max(tolerance, spec.tolerance)
    problems = []
    transforms = []
    if "shift" in spec.invariances:
        transforms += [("shift", c) for c in (0.37, -5.0)]
    if "scale" in spec.invariances:
        transforms += [("scale", k) for k in (0.01, 37.0)]
    for kind, value in transforms:
        moved = []
        for sem_type, x in zip(spec.inputs, inputs, strict=True):
            if kind == "shift" and sem_type is Path:
                moved.append(x + value)
            elif kind == "scale" and sem_type in (Series, Path):
                moved.append(x * value)
            else:
                moved.append(x)
        if not same(reference, run(spec, moved, params), tol):
            problems.append(f"not {kind}-invariant ({kind}={value})")
    return problems


def sample_params(spec: OperatorSpec, seed: int, n_random: int = 1) -> list[dict[str, Any]]:
    """All-minimum and all-maximum grid values plus seeded random combinations."""
    if not spec.params:
        return [{}]
    lows = {p.name: min(p.grid) for p in spec.params}
    highs = {p.name: max(p.grid) for p in spec.params}
    rng = np.random.default_rng(seed)
    samples = [lows, highs]
    for _ in range(n_random):
        samples.append({p.name: p.grid[int(rng.integers(len(p.grid)))] for p in spec.params})
    unique = []
    for s in samples:
        if s not in unique:
            unique.append(s)
    return unique
