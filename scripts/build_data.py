"""Build processed Parquet files from raw downloads (offline, causal, re-runnable).

Usage: uv run python scripts/build_data.py [--only SPX,BTC] [--no-alternates]
"""

from __future__ import annotations

import argparse

from lpstgp.config import load_paths, load_settings
from lpstgp.data.tier_a import build_universe, load_universe


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="comma-separated instrument ids")
    parser.add_argument("--no-alternates", action="store_true")
    args = parser.parse_args()

    paths, settings = load_paths(), load_settings()
    instruments = load_universe()
    if args.only:
        wanted = set(args.only.split(","))
        instruments = tuple(i for i in instruments if i.id in wanted)
    results = build_universe(
        instruments,
        paths.tier_dir("A"),
        end=settings["data"]["design_end"],
        include_alternates=not args.no_alternates,
    )
    failed = [r for r in results if "FAILED" in r[2]]
    print(f"\n{len(results)} series built, {len(failed)} failed")


if __name__ == "__main__":
    main()
