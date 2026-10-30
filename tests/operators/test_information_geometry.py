import numpy as np
import ordpy
import pandas as pd
import pytest
from scipy.special import rel_entr
from tests.operators.conftest import sample_bars


def fisher_functional(p):
    return 0.5 * np.sum(np.diff(np.sqrt(p)) ** 2)


def test_fisher_rao_hist_is_the_sphere_angle(ops, returns):
    p = ops["rolling_hist"](returns, window=20)
    q = ops["past_hist"](returns, window=20)
    d = ops["fisher_rao_hist"](p, q)
    for t in sample_bars(len(returns), 260):
        u, v = np.sqrt(p[t]), np.sqrt(q[t])
        assert d[t] == pytest.approx(2 * np.arccos(np.clip(u @ v, -1, 1)), rel=1e-12)
    assert np.nanmax(d) <= np.pi
    np.testing.assert_allclose(ops["fisher_rao_hist"](p, p)[300:], 0.0, atol=1e-6)


def test_fisher_rao_hist_triangle_inequality(ops, returns):
    a = ops["rolling_hist"](returns, window=10)
    b = ops["rolling_hist"](returns, window=60)
    c = ops["past_hist"](returns, window=30)
    f = ops["fisher_rao_hist"]
    ok = ~np.isnan(f(a, b))
    assert np.all(f(a, c)[ok] <= f(a, b)[ok] + f(b, c)[ok] + 1e-12)


def costa_distance(m1, s1, m2, s2):
    """Fisher-Rao distance between N(m1,s1), N(m2,s2) in the log form (Costa et al. 2015)."""
    a = np.array([m1 / np.sqrt(2), s1])
    b = np.array([m2 / np.sqrt(2), s2])
    b_reflected = np.array([m2 / np.sqrt(2), -s2])
    far, near = np.linalg.norm(a - b_reflected), np.linalg.norm(a - b)
    return np.sqrt(2) * np.log((far + near) / (far - near))


def test_fisher_rao_gauss_matches_log_form(ops, returns):
    out = ops["fisher_rao_gauss"](returns, short=20, long=120)
    s = pd.Series(returns)
    m1, s1 = s.rolling(20).mean(), s.rolling(20).std()
    m2, s2 = s.rolling(120).mean(), s.rolling(120).std()
    for t in sample_bars(len(returns), 130):
        assert out[t] == pytest.approx(costa_distance(m1[t], s1[t], m2[t], s2[t]), rel=1e-7)


def test_fisher_information_functional_matches_ordpy(ops, returns):
    seg = returns[:500]
    _, probs = ordpy.ordinal_distribution(seg, dx=4, return_missing=True)
    assert fisher_functional(probs) == pytest.approx(ordpy.fisher_shannon(seg, dx=4)[1], rel=1e-12)
    h = ops["rolling_hist"](returns, window=60)
    out = ops["fisher_information"](h)
    for t in sample_bars(len(returns), 260):
        assert out[t] == pytest.approx(fisher_functional(h[t]), rel=1e-12)


def test_alpha_divergence_special_cases(ops, returns):
    p = ops["rolling_hist"](returns, window=20)
    q = ops["rolling_hist"](returns, window=120)
    spec = ops["alpha_divergence"]
    t = 600
    bc = np.sum(np.sqrt(p[t] * q[t]))
    assert spec(p, q, alpha=0.0)[t] == pytest.approx(4 * (1 - bc), rel=1e-12)
    # duality D_alpha(p||q) = D_{-alpha}(q||p)
    np.testing.assert_allclose(spec(p, q, alpha=0.5), spec(q, p, alpha=-0.5), rtol=1e-12)
    # the alpha -> -1 limit is KL(p||q) (impl called directly: -0.999 is off the parameter grid)
    kl = rel_entr(p[t], q[t]).sum()
    assert spec.impl(p, q, alpha=-0.999)[t] == pytest.approx(kl, rel=2e-2)
