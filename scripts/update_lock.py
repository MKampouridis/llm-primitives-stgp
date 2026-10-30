"""Add new operator contracts to the version lock (src/lpstgp/operators/registry.lock.toml).

Locked entries are immutable: if a locked contract's code changed, this script refuses (exit 1) and
lists it; add the modification as a new version file instead.

Usage: uv run python scripts/update_lock.py
"""

from __future__ import annotations

import sys

from lpstgp.operators import registry


def main() -> int:
    changed, unlocked = registry.lock_status()
    if changed:
        print("Locked contracts were modified; add new versions instead:", file=sys.stderr)
        for key in changed:
            print(f"  {key}", file=sys.stderr)
        return 1
    entries = registry.read_lock()
    for key in unlocked:
        entries[key] = registry.contract_hash(key)
    registry.write_lock(entries)
    print(f"locked {len(unlocked)} new contracts; {len(entries)} in total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
