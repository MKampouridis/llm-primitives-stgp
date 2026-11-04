"""The confidence-bound Sharpe objective for GP development (D-090)."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from lpstgp.backtest.costs import CostModel
from lpstgp.campaign.plan import Config
from lpstgp.config import load_settings
from lpstgp.gp.fitness import FitnessConfig, market_part, prepare, sharpe_lcb

LCB = FitnessConfig(objective="sharpe_lcb", min_entries_per_year=0.0)


def _data(seed=0, n_years=3):
    dates = pd.bdate_range("2004-01-01", periods=252 * n_years).to_numpy().astype("datetime64[D]")
    lr = np.random.default_rng(seed).normal(3e-4, 0.01, len(dates))
    window = (date(2005, 1, 1), date(2006, 12, 31))
    return dates, lr, prepare(dates, lr, "business", window, CostModel(1, 1), 6)


def test_the_bound_is_the_mertens_standard_error_below_the_sharpe_ratio():
    x = np.random.default_rng(1).normal(5e-4, 0.01, 500)
    sr = x.mean() / x.std()
    z = (x - x.mean()) / x.std()
    se = np.sqrt((1 - np.mean(z**3) * sr + (np.mean(z**4) - 1) / 4 * sr**2) / (len(x) - 1))
    assert sharpe_lcb(x, 252, 1.645) == pytest.approx(np.sqrt(252) * (sr - 1.645 * se))
    assert sharpe_lcb(x, 252, 1.645) < np.sqrt(252) * sr
    assert sharpe_lcb(x, 252, 0.0) == pytest.approx(np.sqrt(252) * sr)
    assert sharpe_lcb(np.zeros(100), 252, 1.645) == 0.0


def test_lumpy_returns_score_below_steady_ones_of_the_same_sharpe_ratio():
    """A few large wins (a rule out of the market most days) widen the bound."""
    rng = np.random.default_rng(2)
    steady = rng.normal(4e-4, 0.01, 504)
    lumpy = np.zeros(504)
    lumpy[rng.choice(504, 12, replace=False)] = rng.normal(0.02, 0.01, 12)
    lumpy = (lumpy - lumpy.mean()) / lumpy.std() * steady.std() + steady.mean()  # same mean, sd
    assert sharpe_lcb(lumpy, 252, 1.645) < sharpe_lcb(steady, 252, 1.645)


def test_more_evidence_narrows_the_bound():
    x = np.random.default_rng(3).normal(5e-4, 0.01, 2000)
    assert sharpe_lcb(x[:250], 252, 1.645) < sharpe_lcb(x, 252, 1.645)


def test_the_objective_reads_only_the_scored_window():
    """Poisoned future: bars after the scored window never change the score."""
    dates, lr, data = _data()
    entry = (np.arange(len(dates)) % 30 == 0).astype(float)
    exit_ = (np.arange(len(dates)) % 30 == 15).astype(float)
    value, parts = market_part(entry, exit_, data, LCB)
    poisoned = lr.copy()
    poisoned[data.stop :] = 0.5
    window = (date(2005, 1, 1), date(2006, 12, 31))
    later = prepare(dates, poisoned, "business", window, CostModel(1, 1), 6)
    assert market_part(entry, exit_, later, LCB)[0] == value
    assert parts["sharpe_lcb"] == value < parts["sharpe"]


def test_no_trade_and_minimum_activity_apply_under_either_objective():
    dates, _lr, data = _data()
    flat = np.zeros(len(dates))
    assert market_part(flat, flat, data, LCB)[0] == LCB.no_trade_value
    strict = FitnessConfig(objective="sharpe_lcb", min_entries_per_year=2.0)
    entry, exit_ = flat.copy(), flat.copy()
    entry[data.active_from + 10], exit_[data.active_from + 300] = 1.0, 1.0
    assert market_part(entry, exit_, data, strict)[0] == strict.no_trade_value


def test_earlier_configurations_keep_their_digests_and_the_objective_enters_new_ones():
    settings = load_settings()
    plain = Config("a", "s2c", gp={"population": 250})
    assert plain.digest(settings) == Config("a", "s2c", gp={"population": 250},
                                            fitness={"objective": "composite"}).digest(settings)  # fmt: skip
    lcb = Config("a", "s2c", gp={"population": 250}, fitness={"objective": "sharpe_lcb"})
    assert lcb.digest(settings) != plain.digest(settings)
    with pytest.raises(ValueError, match="objective"):
        FitnessConfig(objective="sortino")
