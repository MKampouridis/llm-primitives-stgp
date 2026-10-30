"""Admission gates for terminals (data streams, technical and directional-change indicators)."""

from __future__ import annotations

import numpy as np
import pytest

from lpstgp.gates import checks, policy
from lpstgp.gates.synthetic import garch_returns
from lpstgp.operators.contract import Memory
from lpstgp.operators.registry import discover, module_path
from lpstgp.types import Bool, Regime, validate

REGISTRY = discover()
TERMINALS = sorted(REGISTRY.terminals.values(), key=lambda s: s.key)
IDS = [t.key for t in TERMINALS]
N = 1200


def bars(seed: int = 3) -> tuple[np.ndarray, np.ndarray]:
    log_price = np.log(100.0) + np.cumsum(garch_returns(N, seed))
    log_return = np.full(N, np.nan)
    log_return[1:] = np.diff(log_price)
    return log_price, log_return


def run(spec, log_price, log_return):
    return spec(log_price, log_return)


@pytest.mark.parametrize("spec", TERMINALS, ids=IDS)
def test_terminal_module_policy(spec):
    source = module_path(REGISTRY.modules[spec.key]).read_text(encoding="utf-8")
    assert policy.check_operator_source(source) == []


@pytest.mark.parametrize("spec", TERMINALS, ids=IDS)
def test_terminal_type_finite_nonconstant_deterministic(spec):
    lp, lr = bars()
    out = run(spec, lp, lr)
    assert validate(spec.output, out, N) == []
    scored = np.zeros(N, dtype=bool)
    scored[max(spec.lookback + 30, 300) :] = True
    values = out[scored]
    assert np.mean(np.isfinite(values)) >= 0.99
    finite = values[np.isfinite(values)]
    if spec.output in (Bool, Regime):
        assert len(np.unique(finite)) >= 2
    else:
        assert np.nanstd(finite) > 1e-12
    assert checks.same(out, run(spec, lp.copy(), lr.copy()))


@pytest.mark.parametrize("spec", TERMINALS, ids=IDS)
def test_terminal_prefix_invariance(spec):
    lp, lr = bars()
    rng = np.random.default_rng(1)
    for cut in (600, 1000):
        base = run(spec, lp[:cut], lr[:cut])
        for tail in (1, 7, 63):
            for mode in range(4):
                if mode == 0:  # violent reversals, larger than any DC threshold
                    extra = lp[cut - 1] + np.cumsum(np.where(np.arange(tail) % 2, -0.3, 0.3))
                elif mode == 1:
                    extra = np.full(tail, np.nan)
                elif mode == 2:
                    extra = np.full(tail, lp[cut - 1])
                else:
                    extra = lp[cut - 1] + rng.standard_normal(tail)
                lp2 = np.concatenate([lp[:cut], extra])
                lr2 = np.concatenate([lr[:cut], np.diff(np.concatenate([[lp[cut - 1]], extra]))])
                assert checks.same(base, run(spec, lp2, lr2)[:cut]), (cut, tail, mode)


@pytest.mark.parametrize(
    "spec", [t for t in TERMINALS if t.memory is Memory.FINITE], ids=lambda s: s.key
)
def test_terminal_lookback_is_exact(spec):
    lp, lr = bars()
    reference = run(spec, lp, lr)
    rng = np.random.default_rng(2)
    for t in (700, 1100):
        start = t - spec.lookback + 1
        lp2, lr2 = lp.copy(), lr.copy()
        lp2[:start] = rng.standard_normal(start) * 10
        lr2[:start] = rng.standard_normal(start)
        assert checks.same(reference[t : t + 1], run(spec, lp2, lr2)[t : t + 1]), t


def test_terminal_lookbacks_fit_the_cap():
    assert max(t.lookback for t in TERMINALS) <= 504
