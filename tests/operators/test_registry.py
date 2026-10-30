"""Registry discovery, contract completeness and the immutable version lock."""

import pytest

from lpstgp.operators import registry
from lpstgp.operators.contract import CROSS_DOMAINS, DOMAINS, Missing

REG = registry.discover()


def test_contracts_are_complete():
    for spec in REG.all().values():
        assert spec.domain in DOMAINS
        assert spec.summary
        assert spec.definition
        assert spec.references
        assert spec.reference_test
        assert spec.provenance.implemented_by
        if hasattr(spec, "params"):
            for p in spec.params:
                assert p.grid, f"{spec.key}: empty grid for {p.name}"
                params = {q.name: max(q.grid) for q in spec.params}
                assert spec.lookback_for(params) <= 504, f"{spec.key}: lookback exceeds L_max"
            if spec.missing is Missing.MIN_VALID:
                assert 0 < spec.min_valid <= 1


def test_gp_names_are_unique():
    names = [s.gp_name for s in REG.all().values()]
    assert len(names) == len(set(names))


def test_libraries_resolve():
    for name in registry.LIBRARIES:
        assert REG.library(name)


def test_cross_domain_quota():
    """About four operators per mathematical domain (fixed quota per the plan)."""
    counts = {d: len(REG.domain(d)) for d in CROSS_DOMAINS}
    present = {d: c for d, c in counts.items() if c}
    assert all(c == 4 for c in present.values()), counts


def test_version_lock():
    if not registry.LOCK_FILE.is_file():
        pytest.skip("library not frozen yet (no registry.lock.toml)")
    changed, unlocked = registry.lock_status()
    assert changed == [], f"locked contracts modified (add a new version instead): {changed}"
    assert unlocked == [], f"contracts not in the lock (run scripts/update_lock.py): {unlocked}"


def test_operator_catalogue_is_up_to_date():
    from lpstgp.config import REPO_ROOT
    from lpstgp.operators.catalogue import render_catalogue

    path = REPO_ROOT / "docs" / "operators.md"
    assert path.read_text(encoding="utf-8") == render_catalogue(REG) + "\n", (
        "run: uv run python scripts/generate_operator_docs.py"
    )


def test_fingerprint_detects_contract_changes():
    import dataclasses

    from lpstgp.operators.contract import ParamSpec
    from lpstgp.types import Window

    spec = REG.operators["permutation_entropy@1"]
    other_grid = dataclasses.replace(spec, params=(ParamSpec("window", Window), spec.params[1]))
    other_policy = dataclasses.replace(spec, min_valid=0.5)
    base = registry.fingerprint(spec)
    assert registry.fingerprint(other_grid) != base
    assert registry.fingerprint(other_policy) != base


def test_lock_covers_helper_modules_but_not_metadata():
    files = {p.name for p in registry.dependency_files(REG.modules["levy_area@1"])}
    assert "_paths.py" in files  # shared numerical helpers are part of the version
    assert "contract.py" not in files
    assert "types.py" not in files
