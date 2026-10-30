"""Tier A (cross-asset pilot): universe, raw downloads with manifest, and the offline build.

Raw files are immutable (``raw/{source}/{symbol}/{YYYYMMDD}{suffix}``); every download is recorded
in ``manifest.csv``. The build (raw -> processed Parquet) is pure and offline: it uses the latest
manifest entry per series and only row-local operations, so it is causal.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from lpstgp.config import CONFIG_DIR, REPO_ROOT
from lpstgp.data import manifest as mf
from lpstgp.data import schema
from lpstgp.data.sources import SOURCES

UNIVERSE_FILE = CONFIG_DIR / "universe_tierA.toml"


@dataclass(frozen=True)
class SeriesRef:
    source: str
    symbol: str
    divide_by: str | None = None

    @property
    def components(self) -> tuple[tuple[str, str], ...]:
        parts = [(self.source, self.symbol)]
        if self.divide_by:
            parts.append((self.source, self.divide_by))
        return tuple(parts)

    @property
    def label(self) -> str:
        return f"{self.symbol}/{self.divide_by}" if self.divide_by else self.symbol


@dataclass(frozen=True)
class Instrument:
    id: str
    name: str
    asset_class: str
    region: str
    currency: str
    calendar: str
    qa_calendar: str
    cost_bps: float
    primary: SeriesRef
    alternates: tuple[SeriesRef, ...] = field(default=())


def load_universe(path: Path = UNIVERSE_FILE) -> tuple[Instrument, ...]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    instruments = []
    for item in raw["instrument"]:
        instruments.append(
            Instrument(
                id=item["id"],
                name=item["name"],
                asset_class=item["asset_class"],
                region=item["region"],
                currency=item["currency"],
                calendar=item["calendar"],
                qa_calendar=item.get("qa_calendar", ""),
                cost_bps=float(item["cost_bps"]),
                primary=SeriesRef(**item["primary"]),
                alternates=tuple(SeriesRef(**alt) for alt in item.get("alternates", [])),
            )
        )
    ids = [inst.id for inst in instruments]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate instrument ids in the universe")
    for inst in instruments:
        for ref in (inst.primary, *inst.alternates):
            if ref.source not in SOURCES:
                raise ValueError(f"{inst.id}: unknown source {ref.source}")
        if inst.calendar not in ("business", "7day"):
            raise ValueError(f"{inst.id}: unknown calendar {inst.calendar}")
    return tuple(instruments)


def safe_name(symbol: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", symbol)


def raw_dir(tier_dir: Path, source: str, symbol: str) -> Path:
    return tier_dir / "raw" / source / safe_name(symbol)


def series_components(
    instruments: Iterable[Instrument], include_alternates: bool
) -> list[tuple[str, str]]:
    seen: dict[tuple[str, str], None] = {}
    for inst in instruments:
        refs = (inst.primary, *inst.alternates) if include_alternates else (inst.primary,)
        for ref in refs:
            for component in ref.components:
                seen.setdefault(component, None)
    return list(seen)


def download_series(
    tier_dir: Path, source: str, symbol: str, start: date, end: date, force: bool = False
) -> dict[str, str] | None:
    """Download one raw series unless it already exists; returns the new manifest entry."""
    manifest_path = tier_dir / "manifest.csv"
    if not force and mf.latest_entry(manifest_path, source, symbol) is not None:
        return None
    module = SOURCES[source]
    raw = module.fetch(symbol, start, end)
    now = datetime.now(UTC)
    target = raw_dir(tier_dir, source, symbol) / f"{now:%Y%m%d}{raw.suffix}"
    if target.exists():
        target = target.with_name(f"{now:%Y%m%dT%H%M%S}{raw.suffix}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw.content)
    parsed = module.parse(raw.content)
    entry = {
        "source": source,
        "symbol": symbol,
        "query": raw.query,
        "downloaded_at_utc": now.isoformat(timespec="seconds"),
        "file": str(target.relative_to(tier_dir)),
        "bytes": len(raw.content),
        "sha256": mf.sha256_bytes(raw.content),
        "rows": len(parsed),
        "first_date": str(parsed["date"].min())[:10] if len(parsed) else "",
        "last_date": str(parsed["date"].max())[:10] if len(parsed) else "",
        "tool": raw.tool,
        "tool_version": raw.tool_version,
    }
    mf.append_entry(manifest_path, entry)
    return entry


def download_universe(
    instruments: Iterable[Instrument],
    tier_dir: Path,
    start: date,
    end: date,
    include_alternates: bool = True,
    force: bool = False,
    log: Callable[[str], None] = print,
    pause: float = 2.0,
) -> list[tuple[str, str, str]]:
    """Download every series once; returns ``(source, symbol, status)`` for each component."""
    import time

    results = []
    for source, symbol in series_components(instruments, include_alternates):
        try:
            entry = download_series(tier_dir, source, symbol, start, end, force=force)
            status = (
                "skipped (exists)"
                if entry is None
                else f"ok {entry['rows']} rows {entry['first_date']}..{entry['last_date']}"
            )
            if entry is not None and source == "yahoo":
                time.sleep(pause)  # be gentle with Yahoo's per-IP rate limits
        except Exception as exc:  # report and continue; the manifest stays consistent
            status = f"FAILED: {type(exc).__name__}: {str(exc)[:160]}"
        log(f"{source:9s} {symbol:12s} {status}")
        results.append((source, symbol, status))
    return results


def load_raw_series(
    tier_dir: Path, source: str, symbol: str
) -> tuple[pd.DataFrame, dict[str, str]]:
    entry = mf.latest_entry(tier_dir / "manifest.csv", source, symbol)
    if entry is None:
        raise FileNotFoundError(f"no raw download for {source}:{symbol}")
    content = (tier_dir / entry["file"]).read_bytes()
    if mf.sha256_bytes(content) != entry["sha256"]:
        raise ValueError(f"checksum mismatch for {entry['file']}")
    return SOURCES[source].parse(content), entry


def combine(numerator: pd.DataFrame, denominator: pd.DataFrame) -> pd.DataFrame:
    """Ratio of two close-only series on common dates (row-local)."""
    merged = numerator[["date", "close"]].merge(
        denominator[["date", "close"]], on="date", suffixes=("_n", "_d")
    )
    return pd.DataFrame({"date": merged["date"], "close": merged["close_n"] / merged["close_d"]})


def git_revision() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def assemble(
    ref: SeriesRef, frames: list[pd.DataFrame], end: date
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parsed component frames -> normalised bars (capped at ``end``) and flags. Pure."""
    frame = frames[0] if ref.divide_by is None else combine(frames[0], frames[1])
    frame = frame[
        pd.to_datetime(frame["date"]).to_numpy().astype("datetime64[D]") <= np.datetime64(end)
    ]
    return schema.normalise(frame)


