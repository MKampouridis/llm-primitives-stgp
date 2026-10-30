"""Reference tests for the core (glue) operators."""

import itertools

import numpy as np
import pandas as pd
import pytest

from lpstgp.operators._kernels import SCALE_WINDOW
from lpstgp.operators.registry import discover
from lpstgp.types import BIN_EDGES, N_BINS

OPS = {spec.name: spec for spec in discover().operators.values()}
NAN = np.nan


def kleene(a, b, op):
    known = {(0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (1.0, 1.0)}
    if (a, b) in known:
        return float(op(bool(a), bool(b)))
    if op is bool.__and__:
        return 0.0 if 0.0 in (a, b) else NAN
    return 1.0 if 1.0 in (a, b) else NAN


@pytest.mark.parametrize(("name", "op"), [("and", bool.__and__), ("or", bool.__or__)])
def test_kleene_truth_tables(name, op):
    values = (0.0, 1.0, NAN)
    pairs = list(itertools.product(values, values))
    a = np.array([p[0] for p in pairs])
    b = np.array([p[1] for p in pairs])
    out = OPS[name](a, b)
    expected = np.array([kleene(x, y, op) for x, y in pairs])
    np.testing.assert_array_equal(out, expected)
    np.testing.assert_array_equal(OPS["not"](np.array(values)), np.array([1.0, 0.0, NAN]))


def test_comparators_and_crosses():
    a = np.array([1.0, 2.0, 0.5, NAN, 3.0, 1.0])
    b = np.array([1.5, 1.5, 1.5, 1.5, 1.5, 1.5])
    np.testing.assert_array_equal(OPS["gt"](a, b), [0, 1, 0, NAN, 1, 0])
    np.testing.assert_array_equal(OPS["lt"](a, b), [1, 0, 1, NAN, 0, 1])
    # Kleene: AND(false, unknown) = false, so "not above now" rules out a cross even at bar 0
    np.testing.assert_array_equal(OPS["cross_above"](a, b), [0, 1, 0, NAN, NAN, 0])
    np.testing.assert_array_equal(OPS["cross_below"](a, b), [NAN, 0, 1, 0, 0, 1])


def test_rolling_percentile_and_mean_ksd_match_pandas():
    rng = np.random.default_rng(0)
    x = rng.standard_normal(400)
    s = pd.Series(x)
    np.testing.assert_allclose(
        OPS["rolling_percentile"](x, window=60, q=0.8), s.rolling(60).quantile(0.8), rtol=1e-12
    )
    expected = s.rolling(90).mean() + 2.0 * s.rolling(90).std()
    np.testing.assert_allclose(OPS["mean_ksd"](x, window=90, k=2.0), expected, rtol=1e-10)


def test_fused_thresholds_equal_compositions():
    rng = np.random.default_rng(1)
    x = rng.standard_normal(500)
    composed = OPS["gt"](x, OPS["rolling_percentile"](x, window=120, q=0.9))
    np.testing.assert_array_equal(OPS["exceeds_quantile"](x, window=120, q=0.9), composed)
    composed = OPS["gt"](x, OPS["mean_ksd"](x, window=60, k=-0.5))
    np.testing.assert_array_equal(OPS["exceeds_ksd"](x, window=60, k=-0.5), composed)


def test_rolling_hist_matches_numpy_histogram():
    rng = np.random.default_rng(2)
    x = rng.standard_t(4, 600)
    w = 40
    h = OPS["rolling_hist"](x, window=w)
    t = 500
    window = x[t - SCALE_WINDOW + 1 : t + 1]
    med = np.median(window)
    mad = 1.4826 * np.median(np.abs(window - med))
    z = np.clip(
        (x[t - w + 1 : t + 1] - med) / mad, BIN_EDGES[0], np.nextafter(BIN_EDGES[-1], -np.inf)
    )
    counts, _ = np.histogram(z, bins=BIN_EDGES)
    np.testing.assert_allclose(h[t], (counts + 0.5) / (w + 0.5 * N_BINS), rtol=1e-12)
    assert np.isnan(h[SCALE_WINDOW - 2]).all()
    assert not np.isnan(h[SCALE_WINDOW - 1]).any()


def test_past_hist_matches_numpy_histogram_of_the_previous_block():
    rng = np.random.default_rng(3)
    x = rng.standard_normal(700)
    w, t = 60, 650
    past = OPS["past_hist"](x, window=w)
    window = x[t - SCALE_WINDOW + 1 : t + 1]  # scale is measured at t
    med = np.median(window)
    mad = 1.4826 * np.median(np.abs(window - med))
    block = x[t - 2 * w + 1 : t - w + 1]
    z = np.clip((block - med) / mad, BIN_EDGES[0], np.nextafter(BIN_EDGES[-1], -np.inf))
    counts, _ = np.histogram(z, bins=BIN_EDGES)
    np.testing.assert_allclose(past[t], (counts + 0.5) / (w + 0.5 * N_BINS), rtol=1e-12)


def test_to_path_and_increments_roundtrip():
    rng = np.random.default_rng(4)
    r = rng.standard_normal(50)
    r[10] = NAN
    p = OPS["to_path"](r)
    assert np.isnan(p[10])
    d = OPS["increments"](p)
    np.testing.assert_allclose(d[1:10], r[1:10])
    np.testing.assert_allclose(d[12:], r[12:])


def test_quantile_regime_and_regime_is():
    x = np.concatenate([np.arange(100.0), np.arange(100.0)[::-1]])
    r = OPS["quantile_regime"](x, window=60)
    assert r[99] == 1.0
    assert r[199] == -1.0
    assert np.isnan(r[10])
    np.testing.assert_array_equal(
        OPS["regime_is"](np.array([1.0, 0.0, NAN]), state=1.0), [1.0, 0.0, NAN]
    )
