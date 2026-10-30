"""Download the Tier A pilot data (raw files + manifest). Pilot sources only; see docs/decisions.md.

Usage: uv run python scripts/download_tier_a.py [--only SPX,BTC] [--no-alternates] [--force]
"""

from __future__ import annotations

import argparse

from lpstgp.config import load_paths, load_settings
from lpstgp.data.tier_a import download_universe, load_universe


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="comma-separated instrument ids")
    parser.add_argument("--no-alternates", action="store_true")
    parser.add_argument(
        "--force", action="store_true", help="download again even if a raw file exists"
    )
    args = parser.parse_args()

    paths, settings = load_paths(), load_settings()
    instruments = load_universe()
    if args.only:
        wanted = set(args.only.split(","))
        instruments = tuple(i for i in instruments if i.id in wanted)
    results = download_universe(
        instruments,
        paths.tier_dir("A"),
        start=settings["data"]["download_start"],
        end=settings["data"]["design_end"],
        include_alternates=not args.no_alternates,
        force=args.force,
    )
    failed = [r for r in results if r[2].startswith("FAILED")]
    print(f"\n{len(results)} series, {len(failed)} failed")


if __name__ == "__main__":
    main()
