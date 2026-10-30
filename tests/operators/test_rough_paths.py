import itertools

import numpy as np
import pytest
import roughpy as rp
from tests.operators.conftest import sample_bars

from lpstgp.operators.rough_paths._paths import signature3
from lpstgp.operators.rough_paths.p_variation__v1 import p_variation_exact


def roughpy_signature(increments: np.ndarray, depth: int) -> np.ndarray:
    ctx = rp.get_context(width=2, depth=depth, coeffs=rp.DPReal)
    stream = rp.LieIncrementStream.from_increments(increments, ctx=ctx)
    return np.array(stream.signature(rp.RealInterval(0, len(increments)), depth=depth))


def z_increments(p, t, w):
    d = np.diff(p[t - w : t + 1])
    return d / d.std(ddof=1)


def test_levy_area_matches_roughpy(ops, path):
    w = 30
    q = np.cumsum(np.abs(np.diff(path, prepend=path[0])))  # a second path: cumulative volatility
    out = ops["levy_area"](path, q, window=w)
    for t in sample_bars(len(path), w):
        sig = roughpy_signature(
            np.column_stack([z_increments(path, t, w), z_increments(q, t, w)]), 2
        )
        assert out[t] == pytest.approx((sig[4] - sig[5]) / 2 / w, rel=1e-9, abs=1e-12)


def test_chord_area_matches_roughpy(ops, path):
    w = 60
    out = ops["chord_area"](path, window=w)
    for t in sample_bars(len(path), w):
        inc = np.column_stack([np.full(w, 1 / w), z_increments(path, t, w) / np.sqrt(w)])
        sig = roughpy_signature(inc, 2)
        assert out[t] == pytest.approx((sig[4] - sig[5]) / 2, rel=1e-9, abs=1e-12)


def test_signature_kernel_matches_roughpy(path):
    rng = np.random.default_rng(3)
    inc = rng.standard_normal((25, 2))
    ours = signature3(inc[:, 0], inc[:, 1])
    np.testing.assert_allclose(ours, roughpy_signature(inc, 3)[1:], rtol=1e-10, atol=1e-12)


def test_signature_similarity_definition(ops, path):
    w = 40
    out = ops["signature_similarity"](path, window=w)
    for t in sample_bars(len(path), 2 * w, k=3):
        a = roughpy_signature(
            np.column_stack([np.full(w, 1 / w), z_increments(path, t, w) / np.sqrt(w)]), 3
        )[1:]
        b = roughpy_signature(
            np.column_stack([np.full(w, 1 / w), z_increments(path, t - w, w) / np.sqrt(w)]), 3
        )[1:]
        assert out[t] == pytest.approx(a @ b / np.linalg.norm(a) / np.linalg.norm(b), rel=1e-9)


def brute_force_p_variation(x, p):
    n = len(x)
    best = 0.0
    for k in range(n - 1):
        for cut in itertools.combinations(range(1, n - 1), k):
            points = (0, *cut, n - 1)
            best = max(best, sum(abs(x[b] - x[a]) ** p for a, b in itertools.pairwise(points)))
    return best


@pytest.mark.parametrize("p", [2.0, 2.5, 3.0])
def test_p_variation_dp_matches_brute_force(p):
    rng = np.random.default_rng(int(p * 10))
    for _ in range(5):
        x = np.cumsum(rng.standard_normal(10))
        assert p_variation_exact(x, p) == pytest.approx(brute_force_p_variation(x, p), rel=1e-12)


def test_p_variation_operator(ops, path):
    w = 10
    out = ops["p_variation"](path, window=w, pvar=2.0)
    t = 500
    seg = path[t - w : t + 1]
    fine = np.sum(np.abs(np.diff(seg)) ** 2)
    assert out[t] == pytest.approx(np.log(brute_force_p_variation(seg, 2.0) / fine), rel=1e-12)
    assert np.nanmin(out) >= 0.0
