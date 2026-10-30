"""Directional-change (DC) terminals: trend state, events, overshoot, total move and trend age.

A DC event is confirmed when the price reverses by theta from the running extreme (Guillaume et
al. 1997). The state machine is strictly online. To give it finite, exactly checkable memory it is
restarted at the start of a trailing window of WINDOW bars for every bar; with theta <= 4% the
state re-synchronises within the window, so this matches the usual infinite-memory definition
except right after the start of the data.
"""

from collections.abc import Callable

import numpy as np
from numba import njit

from lpstgp.operators.contract import Missing, TerminalSpec
from lpstgp.types import Bool, Real, Regime

WINDOW = 252
THETAS = (0.005, 0.01, 0.02, 0.04)
REFS = (
    "Guillaume, Dacorogna, Dave, Muller, Olsen & Pictet (1997), Finance and Stochastics 1(2):95-129",
    "Glattfelder, Dupuis & Olsen (2011), Quantitative Finance 11(4):599-614",
    "Kampouridis & Otero (2017), Expert Systems with Applications 73:145-160",
    "Long, Kampouridis & Kanellopoulos (2022), PPSN XVII, LNCS 13399:33-47",
)
# output columns of the state machine
TREND, EVENT, OVERSHOOT, TOTAL_MOVE, AGE = range(5)


@njit(cache=True)
def dc_state(p: np.ndarray, start: int, end: int, up: float, down: float) -> np.ndarray:
    """Run the DC machine on log prices p[start..end]; return the 5 outputs at bar `end`."""
    mode = 0
    hi = lo = np.nan
    t_hi = t_lo = start
    ep = dcc = np.nan
    t_ep = -1
    event_at = -1
    for s in range(start, end + 1):
        x = p[s]
        if np.isnan(x):
            continue
        if np.isnan(hi):
            hi = lo = x
            t_hi = t_lo = s
            continue
        if mode >= 0 and x > hi:
            hi, t_hi = x, s
        if mode <= 0 and x < lo:
            lo, t_lo = x, s
        if mode <= 0 and x - lo >= up:  # upturn confirmed
            mode, ep, t_ep, dcc, event_at = 1, lo, t_lo, x, s
            hi, t_hi = x, s
        elif mode >= 0 and hi - x >= down:  # downturn confirmed
            mode, ep, t_ep, dcc, event_at = -1, hi, t_hi, x, s
            lo, t_lo = x, s
    out = np.full(5, np.nan)
    x = p[end]
    if np.isnan(x):
        return out
    out[EVENT] = 1.0 if event_at == end else 0.0
    if mode != 0:
        out[TREND] = float(mode)
        out[OVERSHOOT] = (x - dcc) / up
        out[TOTAL_MOVE] = (x - ep) / up
        out[AGE] = float(end - t_ep)
    return out


@njit(cache=True)
def dc_series(p: np.ndarray, theta: float, window: int, column: int) -> np.ndarray:
    n = len(p)
    out = np.full(n, np.nan)
    up, down = np.log1p(theta), -np.log1p(-theta)
    for t in range(window - 1, n):
        out[t] = dc_state(p, t - window + 1, t, up, down)[column]
    return out


def _impl(theta: float, column: int) -> Callable:
    def impl(log_price: np.ndarray, log_return: np.ndarray) -> np.ndarray:
        return dc_series(np.asarray(log_price, dtype=np.float64), theta, WINDOW, column)

    return impl


def _label(theta: float) -> str:
    return f"{theta * 1000:g}".replace(".", "p")  # 0.005 -> "5" (per mille)


_OUTPUTS = (
    ("trend", TREND, Regime, "+1 after an upturn confirmation, -1 after a downturn (unknown before any)",
     r"\pm1 = direction of the last confirmed DC event"),
    ("event", EVENT, Bool, "a DC event (either direction) is confirmed at this bar",
     r"\mathbb 1\{t = t_{DCC}\}"),
    ("overshoot", OVERSHOOT, Real, "move since the last DC confirmation, in units of theta",
     r"(\log P_t - \log P_{DCC})/\log(1+\theta)"),
    ("total_move", TOTAL_MOVE, Real, "move since the extreme that started the trend, in units of theta",
     r"(\log P_t - \log P_{EP})/\log(1+\theta)"),
    ("age", AGE, Real, "bars since the extreme point that started the current trend", r"t - t_{EP}"),
)  # fmt: skip

TERMINALS = tuple(
    TerminalSpec(
        name=f"dc_{kind}_{_label(theta)}",
        version=1,
        domain="directional_change",
        summary=f"DC (theta = {theta:.1%}): {text}; state machine restarted on the last {WINDOW} bars.",
        output=sem_type,
        lookback=WINDOW,
        missing=Missing.ELEMENTWISE,
        definition=definition + rf", DC threshold \theta = {theta}",
        references=REFS,
        reference_test="independent pure-Python event loop; hand-built price sequences",
        impl=_impl(theta, column),
    )
    for theta in THETAS
    for kind, column, sem_type, text, definition in _OUTPUTS
)
