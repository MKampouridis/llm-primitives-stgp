"""Freeze the accepted WP2 strategies (verbatim copy + lock) and write the catalogue and report.

Usage: uv run python scripts/strategy_freeze.py [--allow-partial]

Refuses to freeze fewer than 28 accepted strategies unless --allow-partial is given.
"""

from __future__ import annotations

import argparse

from lpstgp.config import REPO_ROOT, load_paths
from lpstgp.strategies import freeze, registry
from lpstgp.strategies.generation import all_slots


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    paths = load_paths()
    root = paths.results_dir / "wp2" / "strategy_generation"
    sessions = freeze.summaries(root)
    accepted = [s for s in sessions if s.get("accepted")]
    expected = len(all_slots())
    if len(accepted) < expected and not args.allow_partial:
        raise SystemExit(f"{len(accepted)} of {expected} strategies accepted; use --allow-partial")
    entries = freeze.freeze(accepted, registry.GENERATED_DIR, registry.LOCK_FILE)
    frozen = registry.load_frozen()  # verifies the lock and that every file loads
    assert {f.sid for f in frozen} == set(entries)
    (REPO_ROOT / "docs" / "strategies.md").write_text(freeze.catalogue(accepted), encoding="utf-8")
    out = paths.reports_dir / "wp2" / "strategy_generation.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(freeze.report(sessions), encoding="utf-8")
    print(f"froze {len(entries)} strategies; lock {registry.lock_digest()[:12]}; report {out}")


if __name__ == "__main__":
    main()
