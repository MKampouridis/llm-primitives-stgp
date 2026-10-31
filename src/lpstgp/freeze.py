"""Freeze manifests: the committed record of what is frozen before any test-year read.

A pilot test year (WP2) or a primary test year (WP4) may be read only after a manifest listing
every rule to be evaluated, plus digests of the settings and of the strategy and operator locks,
has been written *and committed to git*. ``FreezeManifest.load_committed`` refuses a manifest that
is untracked or differs from ``HEAD``, so the commit history proves the order of events.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lpstgp.config import REPO_ROOT

SCHEMA = "lpstgp.freeze/1"


class FreezeError(PermissionError):
    """No valid, committed freeze manifest."""


def digest(payload: Any) -> str:
    """sha256 of canonical JSON (sorted keys, no whitespace)."""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def write_manifest(path: Path, rules: Mapping[str, str], context: Mapping[str, Any]) -> dict:
    """Write a manifest: ``rules`` maps a task id to the hash of its frozen rule."""
    manifest = {
        "schema": SCHEMA,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "context": dict(context),
        "rules": dict(sorted(rules.items())),
    }
    manifest["rules_digest"] = digest(manifest["rules"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


@dataclass(frozen=True)
class FreezeManifest:
    path: Path
    commit: str
    rules: Mapping[str, str]
    context: Mapping[str, Any]

    @classmethod
    def load_committed(cls, path: Path, repo: Path = REPO_ROOT) -> FreezeManifest:
        path = Path(path).resolve()
        rel = path.relative_to(Path(repo).resolve()).as_posix()
        if _git(repo, "ls-files", "--error-unmatch", rel).returncode != 0:
            raise FreezeError(f"{rel} is not tracked by git; commit it before any test read")
        if _git(repo, "diff", "--quiet", "HEAD", "--", rel).returncode != 0:
            raise FreezeError(f"{rel} differs from HEAD; commit it before any test read")
        commit = _git(repo, "log", "-n", "1", "--format=%H", "--", rel).stdout.strip()
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("schema") != SCHEMA or digest(manifest["rules"]) != manifest.get(
            "rules_digest"
        ):
            raise FreezeError(f"{rel} is not a valid freeze manifest")
        return cls(path, commit, manifest["rules"], manifest["context"])

    def require(self, task_id: str, rule_hash: str) -> None:
        """Refuse to evaluate a rule that the manifest did not freeze."""
        if self.rules.get(task_id) != rule_hash:
            raise FreezeError(f"{task_id}: rule {rule_hash[:12]} is not in the freeze manifest")
