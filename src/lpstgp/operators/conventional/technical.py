"""Conventional technical-analysis terminals (close-only, fixed parameters).

These form the GP-TA baseline vocabulary (kept separate from the cross-domain library). Every
indicator has finite memory: EMA-type smoothers are truncated and renormalised, so the output at
bar t depends only on the declared lookback. Williams %R and Donchian position are omitted because,
on closes only, they are affine maps of the stochastic %K.
"""

from collections.abc import Callable

import numpy as np

from lpstgp.operators.contract import Missing, TerminalSpec
from lpstgp.operators.conventional._rolling import (
    ema_length,
    rolling_extreme,
    rolling_mean,
    rolling_std,
    truncated_ema,
    wilder_length,
)
from lpstgp.operators.core._kleene import greater
from lpstgp.types import Bool, Real

MURPHY = "Murphy (1999), Technical Analysis of the Financial Markets, New York Institute of Finance"
GP_TA = "Allen & Karjalainen (1999), Journal of Financial Economics 51(2):245-271"


def _close(log_price: np.ndarray) -> np.ndarray:
    return np.exp(log_price)


def ma_gap(n: int) -> Callable:
    def impl(log_price: np.ndarray, log_return: np.ndarray) -> np.ndarray:
        return np.log(_close(log_price) / rolling_mean(_close(log_price), n))

    return impl


def ma_cross(fast: int, slow: int) -> Callable:
    def impl(log_price: np.ndarray, log_return: np.ndarray) -> np.ndarray:
        close = _close(log_price)
        return np.log(rolling_mean(close, fast) / rolling_mean(close, slow))

    return impl


def roc(n: int) -> Callable:
    def impl(log_price: np.ndarray, log_return: np.ndarray) -> np.ndarray:
        out = np.full(len(log_price), np.nan)
        out[n:] = log_price[n:] - log_price[:-n]
        return out

    return impl


def rsi(n: int) -> Callable:
    length = wilder_length(n)

    def impl(log_price: np.ndarray, log_return: np.ndarray) -> np.ndarray:
        close = _close(log_price)
        change = np.full(len(close), np.nan)
        change[1:] = close[1:] - close[:-1]
        up = truncated_ema(
            np.where(np.isnan(change), np.nan, np.maximum(change, 0.0)), 1.0 / n, length
        )
        down = truncated_ema(
            np.where(np.isnan(change), np.nan, np.maximum(-change, 0.0)), 1.0 / n, length
        )
        with np.errstate(invalid="ignore", divide="ignore"):
            return 100.0 * up / (up + down)

    return impl


def stoch_k(n: int) -> Callable:
    def impl(log_price: np.ndarray, log_return: np.ndarray) -> np.ndarray:
        close = _close(log_price)
        lo, hi = rolling_extreme(close, n, False), rolling_extreme(close, n, True)
        with np.errstate(invalid="ignore", divide="ignore"):
            return 100.0 * (close - lo) / (hi - lo)

    return impl


def bollinger_z(n: int) -> Callable:
    def impl(log_price: np.ndarray, log_return: np.ndarray) -> np.ndarray:
        close = _close(log_price)
        with np.errstate(invalid="ignore", divide="ignore"):
            return (close - rolling_mean(close, n)) / rolling_std(close, n, 0)

    return impl


def breakout(n: int, upper: bool) -> Callable:
    def impl(log_price: np.ndarray, log_return: np.ndarray) -> np.ndarray:
        close = _close(log_price)
        prior = np.full(len(close), np.nan)
        prior[1:] = rolling_extreme(close, n, upper)[:-1]  # extreme of the previous n closes
        return greater(close, prior) if upper else greater(prior, close)

    return impl


def volatility(n: int) -> Callable:
    def impl(log_price: np.ndarray, log_return: np.ndarray) -> np.ndarray:
        return rolling_std(np.asarray(log_return, dtype=np.float64), n, 1)

    return impl


MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9


def macd_hist() -> Callable:
    def impl(log_price: np.ndarray, log_return: np.ndarray) -> np.ndarray:
        close = _close(log_price)
        fast = truncated_ema(close, 2.0 / (MACD_FAST + 1), ema_length(MACD_FAST))
        slow = truncated_ema(close, 2.0 / (MACD_SLOW + 1), ema_length(MACD_SLOW))
        line = np.log(fast / slow)
        signal = truncated_ema(line, 2.0 / (MACD_SIGNAL + 1), ema_length(MACD_SIGNAL))
        return line - signal

    return impl


