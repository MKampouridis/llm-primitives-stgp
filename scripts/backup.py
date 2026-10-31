"""Mirror docs, reports, results, raw data and manifests to the backup folder (one-way).

Run at each milestone. Earlier copies of changed or removed files are kept under
``<backup_dir>/_superseded/<UTC timestamp>/``.

Usage: uv run python scripts/backup.py [--dry-run]
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from lpstgp.backup import mirror, write_readme
from lpstgp.config import REPO_ROOT, load_paths
from lpstgp.data.tier_a import git_revision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="list changes, write nothing")
    args = parser.parse_args()

    paths = load_paths()
    if paths.backup_dir is None:
        raise SystemExit("backup_dir is not set in config/paths.toml")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    sources = {
        "docs": REPO_ROOT / "docs",
        "reports": paths.reports_dir,
        "results": paths.results_dir,
        "data": paths.data_dir,
    }
    report = mirror(sources, paths.backup_dir, stamp, dry_run=args.dry_run)
    if not args.dry_run:
        write_readme(paths.backup_dir, stamp, git_revision())
    for rel in report.superseded:
        print(f"superseded  {rel}")
    for rel in report.copied:
        print(f"copied      {rel}")
    verb = "would copy" if args.dry_run else "copied"
    print(
        f"\n{paths.backup_dir}: {verb} {len(report.copied)} files "
        f"({report.bytes_copied / 1e6:.1f} MB), {len(report.superseded)} superseded, "
        f"{report.unchanged} unchanged"
    )


if __name__ == "__main__":
    main()
