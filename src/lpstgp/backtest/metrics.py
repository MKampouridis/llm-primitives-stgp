"""Performance metrics on simple net returns (last axis = bars; works on 1-d or batched 2-d input)."""

from __future__ import annotations

import numpy as np

PERIODS_PER_YEAR = {"business": 252, "7day": 365}


def sharpe(net: np.ndarray, periods_per_year: int) -> np.ndarray:
    """Annualised Sharpe ratio (zero risk-free rate); 0 for a series with no variation."""
    mean = net.mean(axis=-1)
    sd = net.std(axis=-1, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(sd > 0, mean / sd * np.sqrt(periods_per_year), 0.0)
    return out


def sortino(net: np.ndarray, periods_per_year: int) -> np.ndarray:
    downside = np.sqrt(np.mean(np.minimum(net, 0.0) ** 2, axis=-1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(downside > 0, net.mean(axis=-1) / downside * np.sqrt(periods_per_year), 0.0)


def max_drawdown(net: np.ndarray) -> np.ndarray:
    """Largest peak-to-trough fall of the compounded equity curve, as a positive fraction."""
    equity = np.cumprod(1.0 + net, axis=-1)
    peak = np.maximum.accumulate(np.maximum(equity, 1.0), axis=-1)
    return np.max(1.0 - equity / peak, axis=-1)


def total_return(net: np.ndarray) -> np.ndarray:
    return np.prod(1.0 + net, axis=-1) - 1.0


def annual_return(net: np.ndarray, periods_per_year: int) -> np.ndarray:
    years = net.shape[-1] / periods_per_year
    return (1.0 + total_return(net)) ** (1.0 / years) - 1.0


def calmar(net: np.ndarray, periods_per_year: int) -> np.ndarray:
    mdd = max_drawdown(net)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(mdd > 0, annual_return(net, periods_per_year) / mdd, 0.0)


def turnover(held: np.ndarray, periods_per_year: int) -> np.ndarray:
    """Annualised one-way turnover: position changes per year (an entry plus an exit = 2)."""
    changes = np.abs(np.diff(held, axis=-1, prepend=0.0)).sum(axis=-1)
    return changes * periods_per_year / held.shape[-1]


def trades(held: np.ndarray) -> np.ndarray:
    """Number of entries (flat -> long transitions)."""
    return (np.diff(held, axis=-1, prepend=0.0) > 0).sum(axis=-1)


def exposure(held: np.ndarray) -> np.ndarray:
    return held.mean(axis=-1)


def summary(net: np.ndarray, held: np.ndarray, periods_per_year: int) -> dict[str, float]:
    """All metrics for one rule (1-d input)."""
    return {
        "sharpe": float(sharpe(net, periods_per_year)),
        "sortino": float(sortino(net, periods_per_year)),
        "max_drawdown": float(max_drawdown(net)),
        "calmar": float(calmar(net, periods_per_year)),
        "total_return": float(total_return(net)),
        "annual_return": float(annual_return(net, periods_per_year)),
        "turnover": float(turnover(held, periods_per_year)),
        "trades": int(trades(held)),
        "exposure": float(exposure(held)),
        "no_trade": bool(trades(held) == 0),
    }
