"""Data-quality assessment for the data reports: availability and integrity *counts* only.

No prices, return statistics or performance are reported. Jump flags use a trailing (causal)
robust scale and are reported as counts, so roll gaps in continuous futures can be compared with
roll-free proxies without inspecting values.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from lpstgp.splits import Period, is_eligible


def _weekdays(first: np.datetime64, last: np.datetime64) -> np.ndarray:
    if last < first:
        return np.array([], dtype="datetime64[D]")
    days = np.arange(first, last + np.timedelta64(1, "D"))
    return days[np.is_busday(days)]


@lru_cache(maxsize=64)
def _exchange_sessions(code: str, first: date, last: date) -> np.ndarray:
    """Exchange sessions in [first, last]; weekdays outside the calendar's supported range."""
    import exchange_calendars as xc

    lo, hi = pd.Timestamp(first), pd.Timestamp(last)
    calendar_type = type(xc.get_calendar(code))
    bound_min, bound_max = calendar_type.bound_min(), calendar_type.bound_max()
    supported_lo = max(lo, bound_min) if bound_min is not None else lo
    supported_hi = min(hi, bound_max) if bound_max is not None else hi
    if supported_hi < supported_lo:
        return _weekdays(np.datetime64(first, "D"), np.datetime64(last, "D"))
    # Build a little past the end so that a holiday on the last day is not "out of bounds".
    cal = xc.get_calendar(code, start=supported_lo, end=supported_hi + pd.Timedelta(days=7))
    s_lo, s_hi = max(supported_lo, cal.first_session), min(supported_hi, cal.last_session)
    sessions = cal.sessions_in_range(s_lo, s_hi) if s_lo <= s_hi else pd.DatetimeIndex([])
    one_day = np.timedelta64(1, "D")
    # Weekdays only outside the calendar's *supported range* (not merely before its first session).
    before = _weekdays(np.datetime64(first, "D"), np.datetime64(supported_lo.date(), "D") - one_day)
    after = _weekdays(np.datetime64(supported_hi.date(), "D") + one_day, np.datetime64(last, "D"))
    return np.concatenate([before, sessions.to_numpy().astype("datetime64[D]"), after])


def expected_sessions(calendar: str, qa_calendar: str, first: date, last: date) -> np.ndarray:
    """Sessions a complete series would have: all days (7day), an exchange calendar, or weekdays."""
    if calendar == "7day":
        return np.arange(
            np.datetime64(first, "D"), np.datetime64(last, "D") + np.timedelta64(1, "D")
        )
    if qa_calendar:
        return _exchange_sessions(qa_calendar, first, last)
    return _weekdays(np.datetime64(first, "D"), np.datetime64(last, "D"))


def longest_gap(present: np.ndarray, expected: np.ndarray) -> int:
    """Longest run of consecutive expected sessions with no bar."""
    missing = ~np.isin(expected, present)
    best = run = 0
    for flag in missing:
        run = run + 1 if flag else 0
        best = max(best, run)
    return best


def stale_runs(close: np.ndarray, min_len: int) -> int:
    """Number of runs of at least ``min_len`` identical consecutive valid closes."""
    values = close[np.isfinite(close)]
    if len(values) < min_len:
        return 0
    count, run = 0, 1
    for prev, cur in itertools.pairwise(values):
        if cur == prev:
            run += 1
        else:
            count += run >= min_len
            run = 1
    return count + (run >= min_len)


def jump_flags(close: np.ndarray, sigma: float, window: int) -> int:
    """Bars whose |log return| exceeds ``sigma`` trailing robust sds (scale from earlier bars only)."""
    values = close[np.isfinite(close)]
    if len(values) <= window + 1:
        return 0
    r = np.diff(np.log(values))
    flags = 0
    for t in range(window, len(r)):
        past = r[t - window : t]
        scale = 1.4826 * np.median(np.abs(past - np.median(past)))
        if scale > 0 and abs(r[t]) > sigma * scale:
            flags += 1
    return flags


def assess(
    frame: pd.DataFrame,
    flags: pd.DataFrame,
    meta: Mapping[str, Any],
    periods: Sequence[Period],
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    dates = frame["date"].to_numpy().astype("datetime64[D]")
    close = frame["close"].to_numpy(dtype="float64")
    valid = np.isfinite(close)
    valid_dates = dates[valid]
    if not len(valid_dates):
        return {"bars": 0}
    first = valid_dates[0].astype(object)
    last = valid_dates[-1].astype(object)
    calendar, qa_calendar = meta["calendar"], meta.get("qa_calendar", "")
    expected = expected_sessions(calendar, qa_calendar, first, last)
    present = np.isin(expected, valid_dates)
    flag_counts = flags["flag"].value_counts().to_dict() if len(flags) else {}
    q = settings["quality"]
    splits_cfg = settings["splits"]
    # The eligibility calendar spans all periods (the last test end is exclusive).
    last_day = periods[-1].test_end - timedelta(days=1)
    full_expected = expected_sessions(
        calendar, qa_calendar, min(first, periods[0].fit_start), last_day
    )
    eligible = [
        p.id
        for p in periods
        if is_eligible(
            valid_dates,
            full_expected,
            p,
            splits_cfg["lookback_max_bars"],
            splits_cfg["min_session_coverage"],
        )
    ]
    volume = frame["volume"].to_numpy(dtype="float64")
    return {
        "bars": int(valid.sum()),
        "first": first,
        "last": last,
        "expected": len(expected),
        "missing": int((~present).sum()),
        "extra": int(np.count_nonzero(~np.isin(valid_dates, expected))),
        "coverage": float(present.mean()) if len(expected) else float("nan"),
        "longest_gap": longest_gap(valid_dates, expected),
        "invalid_close": int(
            np.count_nonzero(~valid)
        ),  # flagged bars are set to NaN: count each once
        "ohlc_violation": int(flag_counts.get("ohlc_violation", 0)),
        "stale_runs": stale_runs(close, q["stale_run_min"]),
        "jump_flags": jump_flags(close, q["jump_sigma"], q["jump_window"]),
        "volume_share": float(np.mean(np.isfinite(volume[valid]) & (volume[valid] > 0))),
        "close_only": bool(meta.get("close_only", False)),
        "eligible": eligible,
    }


def eligible_span(ids: Sequence[str]) -> str:
    if not ids:
        return "none"
    return f"{ids[0]}–{ids[-1]} ({len(ids)})" if len(ids) > 1 else f"{ids[0]} (1)"


def render_table(rows: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]]) -> str:
    header = (
        "| Instrument | Class | Source | Close-only | First | Last | Bars | Coverage | Missing | Longest gap | "
        "Invalid | OHLC viol. | Stale runs | Jump flags | Volume share | Eligible periods |\n"
        "|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|\n"
    )
    lines = []
    for meta, result in rows:
        if not result.get("bars"):
            lines.append(
                f"| {meta['instrument_id']} | {meta['asset_class']} | {meta['source']}:{meta['source_symbol']} | | | | 0 | | | | | | | | | none |"
            )
            continue
        lines.append(
            f"| {meta['instrument_id']} | {meta['asset_class']} | {meta['source']}:{meta['source_symbol']} | "
            f"{'yes' if result['close_only'] else 'no'} | {result['first']} | {result['last']} | {result['bars']} | "
            f"{result['coverage']:.1%} | {result['missing']} | {result['longest_gap']} | {result['invalid_close']} | "
            f"{result['ohlc_violation']} | {result['stale_runs']} | {result['jump_flags']} | "
            f"{result['volume_share']:.0%} | {eligible_span(result['eligible'])} |"
        )
    return header + "\n".join(lines) + "\n"
