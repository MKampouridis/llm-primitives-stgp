import antropy
import numpy as np
import ordpy
import pytest
from scipy.stats import entropy
from sklearn.metrics import mutual_info_score
from tests.operators.conftest import sample_bars


def test_shannon_entropy_matches_scipy(ops, returns):
    h = ops["rolling_hist"](returns, window=40)
    out = ops["shannon_entropy"](h)
    for t in sample_bars(len(returns), 260):
        assert out[t] == pytest.approx(entropy(h[t]) / np.log(16), rel=1e-12)


@pytest.mark.parametrize("order", [3, 4, 5])
def test_permutation_entropy_matches_ordpy_and_antropy(ops, returns, order):
    w = 120
    out = ops["permutation_entropy"](returns, window=w, order=order)
    for t in sample_bars(len(returns), w):
        seg = returns[t - w + 1 : t + 1]
        assert out[t] == pytest.approx(ordpy.permutation_entropy(seg, dx=order), rel=1e-10)
        assert out[t] == pytest.approx(
            antropy.perm_entropy(seg, order=order, normalize=True), rel=1e-10
        )


@pytest.mark.parametrize("levels", [2, 3, 4])
def test_lz_compressibility_matches_antropy(ops, returns, levels):
    w = 120
    out = ops["lz_compressibility"](returns, window=w, levels=levels)
    for t in sample_bars(len(returns), w):
        seg = returns[t - w + 1 : t + 1]
        thresholds = np.quantile(seg, [k / levels for k in range(1, levels)])
        symbols = np.searchsorted(thresholds, seg, side="right")
        assert out[t] == pytest.approx(antropy.lziv_complexity(symbols, normalize=True), rel=1e-12)


@pytest.mark.parametrize("lag", [1, 5])
def test_lagged_mutual_info_matches_sklearn(ops, returns, lag):
    w = 180
    out = ops["lagged_mutual_info"](returns, window=w, lag=lag)
    for t in sample_bars(len(returns), w):
        seg = returns[t - w + 1 : t + 1]
        thresholds = np.quantile(seg, [0.25, 0.5, 0.75])
        now = np.searchsorted(thresholds, seg[lag:], side="right")
        before = np.searchsorted(thresholds, seg[:-lag], side="right")
        assert out[t] == pytest.approx(
            mutual_info_score(now, before) / np.log(4), rel=1e-10, abs=1e-12
        )


def test_lagged_mutual_info_detects_dependence(ops):
    rng = np.random.default_rng(5)
    noise = rng.standard_normal(2000)
    ar = np.zeros(2000)
    for t in range(1, 2000):
        ar[t] = 0.9 * ar[t - 1] + noise[t]
    mi_ar = np.nanmean(ops["lagged_mutual_info"](ar, window=252, lag=1))
    mi_iid = np.nanmean(ops["lagged_mutual_info"](noise, window=252, lag=1))
    assert mi_ar > 5 * mi_iid
