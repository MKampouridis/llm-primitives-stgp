"""Long-only backtest of entry/exit rules with a one-bar execution shift and transaction costs.

Signals are Kleene arrays (1 true, 0 false, NaN unknown) computed from data up to each bar's close.

* Decision at bar t: flat -> long when entry_t = 1 and exit_t != 1; long -> flat when exit_t = 1;
  unknown means no action. Before ``active_from`` the rule is flat and takes no action.
* Execution shift: the position held over bar t is the decision of bar t - lag. With lag = 1 the
  trade happens at the close of the signal bar and earns the next bar's close-to-close return;
  lag = 2 executes one close later (robustness).
* Costs are charged on every change of the held position, buy and sell rates may differ.
* Bars with an unknown return (invalid close) contribute 0; the next valid bar's return spans the gap.

``mode="reverse"`` (GP development E2, D-094) is stop-and-reverse long-short with the same two
trees: flat until the first signal; entry_t = 1 and exit_t != 1 -> long, exit_t = 1 and entry_t
!= 1 -> short; once in the market the rule is always long or short. ``scale`` (optional, one
value per bar, known at that bar's close) multiplies the decision before the execution shift, so
a position is sized with information up to its decision bar only; costs are charged on every
change of the held position, resizing included.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit

from lpstgp.backtest.costs import CostModel


@njit(cache=True)
def decide(entry: np.ndarray, exit_: np.ndarray, active_from: int) -> np.ndarray:
    """Position (0/1) decided at the close of each bar."""
    n = len(entry)
    out = np.zeros(n)
    state = 0.0
    for t in range(n):
        if t >= active_from:
            if state == 0.0 and entry[t] == 1.0 and exit_[t] != 1.0:
                state = 1.0
            elif state == 1.0 and exit_[t] == 1.0:
                state = 0.0
        out[t] = state
    return out


@njit(cache=True)
def decide_reverse(entry: np.ndarray, exit_: np.ndarray, active_from: int) -> np.ndarray:
    """Position (-1/0/+1) decided at the close of each bar: stop-and-reverse long-short."""
    n = len(entry)
    out = np.zeros(n)
    state = 0.0
    for t in range(n):
        if t >= active_from:
            go_long = entry[t] == 1.0 and exit_[t] != 1.0
            go_short = exit_[t] == 1.0 and entry[t] != 1.0
            if go_long:
                state = 1.0
            elif go_short:
                state = -1.0
        out[t] = state
    return out


@njit(cache=True)
def decide_batch(entry: np.ndarray, exit_: np.ndarray, active_from: np.ndarray) -> np.ndarray:
    out = np.empty(entry.shape)
    for k in range(entry.shape[0]):
        out[k] = decide(entry[k], exit_[k], active_from[k])
    return out


@njit(cache=True)
def decide_reverse_batch(
    entry: np.ndarray, exit_: np.ndarray, active_from: np.ndarray
) -> np.ndarray:
    out = np.empty(entry.shape)
    for k in range(entry.shape[0]):
        out[k] = decide_reverse(entry[k], exit_[k], active_from[k])
    return out


MODES = ("long_only", "reverse")


def held(decisions: np.ndarray, lag: int) -> np.ndarray:
    """Position held over each bar: the decision ``lag`` bars earlier (flat before)."""
    out = np.zeros_like(decisions)
    out[..., lag:] = decisions[..., :-lag] if lag else decisions
    return out


@dataclass(frozen=True)
class BacktestResult:
    held: np.ndarray  # position over each bar
    gross: np.ndarray  # simple returns before costs
    cost: np.ndarray  # cost paid in each bar
    net: np.ndarray  # simple returns after costs


def run(
    entry: np.ndarray,
    exit_: np.ndarray,
    log_return: np.ndarray,
    costs: CostModel,
    active_from: int | np.ndarray = 0,
    lag: int = 1,
    mode: str = "long_only",
    scale: np.ndarray | None = None,
) -> BacktestResult:
    """Backtest one rule (1-d signals) or a batch (2-d: individuals x bars) on one asset."""
    if mode not in MODES:
        raise ValueError(f"position mode {mode!r} is not one of {MODES}")
    batch = entry.ndim == 2
    entry2 = np.atleast_2d(np.asarray(entry, dtype=np.float64))
    exit2 = np.atleast_2d(np.asarray(exit_, dtype=np.float64))
    starts = np.broadcast_to(np.asarray(active_from, dtype=np.int64), (entry2.shape[0],)).copy()
    decide_all = decide_batch if mode == "long_only" else decide_reverse_batch
    decisions = decide_all(entry2, exit2, starts)
    if scale is not None:
        decisions = decisions * np.asarray(scale, dtype=np.float64)
    position = held(decisions, lag)
    simple = np.where(np.isnan(log_return), 0.0, np.expm1(np.nan_to_num(log_return)))
    gross = position * simple
    change = np.diff(position, axis=1, prepend=0.0)
    buy, sell = costs.rates(position.shape[1])
    cost = np.where(change > 0, change * buy, -change * sell)
    net = gross - cost
    if not batch:
        return BacktestResult(position[0], gross[0], cost[0], net[0])
    return BacktestResult(position, gross, cost, net)
