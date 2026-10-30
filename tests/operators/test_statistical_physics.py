import numpy as np
import pytest
from scipy.stats import entropy
from statsmodels.nonparametric.kernel_regression import KernelReg
from statsmodels.tsa.stattools import acf
from tests.operators.conftest import sample_bars


def test_critical_slowing_matches_statsmodels(ops, returns):
    w = 120
    out = ops["critical_slowing"](returns, window=w)
    for t in sample_bars(len(returns), w):
        y = np.abs(returns[t - w + 1 : t + 1])
        trend = np.polyval(np.polyfit(np.arange(w), y, 1), np.arange(w))
        assert out[t] == pytest.approx(acf(y - trend, nlags=1, fft=False)[1], rel=1e-8)


def test_kramers_moyal_drift_matches_kernel_regression(ops, path):
    w = 120
    out = ops["kramers_moyal_drift"](path, window=w)
    for t in sample_bars(len(path), w, k=4):
        seg = path[t - w + 1 : t + 1]
        z = (seg - seg.mean()) / seg.std(ddof=1)
        h = 1.06 * (w - 1) ** (-0.2)
        model = KernelReg(endog=np.diff(z), exog=z[:-1], var_type="c", reg_type="lc", bw=[h])
        assert out[t] == pytest.approx(model.fit(np.array([z[-1]]))[0][0], rel=1e-7)


def test_kramers_moyal_drift_sees_mean_reversion(ops):
    rng = np.random.default_rng(9)
    x = np.zeros(3000)
    for t in range(1, 3000):
        x[t] = 0.8 * x[t - 1] + rng.standard_normal()
    w = 252
    drift = ops["kramers_moyal_drift"](x, window=w)
    high = [t for t in range(w, 3000) if x[t] >= np.quantile(x[t - w + 1 : t + 1], 0.9)]
    low = [t for t in range(w, 3000) if x[t] <= np.quantile(x[t - w + 1 : t + 1], 0.1)]
    assert np.mean(drift[high]) < 0  # from high states the expected move is down
    assert np.mean(drift[low]) > 0


def test_tsallis_entropy_formula_and_shannon_limit(ops, returns):
    h = ops["rolling_hist"](returns, window=60)
    spec = ops["tsallis_entropy"]
    t = 900
    for q in (0.5, 2.0):
        expected = (1 - np.sum(h[t] ** q)) / (1 - 16 ** (1 - q))
        assert spec(h, q=q)[t] == pytest.approx(expected, rel=1e-12)
    near_one = spec.impl(h, q=1.0 + 1e-7)[t]
    assert near_one == pytest.approx(entropy(h[t]) / np.log(16), rel=1e-5)


def test_hill_tail_index(ops, returns):
    w = 252
    out = ops["hill_tail_index"](returns, window=w)
    for t in sample_bars(len(returns), w):
        a = np.sort(np.abs(returns[t - w + 1 : t + 1]))[::-1]
        k = max(5, int(0.1 * w))
        assert out[t] == pytest.approx(k / np.sum(np.log(a[:k]) - np.log(a[k])), rel=1e-12)
    pareto = np.random.default_rng(4).pareto(3.0, 20000) + 1.0
    signs = np.where(np.random.default_rng(5).random(20000) < 0.5, -1.0, 1.0)
    estimate = np.nanmean(ops["hill_tail_index"](pareto * signs, window=252))
    assert estimate == pytest.approx(3.0, rel=0.15)
