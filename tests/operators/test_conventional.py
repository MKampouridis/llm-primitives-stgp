import numpy as np
import pandas as pd
import pytest
from ta.momentum import RSIIndicator

from lpstgp.operators.conventional import directional_change as dc


@pytest.fixture(scope="module")
def prices(path):
    log_price = path + np.log(100.0)
    log_return = np.full(len(path), np.nan)
    log_return[1:] = np.diff(log_price)
    return log_price, log_return, pd.Series(np.exp(log_price))


def test_moving_average_family(terminals, prices):
    lp, lr, c = prices
    # pandas uses running sums, we sum each window: agreement to the last few ulps only
    np.testing.assert_allclose(
        terminals["ma_gap_50"](lp, lr), np.log(c / c.rolling(50).mean()), rtol=1e-9, atol=1e-12
    )
    expected = np.log(c.rolling(10).mean() / c.rolling(50).mean())
    np.testing.assert_allclose(terminals["ma_cross_10_50"](lp, lr), expected, rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(terminals["roc_20"](lp, lr)[20:], lp[20:] - lp[:-20], rtol=1e-12)


def test_rsi_matches_ta_after_warmup(terminals, prices):
    lp, lr, c = prices
    for n in (7, 14, 28):
        ours = terminals[f"rsi_{n}"](lp, lr)
        reference = RSIIndicator(c, window=n).rsi().to_numpy()
        np.testing.assert_allclose(ours[600:], reference[600:], atol=0.1)


def test_oscillators_and_bands(terminals, prices):
    lp, lr, c = prices
    lo, hi = c.rolling(14).min(), c.rolling(14).max()
    np.testing.assert_allclose(
        terminals["stoch_k_14"](lp, lr), 100 * (c - lo) / (hi - lo), rtol=1e-12
    )
    z = (c - c.rolling(20).mean()) / c.rolling(20).std(ddof=0)
    np.testing.assert_allclose(terminals["bollinger_z_20"](lp, lr), z, rtol=1e-9)
    vol = pd.Series(lr).rolling(60).std()
    np.testing.assert_allclose(terminals["volatility_60"](lp, lr), vol, rtol=1e-10)


def test_breakouts(terminals, prices):
    lp, lr, c = prices
    prior_high = c.rolling(20).max().shift(1)
    expected = np.where(prior_high.isna(), np.nan, (c > prior_high).astype(float))
    np.testing.assert_array_equal(terminals["breakout_high_20"](lp, lr), expected)


def test_macd_hist_matches_pandas_after_warmup(terminals, prices):
    lp, lr, c = prices
    line = np.log(c.ewm(span=12, adjust=False).mean() / c.ewm(span=26, adjust=False).mean())
    expected = line - line.ewm(span=9, adjust=False).mean()
    np.testing.assert_allclose(terminals["macd_hist"](lp, lr)[600:], expected[600:], atol=1e-6)


def naive_dc(log_price, theta, start, end):
    """Independent restatement of the DC state machine (Glattfelder et al. 2011) on p[start..end]."""
    up, down = np.log1p(theta), -np.log1p(-theta)
    trend, extreme_hi, extreme_lo, ep, t_ep, dcc, last_event = (
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    t_hi = t_lo = None
    for s in range(start, end + 1):
        x = log_price[s]
        if extreme_hi is None:
            extreme_hi = extreme_lo = x
            t_hi = t_lo = s
            continue
        if trend in (None, "up") and x > extreme_hi:
            extreme_hi, t_hi = x, s
        if trend in (None, "down") and x < extreme_lo:
            extreme_lo, t_lo = x, s
        if trend in (None, "down") and x - extreme_lo >= up:
            trend, ep, t_ep, dcc, last_event = "up", extreme_lo, t_lo, x, s
            extreme_hi, t_hi = x, s
        elif trend in (None, "up") and extreme_hi - x >= down:
            trend, ep, t_ep, dcc, last_event = "down", extreme_hi, t_hi, x, s
            extreme_lo, t_lo = x, s
    x = log_price[end]
    if trend is None:
        return (np.nan, 1.0 if last_event == end else 0.0, np.nan, np.nan, np.nan)
    return (
        1.0 if trend == "up" else -1.0,
        1.0 if last_event == end else 0.0,
        (x - dcc) / up,
        (x - ep) / up,
        float(end - t_ep),
    )


@pytest.mark.parametrize("theta", dc.THETAS)
def test_directional_change_matches_naive_loop(terminals, prices, theta):
    lp, lr, _ = prices
    label = dc._label(theta)
    names = ("trend", "event", "overshoot", "total_move", "age")
    outputs = [terminals[f"dc_{name}_{label}"](lp, lr) for name in names]
    for t in (dc.WINDOW - 1, 400, 800, 1200, len(lp) - 1):
        expected = naive_dc(lp, theta, t - dc.WINDOW + 1, t)
        got = tuple(o[t] for o in outputs)
        np.testing.assert_allclose(got, expected, rtol=1e-12, equal_nan=True)


def test_directional_change_hand_built_sequence():
    # +5%, -1%, -3% (a 2% downturn from the high is confirmed), +3% (upturn from the low)
    steps = [0.0] * 5 + [0.05, -0.01, -0.03, 0.03]
    p = np.cumsum(steps)
    trend = dc.dc_series(p, 0.02, 9, dc.TREND)[-1]
    event = dc.dc_series(p, 0.02, 9, dc.EVENT)[-1]
    age = dc.dc_series(p, 0.02, 9, dc.AGE)[-1]
    assert trend == 1.0
    assert event == 1.0
    assert age == 1.0  # the upturn started from the low one bar earlier
