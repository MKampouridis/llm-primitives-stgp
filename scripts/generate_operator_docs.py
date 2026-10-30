"""Write docs/operators.md from the contracts, and docs/arm6_review.md if it does not exist yet.

Usage: uv run python scripts/generate_operator_docs.py
"""

from __future__ import annotations

from lpstgp.config import REPO_ROOT
from lpstgp.operators.catalogue import render_catalogue, render_review_checklist
from lpstgp.operators.registry import discover


def main() -> None:
    reg = discover()
    docs = REPO_ROOT / "docs"
    (docs / "operators.md").write_text(render_catalogue(reg) + "\n", encoding="utf-8")
    print(f"wrote {docs / 'operators.md'}")
    review = docs / "arm6_review.md"
    if not review.exists():  # hand-edited afterwards: never overwrite reviews
        review.write_text(render_review_checklist(reg) + "\n", encoding="utf-8")
        print(f"wrote {review}")


if __name__ == "__main__":
    main()
