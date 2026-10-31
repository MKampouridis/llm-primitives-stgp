"""Equal-weight portfolios, the paired stationary bootstrap and Holm's adjustment."""

import numpy as np
import pytest

from lpstgp.analysis.inference import holm, paired_bootstrap, stationary_indices
from lpstgp.analysis.portfolio import average_runs, equal_weight, portfolio_sharpe


def test_average_runs_and_equal_weight_on_the_union_calendar():
    d1 = np.array(["2006-07-03", "2006-07-04", "2006-07-05"], dtype="datetime64[D]")
    d2 = np.array(["2006-07-03", "2006-07-05"], dtype="datetime64[D]")
    inst1 = average_runs([(d1, np.array([0.01, 0.02, 0.03])), (d1, np.array([0.03, 0.0, 0.01]))])
    np.testing.assert_allclose(inst1[1], [0.02, 0.01, 0.02])
    dates, port = equal_weight({"A": inst1, "B": (d2, np.array([0.02, -0.02]))})
    np.testing.assert_array_equal(dates, d1)
    np.testing.assert_allclose(port, [0.02, 0.005, 0.0])  # B is flat on 07-04
    with pytest.raises(ValueError, match="share"):
        average_runs([(d1, np.zeros(3)), (d2, np.zeros(2))])
    assert np.isfinite(portfolio_sharpe((dates, port)))


def test_stationary_indices_have_the_right_mean_block_length():
    rng = np.random.default_rng(0)
    idx = np.concatenate([stationary_indices(500, 10.0, rng) for _ in range(40)])
    assert idx.min() >= 0
    assert idx.max() < 500
    breaks = np.mean(np.diff(idx) != 1)  # a new block starts with probability 1/block (+ wraps)
    assert 0.08 < breaks < 0.12


def test_paired_bootstrap_detects_a_clear_difference_and_not_a_null():
    rng = np.random.default_rng(1)
    common = rng.normal(0, 0.01, 750)
    better = common + 0.002
    strong = paired_bootstrap(better, common, resamples=400, seed=2)
    assert strong.difference > 0
    assert strong.ci_low > 0
    assert strong.p_value < 0.01
    null = paired_bootstrap(common + rng.normal(0, 1e-4, 750), common, resamples=400, seed=2)
    assert null.ci_low < 0 < null.ci_high or abs(null.difference) < 0.05
    with pytest.raises(ValueError, match="same days"):
        paired_bootstrap(common, common[:-1])


def test_holm():
    np.testing.assert_allclose(holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])
    np.testing.assert_allclose(holm([0.5, 0.9]), [1.0, 1.0])
