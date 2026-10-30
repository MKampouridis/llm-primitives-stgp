import numpy as np
import ot
import pytest
from scipy import integrate
from scipy.special import ndtri
from scipy.stats import wasserstein_distance
from tests.operators.conftest import sample_bars

from lpstgp.operators.optimal_transport.sinkhorn_divergence__v1 import CENTRES, COST


def test_w1_hist_matches_pot(ops, returns):
    p = ops["rolling_hist"](returns, window=20)
    q = ops["rolling_hist"](returns, window=120)
    out = ops["w1_hist"](p, q)
    ground = np.abs(CENTRES[:, None] - CENTRES[None, :])
    for t in sample_bars(len(returns), 260):
        assert out[t] == pytest.approx(ot.emd2(p[t], q[t], ground), rel=1e-9)
        assert out[t] == pytest.approx(
            ot.wasserstein_1d(CENTRES, CENTRES, p[t], q[t], p=1), rel=1e-9
        )


def entropic_objective(a, b, eps):
    plan = ot.sinkhorn(a, b, COST, reg=eps, method="sinkhorn", stopThr=1e-13, numItermax=200000)
    kl = np.sum(plan * np.log(plan / np.outer(a, b)))
    return np.sum(plan * COST) + eps * kl


@pytest.mark.parametrize("eps", [0.25, 1.0])
def test_sinkhorn_divergence_matches_pot(ops, returns, eps):
    p = ops["rolling_hist"](returns, window=20)
    q = ops["rolling_hist"](returns, window=120)
    out = ops["sinkhorn_divergence"](p, q, epsilon=eps)
    for t in sample_bars(len(returns), 260, k=3):
        expected = entropic_objective(p[t], q[t], eps) - 0.5 * (
            entropic_objective(p[t], p[t], eps) + entropic_objective(q[t], q[t], eps)
        )
        assert out[t] == pytest.approx(expected, rel=1e-6, abs=1e-9)


def test_sinkhorn_divergence_properties(ops, returns):
    p = ops["rolling_hist"](returns, window=20)
    q = ops["past_hist"](returns, window=20)
    spec = ops["sinkhorn_divergence"]
    np.testing.assert_allclose(spec(p, p, epsilon=0.5)[300:], 0.0, atol=1e-9)
    assert np.nanmin(spec(p, q, epsilon=0.25)) >= -1e-9


def test_w2_to_gaussian_matches_quadrature(ops, returns):
    w = 60
    out = ops["w2_to_gaussian"](returns, window=w)
    t = 777
    z = np.sort(returns[t - w + 1 : t + 1])
    z = (z - z.mean()) / z.std(ddof=1)
    total = 0.0
    for i, value in enumerate(z):
        piece, _ = integrate.quad(
            lambda u, v=value: (v - ndtri(u)) ** 2, i / w, (i + 1) / w, limit=200
        )
        total += piece
    assert out[t] == pytest.approx(np.sqrt(total), rel=1e-6)


def test_transport_asymmetry_matches_scipy(ops, returns):
    w = 120
    out = ops["transport_asymmetry"](returns, window=w)
    for t in sample_bars(len(returns), w):
        seg = returns[t - w + 1 : t + 1]
        gains, losses = seg[seg > 0], -seg[seg < 0]
        sign = np.sign(gains.mean() - losses.mean())
        expected = sign * wasserstein_distance(gains, losses) / np.abs(seg).mean()
        assert out[t] == pytest.approx(expected, rel=1e-10)
