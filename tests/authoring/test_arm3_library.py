"""The frozen arm-3 library: verbatim files under a lock, a separate named library (D-063)."""

import shutil
from collections import Counter

import pytest

from lpstgp import libraries
from lpstgp.authoring import gates, registry
from lpstgp.authoring.generation import DOMAINS
from lpstgp.gp import pset
from lpstgp.operators.contract import OperatorSpec
from lpstgp.operators.registry import discover


def test_lock_covers_four_operators_per_domain():
    lock = registry.read_lock("arm3")
    assert len(lock) == 28
    assert Counter(e["domain"] for e in lock.values()) == dict.fromkeys(DOMAINS, 4)
    for name, entry in lock.items():
        assert entry["file"] == f"{entry['domain']}/{name}__v1.py"
        assert "claude-opus-5-5" in entry["provenance"]["implemented_by"]


def test_library_loads_verifies_and_builds_a_primitive_set():
    specs = registry.load_library("arm3")
    assert len(specs) == 28
    assert all(s.reference_test.startswith("none: LLM-authored") for s in specs)
    lib = libraries.resolve("arm3")
    assert "arm3" in libraries.NAMES
    built = pset.build(lib, "arm3")
    assert len(built.operators) == 28 + sum(
        isinstance(s, OperatorSpec) for s in discover().domain("core")
    )


def test_wp1_registry_never_sees_the_authored_operators():
    registry.load_library("arm3")
    wp1 = discover()
    assert wp1.operators
    assert not any(m.startswith("lpstgp.authoring") for m in wp1.modules.values())
    assert not any("LLM-authored" in s.reference_test for s in wp1.operators.values())


def test_a_changed_file_is_refused(tmp_path, monkeypatch):
    shutil.copytree(registry.GENERATED_DIR, tmp_path / "generated")
    shutil.copyfile(registry.lock_path("arm3"), tmp_path / "arm3.lock.toml")
    victim = next((tmp_path / "generated" / "arm3" / "spectral").glob("*.py"))
    victim.write_text(victim.read_text() + "\n# edited\n")
    monkeypatch.setattr(registry, "GENERATED_DIR", tmp_path / "generated")
    monkeypatch.setattr(registry, "AUTHORING_DIR", tmp_path)
    registry.load_library.cache_clear()
    try:
        with pytest.raises(registry.LockMismatchError, match="differs"):
            registry.load_library("arm3")
    finally:
        registry.load_library.cache_clear()


def test_freezing_twice_is_refused():
    with pytest.raises(RuntimeError, match="already frozen"):
        registry.freeze("arm3", [])


@pytest.mark.slow
@pytest.mark.parametrize("spec", registry.load_library("arm3"), ids=lambda s: s.name)
def test_frozen_operators_still_pass_the_synthetic_gates(spec):
    failures = [r for r in gates.synthetic_gates(spec) if not r["passed"]]
    assert not failures, failures
