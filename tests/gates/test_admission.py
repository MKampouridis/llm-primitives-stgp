"""Admission gates, applied to every registered operator with sampled legal parameters.

1 compiles + source policy   2 type-correct   3 finite and non-constant (synthetic here; real data
in test_real_data_gates)   4 deterministic   5 prefix-invariant
plus the declared-lookback (window-locality) check and declared invariances.
"""

from __future__ import annotations

import pytest

from lpstgp.gates import checks, policy
from lpstgp.gates.synthetic import make_input
from lpstgp.operators.registry import discover, module_path

N = 1200
SEED = 20261030
REGISTRY = discover()
OPERATORS = sorted(REGISTRY.operators.values(), key=lambda s: s.key)
CASES = [(spec, params) for spec in OPERATORS for params in checks.sample_params(spec, SEED)]
IDS = [f"{spec.key}-{'-'.join(f'{k}={v}' for k, v in params.items())}" for spec, params in CASES]


def inputs_for(spec, seed=SEED):
    counts: dict[type, int] = {}
    values = []
    for sem_type in spec.inputs:
        variant = counts.get(sem_type, 0)
        counts[sem_type] = variant + 1
        values.append(make_input(sem_type, N, seed, variant))
    return values


@pytest.mark.parametrize("spec", OPERATORS, ids=[s.key for s in OPERATORS])
def test_gate1_compiles_and_respects_source_policy(spec):
    source = module_path(REGISTRY.modules[spec.key]).read_text(encoding="utf-8")
    assert policy.check_operator_source(source) == []


@pytest.mark.parametrize(("spec", "params"), CASES, ids=IDS)
def test_gate2_type_correct(spec, params):
    assert checks.check_type(spec, inputs_for(spec), params) == []


@pytest.mark.parametrize(("spec", "params"), CASES, ids=IDS)
def test_gate3_finite_and_nonconstant_synthetic(spec, params):
    inputs = inputs_for(spec)
    out = checks.run(spec, inputs, params)
    mask = checks.inputs_defined(inputs)  # judge only bars whose inputs are defined
    mask[: max(spec.earliest(params) + 30, 300)] = False
    assert checks.check_finite_nonconstant(spec, out, mask, min_finite=0.99) == []


@pytest.mark.parametrize(("spec", "params"), CASES, ids=IDS)
def test_gate4_deterministic(spec, params):
    assert checks.check_deterministic(spec, inputs_for(spec), params) == []


@pytest.mark.parametrize(("spec", "params"), CASES, ids=IDS)
def test_gate5_prefix_invariant(spec, params):
    assert checks.check_prefix(spec, inputs_for(spec), params, cuts=(600, 1000), seed=SEED) == []


@pytest.mark.parametrize(("spec", "params"), CASES, ids=IDS)
def test_declared_lookback_is_exact(spec, params):
    assert (
        checks.check_locality(spec, inputs_for(spec), params, positions=(700, 1100), seed=SEED)
        == []
    )


@pytest.mark.parametrize(("spec", "params"), CASES, ids=IDS)
def test_declared_invariances(spec, params):
    assert checks.check_invariance(spec, inputs_for(spec), params) == []


def test_every_operator_declares_shift_invariance_for_path_inputs():
    from lpstgp.types import Path

    offenders = [s.key for s in OPERATORS if Path in s.inputs and "shift" not in s.invariances]
    assert offenders == [], "Path consumers must be shift-invariant (causal price adjustment)"
