"""Run or inspect slices of a campaign plan: one SGE job-array element runs one slice.

Usage:
  uv run python scripts/campaign_tasks.py status --campaign wp2-calibration
  uv run python scripts/campaign_tasks.py run --campaign wp2-calibration --index 0 [--count 1]

A plan is results_dir/campaigns/<campaign>/tasks.json (written by scripts/wp2_pilot.py STEP
--mode plan). `run` does tasks index .. index + count - 1 in this process, after checking the
plan's settings, data and library digests; finished tasks are skipped, so a slice can be repeated.
`status` also prints the number of array elements and the qsub line for a given --count.
"""

from __future__ import annotations

import argparse
import json
import math

from lpstgp.campaign.execute import execute_slice, load_plan, progress
from lpstgp.config import load_paths, load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "run"))
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()
    paths, settings = load_paths(), load_settings()
    plan_path = paths.results_dir / "campaigns" / args.campaign / "tasks.json"
    if args.action == "run":
        print(json.dumps(execute_slice(plan_path, paths, settings, args.index, args.count)))
        return
    status = progress(plan_path, settings)
    elements = math.ceil(status["tasks"] / args.count)
    print(json.dumps(status | {"configs": len(load_plan(plan_path)["configs"])}))
    print(
        f"qsub -t 1-{elements} -tc 60 -v CAMPAIGN={args.campaign},COUNT={args.count} "
        "scripts/ceres/tasks.sge"
    )


if __name__ == "__main__":
    main()
