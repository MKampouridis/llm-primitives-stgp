"""Refuse data files, large files and secret-like strings in the repository.

Stdlib only, so the git pre-commit hook can run it with any Python 3.
Usage: ``python scripts/check_hygiene.py`` (all tracked files) or ``--staged``.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

MAX_BYTES = 512 * 1024
SIZE_ALLOWLIST = {"uv.lock"}

FORBIDDEN_SUFFIXES = {
    ".parquet", ".feather", ".arrow", ".csv", ".h5", ".hdf5", ".pkl", ".pickle",
    ".npy", ".npz", ".zip", ".gz", ".pem", ".key", ".p12", ".pfx", ".token",
}  # fmt: skip
FORBIDDEN_NAME_PATTERNS = [
    re.compile(r"^\.env(\..+)?$"),
    re.compile(r"^id_(rsa|ed25519|ecdsa|dsa)"),
    re.compile(r"^credentials"),
    re.compile(r"^\.pgpass$"),
    re.compile(r"^paths\.toml$"),
]
NAME_ALLOWLIST = {".env.example"}

# Patterns are assembled from fragments so this file does not match itself.
SECRET_PATTERNS = [
    ("Anthropic API key", re.compile("sk-" + "ant-" + r"[A-Za-z0-9_\-]{20,}")),
    ("OpenAI-style key", re.compile("sk-" + r"(proj-)?[A-Za-z0-9]{32,}")),
    ("AWS access key", re.compile("AK" + r"IA[0-9A-Z]{16}")),
    ("GitHub token", re.compile("gh" + r"[pousr]_[A-Za-z0-9]{36,}")),
    ("GitHub fine-grained token", re.compile("github" + r"_pat_[A-Za-z0-9_]{40,}")),
    ("Slack token", re.compile("xo" + r"x[abprs]-[A-Za-z0-9\-]{10,}")),
    ("Google API key", re.compile("AI" + r"za[0-9A-Za-z_\-]{35}")),
    ("Private key block", re.compile("-----BEGIN " + r"([A-Z]+ )?PRIVATE KEY-----")),
]


def tracked_files(staged: bool) -> list[str]:
    cmd = (
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
        if staged
        else ["git", "ls-files"]
    )
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def check(paths: list[str], root: Path) -> list[str]:
    problems: list[str] = []
    for rel in paths:
        path = root / rel
        name = path.name
        if name not in NAME_ALLOWLIST:
            if path.suffix.lower() in FORBIDDEN_SUFFIXES:
                problems.append(
                    f"{rel}: data or key file type '{path.suffix}' must not be committed"
                )
            if any(p.search(name) for p in FORBIDDEN_NAME_PATTERNS):
                problems.append(f"{rel}: secret or machine-specific file must not be committed")
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size > MAX_BYTES and name not in SIZE_ALLOWLIST:
            problems.append(f"{rel}: {size / 1024:.0f} KB exceeds the {MAX_BYTES // 1024} KB limit")
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                problems.append(f"{rel}: contains something that looks like a {label}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="check staged files only")
    args = parser.parse_args()
    root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    problems = check(tracked_files(args.staged), root)
    for problem in problems:
        print(f"hygiene: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
