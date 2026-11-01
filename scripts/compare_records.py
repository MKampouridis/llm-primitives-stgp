"""Compare two copies of a campaign's run records (e.g. the Mac's and CERES's): same rules?

Usage: uv run python scripts/compare_records.py DIR_A DIR_B
Each DIR is a campaign folder (results/campaigns/<name>). Records are matched by file name and
compared on everything that is a result (hall of fame, selection, generations, budget); timings,
paths, environment and creation times are expected to differ and are ignored.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RESULT_KEYS = (
    "hall_of_fame", "selected", "generations", "budget", "validation_checkpoints", "selection",
)  # fmt: skip


def results(record: dict) -> dict:
    """The record's results, without per-generation timings (keys ending in _s)."""
    out = {k: record.get(k) for k in RESULT_KEYS}
    if out["generations"]:
        out["generations"] = [
            {k: v for k, v in g.items() if not k.endswith("_s")} for g in out["generations"]
        ]
    return out


def load(folder: Path) -> dict[str, dict]:
    return {p.name: json.loads(p.read_text()) for p in sorted(folder.glob("tier*/*/*.json"))}


def main() -> None:
    a, b = (load(Path(arg)) for arg in sys.argv[1:3])
    if a.keys() != b.keys() or not a:
        raise SystemExit(f"different record sets: {sorted(a)} vs {sorted(b)}")
    differ = 0
    for name in a:
        ra, rb = results(a[name]), results(b[name])
        keys = [k for k in RESULT_KEYS if ra[k] != rb[k]]
        envs = (a[name].get("environment", {}), b[name].get("environment", {}))
        print(f"{name}: {'IDENTICAL' if not keys else 'DIFFERENT in ' + ', '.join(keys)}")
        print(f"  {envs[0].get('platform', '?')} vs {envs[1].get('platform', '?')}")
        differ += bool(keys)
    raise SystemExit(1 if differ else 0)


if __name__ == "__main__":
    main()
