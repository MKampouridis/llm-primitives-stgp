import antropy
import nolds
import numpy as np
import pytest
from tests.operators.conftest import sample_bars

from lpstgp.operators.fractal._scaling import scales_for
from lpstgp.operators.fractal.dfa__v1 import MIN_BLOCKS as DFA_BLOCKS
from lpstgp.operators.fractal.hurst_rs__v1 import MIN_BLOCKS as RS_BLOCKS


def fbm(n: int, hurst: float, seed: int) -> np.ndarray:
    """Fractional Brownian motion by the Davies-Harte circulant embedding."""
    rng = np.random.default_rng(seed)
    k = np.arange(n + 1)
    gamma = 0.5 * (np.abs(k - 1) ** (2 * hurst) - 2 * k ** (2 * hurst) + (k + 1) ** (2 * hurst))
    row = np.concatenate([gamma, gamma[-2:0:-1]])
    eig = np.fft.fft(row).real
    eig[eig < 0] = 0
    m = len(row)
    w = rng.standard_normal(m) + 1j * rng.standard_normal(m)
    fgn = np.fft.fft(np.sqrt(eig / m) * w).real[:n]
    return np.cumsum(fgn)


def test_hurst_rs_matches_nolds(ops, returns):
    w = 252
    out = ops["hurst_rs"](returns, window=w)
    scales = list(scales_for(w, RS_BLOCKS))
    for t in sample_bars(len(returns), w, k=4):
        seg = returns[t - w + 1 : t + 1]
        # nolds aligns blocks to the start; on the reversed window they align to our end, and R/S
        # is invariant to reversal
        expected = nolds.hurst_rs(
            seg[::-1], nvals=scales, fit="poly", corrected=False, unbiased=False
        )
        assert out[t] == pytest.approx(expected, rel=1e-9)


def test_dfa_matches_nolds_on_divisible_window(ops, returns):
    w = 96  # every DFA scale divides 96, so box alignment cannot differ
    scales = list(scales_for(w, DFA_BLOCKS))
    assert all(w % n == 0 for n in scales)
    out = ops["dfa"].impl(returns, w)
    for t in sample_bars(len(returns), w, k=4):
        seg = returns[t - w + 1 : t + 1]
        expected = nolds.dfa(
            seg, nvals=scales, overlap=False, order=1, fit_trend="poly", fit_exp="poly"
        )
        assert out[t] == pytest.approx(expected, rel=1e-9)


def textbook_higuchi(x, kmax):
    n = len(x)
    lk = []
    for k in range(1, kmax + 1):
        lm = []
        for m in range(k):
            steps = (n - 1 - m) // k
            total = sum(abs(x[m + i * k] - x[m + (i - 1) * k]) for i in range(1, steps + 1))
            lm.append(total * (n - 1) / (steps * k) / k)
        lk.append(np.mean(lm))
    return -np.polyfit(np.log(np.arange(1, kmax + 1)), np.log(lk), 1)[0]


def test_higuchi_fd(ops, path):
    w = 120
    out = ops["higuchi_fd"](path, window=w, kmax=8)
    for t in sample_bars(len(path), w, k=3):
        seg = path[t - w + 1 : t + 1]
        assert out[t] == pytest.approx(textbook_higuchi(seg, 8), rel=1e-9)
        assert out[t] == pytest.approx(antropy.higuchi_fd(seg, kmax=8), abs=0.05)
    brownian = np.cumsum(np.random.default_rng(1).standard_normal(3000))
    assert np.nanmean(ops["higuchi_fd"](brownian, window=252, kmax=10)) == pytest.approx(
        1.5, abs=0.08
    )


def numpy_ghe(x, q, tau_max=10):
    taus = np.arange(1, tau_max + 1)
    k = [np.mean(np.abs(x[tau:] - x[:-tau]) ** q) for tau in taus]
    return np.polyfit(np.log(taus), np.log(k), 1)[0] / q


@pytest.mark.parametrize("q", [1.0, 2.0])
def test_generalized_hurst_matches_numpy(ops, path, q):
    w = 180
    out = ops["generalized_hurst"](path, window=w, q=q)
    for t in sample_bars(len(path), w, k=4):
        assert out[t] == pytest.approx(numpy_ghe(path[t - w + 1 : t + 1], q), rel=1e-9)


@pytest.mark.parametrize("hurst", [0.3, 0.7])
def test_scaling_estimators_recover_fbm(ops, hurst):
    x = fbm(4000, hurst, seed=int(hurst * 100))
    increments = np.diff(x)
    assert np.nanmean(ops["generalized_hurst"](x, window=252, q=2.0)) == pytest.approx(
        hurst, abs=0.1
    )
    assert np.nanmean(ops["dfa"](increments, window=252)) == pytest.approx(hurst, abs=0.12)
    assert np.nanmean(ops["higuchi_fd"](x, window=252, kmax=10)) == pytest.approx(
        2 - hurst, abs=0.12
    )
