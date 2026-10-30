"""Gate 3 on real data: every operator is finite and non-constant on P01's train span.

Uses P01 VALIDATE sandboxes only (horizon 2008-07-01, before the first test year), so the
seed library's admission never touches any period's test data. Instruments without data before
2008 (crypto) are covered by the synthetic gates.
"""

from __future__ import annotations

import numpy as np
import pytest

from lpstgp.config import load_settings
from lpstgp.data.store import DataStore
from lpstgp.gates import checks
from lpstgp.operators.registry import discover
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage, periods_from_settings
from lpstgp.types import Bool, Hist, Path, Real, Regime, Series

pytestmark = pytest.mark.realdata

REGISTRY = discover()
OPS = {s.name: s for s in REGISTRY.operators.values()}
CASES = [
    (spec, params)
    for spec in sorted(REGISTRY.operators.values(), key=lambda s: s.key)
    for params in checks.sample_params(spec, 20261030)
]


@pytest.fixture(scope="module")
def p01(tier_a_dir):
    settings = load_settings()
    period = periods_from_settings(settings)[0]
    store = DataStore(tier_a_dir)
    lmax = settings["splits"]["lookback_max_bars"]
    sandbox = Sandbox.open(store, period, Stage.VALIDATE, store.instruments(), lmax)
    usable = [
        i
        for i in sandbox.instruments
        if sandbox.access_log[sandbox.instruments.index(i)].warmup_bars == lmax
    ]
    return sandbox, usable


def real_inputs(spec, bars):
    ret, price = np.asarray(bars.log_return), np.asarray(bars.log_price)
    feature = OPS["mean_ksd"].impl(
        ret, 60, 0.0
    )  # rolling mean return (k=0 is off-grid: test input only)
    makers = {
        Series: [lambda: ret, lambda: np.abs(ret)],
        Path: [lambda: price, lambda: OPS["to_path"](np.abs(ret))],
        Hist: [
            lambda: OPS["rolling_hist"](ret, window=20),
            lambda: OPS["rolling_hist"](ret, window=120),
        ],
        Real: [lambda: feature, lambda: OPS["rolling_percentile"](feature, window=120, q=0.5)],
        Bool: [
            lambda: OPS["gt"](ret, np.zeros_like(ret)),
            lambda: OPS["gt"](feature, np.zeros_like(feature)),
        ],
        Regime: [lambda: OPS["quantile_regime"](feature, window=120)] * 2,
    }
    counts: dict = {}
    values = []
    for sem_type in spec.inputs:
        k = counts.get(sem_type, 0)
        counts[sem_type] = k + 1
        values.append(makers[sem_type][k % 2]())
    return values


@pytest.mark.parametrize(("spec", "params"), CASES, ids=[f"{s.key}-{p}" for s, p in CASES])
def test_gate3_finite_and_nonconstant_on_p01(p01, spec, params):
    sandbox, instruments = p01
    assert len(instruments) >= 20
    failures = []
    for instrument in instruments:
        bars = sandbox[instrument]
        inputs = real_inputs(spec, bars)
        out = checks.run(spec, inputs, params)
        # P01 fit + validation years (2005-07 .. 2008-06): all before the first test year
        scored = (bars.dates >= np.datetime64(sandbox.period.fit_start)) & checks.inputs_defined(
            inputs
        )
        problems = checks.check_finite_nonconstant(spec, out, scored, min_finite=0.99)
        if problems:
            failures.append((instrument, problems))
    nonconstant_share = 1 - sum("constant output" in p for _, ps in failures for p in ps) / len(
        instruments
    )
    finite_failures = [f for f in failures if any("finite" in p for p in f[1])]
    assert finite_failures == [], finite_failures
    assert nonconstant_share >= 0.9, failures
