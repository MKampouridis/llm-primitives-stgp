"""Data terminals: the base streams of every primitive set (close-only in Tier A)."""

import numpy as np

from lpstgp.operators.contract import Memory, Missing, TerminalSpec
from lpstgp.types import Path, Series


def _log_price(log_price: np.ndarray, log_return: np.ndarray) -> np.ndarray:
    return np.array(log_price, dtype=np.float64)


def _ret(log_price: np.ndarray, log_return: np.ndarray) -> np.ndarray:
    return np.array(log_return, dtype=np.float64)


def _abs_ret(log_price: np.ndarray, log_return: np.ndarray) -> np.ndarray:
    return np.abs(np.asarray(log_return, dtype=np.float64))


TERMINALS = (
    TerminalSpec(
        name="log_price",
        version=1,
        domain="data",
        summary="Log price path (raw log close plus causal event adjustment since the sandbox start).",
        output=Path,
        lookback=1,
        missing=Missing.ELEMENTWISE,
        definition=r"p_t = \log C_t + \sum_{s \le t} a_s, with a_s the dividend/split adjustment at bar s",
        references=(
            "Campbell, Lo & MacKinlay (1997), The Econometrics of Financial Markets, ch. 1",
        ),
        reference_test="identity",
        impl=_log_price,
        size_weight=0,
        memory=Memory.CUMULATIVE,
    ),
    TerminalSpec(
        name="ret",
        version=1,
        domain="data",
        summary="Point-in-time total log return between consecutive valid bars.",
        output=Series,
        lookback=2,
        missing=Missing.ELEMENTWISE,
        definition=r"r_t = p_t - p_{t^-}, t^- the previous valid bar",
        references=(
            "Campbell, Lo & MacKinlay (1997), The Econometrics of Financial Markets, ch. 1",
        ),
        reference_test="identity",
        impl=_ret,
        size_weight=0,
    ),
    TerminalSpec(
        name="abs_ret",
        version=1,
        domain="data",
        summary="Absolute log return (a volatility proxy).",
        output=Series,
        lookback=2,
        missing=Missing.ELEMENTWISE,
        definition=r"|r_t|",
        references=("Ding, Granger & Engle (1993), J. Empirical Finance 1(1):83-106",),
        reference_test="identity",
        impl=_abs_ret,
        size_weight=0,
    ),
)
