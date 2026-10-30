import antropy
import numpy as np
import pytest
import pywt
from scipy.linalg import hankel
from scipy.signal import periodogram
from tests.operators.conftest import sample_bars


@pytest.mark.parametrize("w", [15, 60, 120])
def test_spectral_entropy_matches_antropy(ops, returns, w):
    out = ops["spectral_entropy"](returns, window=w)
    for t in sample_bars(len(returns), w):
        seg = returns[t - w + 1 : t + 1]
        assert out[t] == pytest.approx(
            antropy.spectral_entropy(seg, sf=1, method="fft", normalize=True), rel=1e-9
        )


def test_spectral_slope_matches_scipy_gph(ops, returns):
    w = 252
    out = ops["spectral_slope"](returns, window=w)
    m = int(np.floor(np.sqrt(w)))
    for t in sample_bars(len(returns), w):
        freqs, power = periodogram(returns[t - w + 1 : t + 1])
        omega = 2 * np.pi * freqs[1 : m + 1]
        slope = np.polyfit(np.log(4 * np.sin(omega / 2) ** 2), np.log(power[1 : m + 1]), 1)[0]
        assert out[t] == pytest.approx(-slope, rel=1e-8)


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_wavelet_energy_share_matches_pywavelets(ops, returns, level):
    w = 90
    out = ops["wavelet_energy_share"](returns, window=w, level=level)
    used = 16 * (w // 16)
    for t in sample_bars(len(returns), w):
        coeffs = pywt.wavedec(returns[t - used + 1 : t + 1], "haar", level=4)
        energy = {j: np.sum(coeffs[-j] ** 2) for j in range(1, 5)}
        assert out[t] == pytest.approx(energy[level] / sum(energy.values()), rel=1e-10)


def test_ssa_trend_share_matches_hankel_svd(ops, path):
    w = 120
    out = ops["ssa_trend_share"](path, window=w)
    for t in sample_bars(len(path), w):
        seg = path[t - w + 1 : t + 1]
        c = seg - seg.mean()
        sv = np.linalg.svd(hankel(c[:10], c[9:]), compute_uv=False)
        assert out[t] == pytest.approx(sv[0] ** 2 / np.sum(sv**2), rel=1e-9)