def _terminal(
    name, summary, output, lookback, missing, definition, references, reference_test, impl
):
    return TerminalSpec(
        name=name,
        version=1,
        domain="technical",
        summary=summary,
        output=output,
        lookback=lookback,
        missing=missing,
        definition=definition,
        references=references,
        reference_test=reference_test,
        impl=impl,
    )


TERMINALS = (
    *[
        _terminal(f"ma_gap_{n}", f"log(close / SMA{n})", Real, n, Missing.PROPAGATE,
                  rf"\log(C_t/\mathrm{{SMA}}_{{{n}}}(C)_t)", (MURPHY, GP_TA), "pandas rolling mean", ma_gap(n))
        for n in (20, 50, 200)
    ],
    *[
        _terminal(f"ma_cross_{f}_{s}", f"log(SMA{f} / SMA{s})", Real, s, Missing.PROPAGATE,
                  rf"\log(\mathrm{{SMA}}_{{{f}}}/\mathrm{{SMA}}_{{{s}}})", (MURPHY, GP_TA), "pandas rolling mean",
                  ma_cross(f, s))
        for f, s in ((5, 20), (10, 50), (50, 200))
    ],
    *[
        _terminal(f"roc_{n}", f"{n}-bar log return (momentum)", Real, n + 1, Missing.PROPAGATE,
                  rf"\log(C_t/C_{{t-{n}}})", (MURPHY, GP_TA), "numpy", roc(n))
        for n in (5, 20, 60)
    ],
    *[
        _terminal(f"rsi_{n}", f"Wilder RSI({n}), smoothing truncated after {wilder_length(n)} bars", Real,
                  wilder_length(n) + 1, Missing.PROPAGATE,
                  r"100\,\bar U/(\bar U + \bar D), Wilder averages (\alpha = 1/n) of up/down close changes",
                  ("Wilder (1978), New Concepts in Technical Trading Systems, Trend Research", MURPHY),
                  "ta.momentum.RSIIndicator after warm-up", rsi(n))
        for n in (7, 14, 28)
    ],
    *[
        _terminal(f"stoch_k_{n}", f"stochastic %K({n}) on closes", Real, n, Missing.PROPAGATE,
                  rf"100(C_t - \min_{{{n}}} C)/(\max_{{{n}}} C - \min_{{{n}}} C)",
                  ("Lane (1984), Technical Analysis of Stocks & Commodities 2(3)", MURPHY),
                  "pandas rolling min/max", stoch_k(n))
        for n in (14, 28)
    ],
    *[
        _terminal(f"bollinger_z_{n}", f"(close - SMA{n}) / SD{n} (Bollinger %b in sd units)", Real, n,
                  Missing.PROPAGATE, rf"(C_t - \mathrm{{SMA}}_{{{n}}})/\sigma_{{{n}}}",
                  ("Bollinger (2001), Bollinger on Bollinger Bands, McGraw-Hill",),
                  "pandas rolling mean/std(ddof=0)", bollinger_z(n))
        for n in (20, 50)
    ],
    *[
        _terminal(f"breakout_{'high' if up else 'low'}_{n}",
                  f"close {'above the highest' if up else 'below the lowest'} of the previous {n} closes",
                  Bool, n + 1, Missing.PROPAGATE,
                  rf"\mathbb 1\{{C_t {'>' if up else '<'} {'max' if up else 'min'}(C_{{t-{n}}},\dots,C_{{t-1}})\}}",
                  ("Donchian (1960), Commodity Year Book; channel breakout", GP_TA),
                  "pandas rolling max/min shifted by one", breakout(n, up))
        for up in (True, False)
        for n in (20, 55)
    ],
    *[
        _terminal(f"volatility_{n}", f"sd of the last {n} log returns", Real, n + 1, Missing.PROPAGATE,
                  rf"\mathrm{{sd}}(r_{{t-{n}+1}},\dots,r_t)", (MURPHY,), "pandas rolling std", volatility(n))
        for n in (20, 60)
    ],
    _terminal("macd_hist", "log(EMA12/EMA26) minus its EMA9 signal (truncated EMAs)", Real,
              ema_length(MACD_SLOW) + ema_length(MACD_SIGNAL) - 1, Missing.PROPAGATE,
              r"M_t - \mathrm{EMA}_9(M)_t, M = \log(\mathrm{EMA}_{12}(C)/\mathrm{EMA}_{26}(C))",
              ("Appel (2005), Technical Analysis: Power Tools for Active Investors, FT Prentice Hall", MURPHY),
              "pandas ewm(adjust=False) after warm-up", macd_hist()),
)  # fmt: skip
