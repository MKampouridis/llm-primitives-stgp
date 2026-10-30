"""Append-only manifest of downloaded raw files: source, symbol, query, time, checksum."""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Mapping
from pathlib import Path

FIELDS = (
    "source",
    "symbol",
    "query",
    "downloaded_at_utc",
    "file",
    "bytes",
    "sha256",
    "rows",
    "first_date",
    "last_date",
    "tool",
    "tool_version",
)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def append_entry(manifest: Path, entry: Mapping[str, object]) -> None:
    unknown = set(entry) - set(FIELDS)
    if unknown:
        raise ValueError(f"unknown manifest fields {sorted(unknown)}")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    new = not manifest.exists()
    with manifest.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        writer.writerow({key: entry.get(key, "") for key in FIELDS})


def read_entries(manifest: Path) -> list[dict[str, str]]:
    if not manifest.exists():
        return []
    with manifest.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def latest_entry(manifest: Path, source: str, symbol: str) -> dict[str, str] | None:
    """Most recent download of (source, symbol); ties broken by file name."""
    matches = [e for e in read_entries(manifest) if e["source"] == source and e["symbol"] == symbol]
    if not matches:
        return None
    return max(matches, key=lambda e: (e["downloaded_at_utc"], e["file"]))
