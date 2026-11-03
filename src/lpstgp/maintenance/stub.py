"""A scripted stand-in for the LLM session: tests the maintenance mechanics without any model.

Same signature as :func:`lpstgp.maintenance.session.run`. Per arm, it makes a fixed, valid change
so that every path of the cycle is exercised: arm 4-grow grows one operator; arm 4-full grows one
and refines one (a comment-only edit, so a new version with the same behaviour); arm 5 proposes
the brief's best elite rule pair. Used by ``scripts/maintain.py --stub`` and the tests; its runs
are never reported.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lpstgp.maintenance import session
from lpstgp.maintenance.rules import RULES_FILE

GROWN = '''"""Stub operator: rolling t-statistic of the mean."""

import numpy as np
from operator_api import Operator, Real, Series, Window, trailing_windows

DOMAIN = "statistical_physics"


def tstat(x, window):
    rows = trailing_windows(x, window)
    mean = rows.mean(axis=1)
    sd = rows.std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = mean / sd * np.sqrt(window)
    out[~np.isfinite(out)] = np.nan
    return out


OPERATOR = Operator(
    name="$name",
    summary="t-statistic of the mean of the last `window` values.",
    inputs=(Series,),
    params=(("window", Window),),
    output=Real,
    lookback=lambda window: window,
    missing="propagate",
    definition=r"t = \\bar x / s \\sqrt{w}",
    references=("Student (1908), Biometrika 6(1):1-25",),
    impl=tstat,
    invariances=("scale",),
)
'''
ELITE = re.compile(r"entry: `([^`]+)`\n\s+exit: `([^`]+)`")


def run(
    arm: str,
    archive: Path,
    brief: str,
    setup: Callable[[Path], None],
    finish: Callable[[Path], dict[str, Any]],
    repair_prompt: Callable[[dict[str, Any]], str | None],
    claude_version: str = "",
    timeout: float = 0,
    root: Path | None = None,
) -> dict[str, Any]:
    archive.mkdir(parents=True, exist_ok=True)
    folder = archive / "stub_folder"
    if not folder.exists():
        session.prepare(folder, brief)
        setup(folder)
        (archive / "BRIEF.md").write_text(brief, encoding="utf-8")
        tag = archive.parent.name + archive.parent.parent.name.lower()  # c<k><period>
        if arm in ("4-grow", "4-full"):
            name = f"stub_tstat_{tag}"
            (folder / f"{name}.py").write_text(GROWN.replace("$name", name), encoding="utf-8")
        if arm == "4-full":
            first = sorted(p for p in folder.glob("*.py") if p.name.startswith(("a", "b", "c")))
            first = next(p for p in first if p.name != "operator_api.py")
            first.write_text(first.read_text() + f"\n# stub refinement {tag}\n", encoding="utf-8")
        if arm == "5":
            pairs = ELITE.findall(brief)[:2]
            items = [{"entry": e, "exit": x} for e, x in pairs]
            (folder / RULES_FILE).write_text(json.dumps(items, indent=1), encoding="utf-8")
    result = finish(folder)
    return {
        "arm": arm,
        "session_id": f"stub-{archive.parent.parent.name}-{archive.parent.name}",
        "folder": str(folder),
        "brief_sha12": "stub",
        "completed": True,
        "models": [session.MODEL],
        "model_ok": True,
        "repaired": False,
        "runs": [],
        "result": result,
        "code_version": "stub",
        "finished_utc": "2026-01-01T00:00:00+00:00",
    }