def build_series(
    inst: Instrument, ref: SeriesRef, tier_dir: Path, end: date, role: str
) -> tuple[Path, pd.DataFrame, pd.DataFrame]:
    frames, entries = [], []
    for source, symbol in ref.components:
        frame, entry = load_raw_series(tier_dir, source, symbol)
        frames.append(frame)
        entries.append(entry)
    bars, flags = assemble(ref, frames, end)
    traits = SOURCES[ref.source].describe(ref.symbol)
    meta = {
        "schema_version": schema.SCHEMA_VERSION,
        "instrument_id": inst.id,
        "name": inst.name,
        "tier": "A",
        "role": role,
        "asset_class": inst.asset_class,
        "region": inst.region,
        "currency": inst.currency,
        "calendar": inst.calendar,
        "qa_calendar": inst.qa_calendar,
        "cost_bps": inst.cost_bps,
        "source": ref.source,
        "source_symbol": ref.label,
        "close_only": traits["close_only"],
        "vendor_split_adjusted": traits["vendor_split_adjusted"],
        "raw_files": [{"file": e["file"], "sha256": e["sha256"]} for e in entries],
        "design_end": end.isoformat(),
        "built_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "code_version": git_revision(),
    }
    if role == "primary":
        path = tier_dir / "processed" / f"{inst.id}.parquet"
    else:
        path = (
            tier_dir
            / "processed"
            / "alternates"
            / f"{inst.id}__{ref.source}_{safe_name(ref.label)}.parquet"
        )
    schema.write_parquet(bars, meta, path)
    if not flags.empty:
        flags_path = path.with_suffix(".flags.parquet")
        flags.assign(date=flags["date"].to_numpy().astype("datetime64[D]")).to_parquet(
            flags_path, index=False
        )
    return path, bars, flags


def build_universe(
    instruments: Iterable[Instrument],
    tier_dir: Path,
    end: date,
    include_alternates: bool = True,
    log: Callable[[str], None] = print,
) -> list[tuple[str, str, str]]:
    results = []
    for inst in instruments:
        refs = [("primary", inst.primary)]
        if include_alternates:
            refs += [("alternate", alt) for alt in inst.alternates]
        for role, ref in refs:
            try:
                path, bars, flags = build_series(inst, ref, tier_dir, end, role)
                status = f"ok {len(bars)} bars, {len(flags)} flags -> {path.relative_to(tier_dir)}"
            except Exception as exc:
                status = f"FAILED: {type(exc).__name__}: {str(exc)[:160]}"
            log(f"{inst.id:7s} {role:9s} {ref.source}:{ref.label:14s} {status}")
            results.append((inst.id, role, status))
    return results
