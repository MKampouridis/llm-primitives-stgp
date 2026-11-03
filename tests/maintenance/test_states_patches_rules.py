"""Library states, patches (gates 1-2), arm 5's rules and the paired-seed gate."""

import json
import random
import shutil
from pathlib import Path

import pytest

from lpstgp.authoring import registry as authored
from lpstgp.gp.generate import Generator
from lpstgp.gp.variation import Limits, Rule
from lpstgp.maintenance import evidence, gate, patch, rules, state, stub
from lpstgp.types import Bool

LIMITS = Limits(17, 120, 504)


@pytest.fixture
def results(tmp_path):
    arm3 = state.arm3_state()
    state.save(arm3, {}, tmp_path)
    return tmp_path, arm3


def test_arm3_state_is_content_addressed_and_loads(results):
    root, arm3 = results
    assert state.arm3_state().id == arm3.id
    assert state.read(arm3.id, root).manifest() == arm3.manifest()
    specs = state.load_specs(arm3.id, str(root))
    assert {s.name for s in specs} == set(authored.read_lock("arm3"))
    assert all(s.version == 1 for s in specs)


def test_a_changed_state_file_is_refused(results):
    root, arm3 = results
    copy = root / "copy"
    shutil.copytree(root, copy)
    target = next((state.states_root(copy) / arm3.id / "files").glob("*.py"))
    target.write_text(target.read_text() + "\n# edited\n")
    with pytest.raises(authored.LockMismatchError):
        state.load_specs(arm3.id, str(copy))


def folder_with_library(tmp_path, arm3, root):
    folder = tmp_path / "session"
    folder.mkdir()
    stored = {e.key: state.states_root(root) / arm3.id / e.file for e in arm3.entries}
    initial = patch.initial_files(arm3, stored, folder)
    initial_sha = {f: patch.sha(folder / f) for f in initial}
    return folder, initial, initial_sha


def low_rows(arm3, usage=0.0):
    return {e.key: {"usage": usage, "contribution": None} for e in arm3.entries}


def grow(folder, name, domain='DOMAIN = "fractal"\n'):
    text = stub.GROWN.replace("$name", name)
    text = text.replace('DOMAIN = "statistical_physics"\n', domain)
    (folder / f"{name}.py").write_text(text)


def test_patch_reads_grows_refines_and_prunes(tmp_path, results):
    root, arm3 = results
    folder, initial, initial_sha = folder_with_library(tmp_path, arm3, root)
    grow(folder, "new_tstat")
    refined = folder / "dfa_exponent.py"
    refined.write_text(refined.read_text() + "\n# refined\n")
    (folder / "ising_coupling.py").write_text("   \n")
    (folder / "tsallis_q_index.py").unlink()
    rows = low_rows(arm3)
    p = patch.read_patch(
        folder, "4-full", arm3, initial, initial_sha, rows, rows, (), tmp_path / "w", gates=False
    )
    assert [r["operator"]["name"] for r in p.grows] == ["new_tstat"]
    assert p.grows[0]["domain"] == "fractal"
    assert [r["operator"]["name"] for r in p.refines] == ["dfa_exponent"]
    assert sorted(p.prunes) == ["ising_coupling", "tsallis_q_index"]
    assert p.admissible, p.problems
    new, sources = patch.apply(
        arm3,
        p,
        folder,
        "4-full/x/PL1/c1",
        {"implemented_by": "t", "specified_by": "t", "date": "2026-11-03"},
    )
    keys = {e.key for e in new.entries}
    assert "dfa_exponent@2" in keys
    assert "dfa_exponent@1" not in keys
    assert "new_tstat@1" in keys
    assert "ising_coupling@1" not in keys
    assert new.meta["retired"] == ["ising_coupling", "tsallis_q_index"]
    assert new.by_name()["dfa_exponent"].parent == "dfa_exponent@1"
    state.save(new, sources, root)
    specs = {s.key: s for s in state.load_specs(new.id, str(root))}
    assert specs["dfa_exponent@2"].gp_name == "DfaExponent_v2"


def test_bounds_prune_rule_domain_and_names(tmp_path, results):
    root, arm3 = results
    folder, initial, initial_sha = folder_with_library(tmp_path, arm3, root)
    for k in range(3):
        grow(folder, f"new_tstat_{k}")
    grow(folder, "no_domain", domain="")
    grow(folder, "dfa_exponent_again")
    (folder / "ising_coupling.py").write_text("")
    busy = low_rows(arm3, usage=0.5)
    p = patch.read_patch(
        folder, "4-grow", arm3, initial, initial_sha, busy, busy, ("dfa_exponent_again",),
        tmp_path / "w", gates=False,
    )  # fmt: skip
    text = " | ".join(p.problems)
    assert "5 grow(s)" in text
    assert "prune is not allowed" in text
    assert "no_domain.py: set DOMAIN" in text
    assert "is or was in the library" in text
    p = patch.read_patch(
        folder, "4-full", arm3, initial, initial_sha, busy, None, (), tmp_path / "w2", gates=False
    )
    assert any("prune of ising_coupling" in x for x in p.problems)


def test_refine_must_keep_the_operator_name(tmp_path, results):
    root, arm3 = results
    folder, initial, initial_sha = folder_with_library(tmp_path, arm3, root)
    grow(folder, "dfa_exponent")  # overwrite dfa_exponent.py with another operator
    (folder / "dfa_exponent.py").write_text(
        (folder / "dfa_exponent.py").read_text().replace('name="dfa_exponent"', 'name="other"')
    )
    p = patch.read_patch(
        folder, "4-full", arm3, initial, initial_sha, {}, None, (), tmp_path / "w", gates=False
    )
    assert any("not dfa_exponent" in x for x in p.problems)


def test_gate_one_runs_the_admission_checks(tmp_path, results):
    root, arm3 = results
    folder, initial, initial_sha = folder_with_library(tmp_path, arm3, root)
    grow(folder, "new_tstat")
    p = patch.read_patch(
        folder, "4-grow", arm3, initial, initial_sha, {}, None, (), tmp_path / "w", gates=True
    )
    assert p.admissible, p.problems
    assert p.grows[0]["gates_passed"]
    assert p.grows[0]["cross_process_deterministic"]
    bad = (folder / "new_tstat.py").read_text().replace("lambda window: window", "lambda window: 1")
    (folder / "new_tstat.py").write_text(bad)
    p = patch.read_patch(
        folder, "4-grow", arm3, initial, initial_sha, {}, None, (), tmp_path / "w2", gates=True
    )
    assert any("fails check" in x for x in p.problems)


def test_rules_are_parsed_typed_and_never_evaluated(tmp_path, arm3_lib):
    gen = Generator(arm3_lib, 504, random.Random(5))
    good = [Rule(gen.ramped(Bool, 2, 4), gen.ramped(Bool, 2, 4)) for _ in range(30)]
    items = [{"entry": str(r.entry), "exit": str(r.exit)} for r in good[:2]]
    items += [
        {"entry": "__import__", "exit": str(good[0].exit)},
        {"entry": "CrossAbove_v1(Ret_v1, LongWindow_60)", "exit": str(good[0].exit)},
        {"entry": str(good[0].entry), "exit": str(good[0].exit)},  # duplicate
        {"entry": str(good[0].entry)},
    ]
    items += [{"entry": str(r.entry), "exit": str(r.exit)} for r in good[2:]]
    path = tmp_path / rules.RULES_FILE
    path.write_text(json.dumps(items))
    admitted, problems = rules.check_rules(path, arm3_lib, LIMITS)
    assert len(admitted) == rules.MAX_RULES
    assert admitted[0] == (str(good[0].entry), str(good[0].exit))
    text = " | ".join(problems)
    assert "unknown nodes ['__import__']" in text
    assert "duplicate" in text
    assert "needs exactly the keys" in text
    assert "beyond the first" in text


def _rec(inst, seed, v):
    return {
        "instruments": [inst],
        "period": {"id": "PL1"},
        "seed": seed,
        "selected": 0,
        "hall_of_fame": [{"validation": {"fitness": v}}],
    }


def test_paired_gate():
    cur = [_rec("A", 1, 1.0), _rec("B", 2, 1.0), _rec("C", 3, 1.0)]
    worse = [_rec("A", 1, 0.9), _rec("B", 2, 0.9), _rec("C", 3, 1.2)]
    out = gate.paired_check(cur, worse)
    assert out["median_difference"] == pytest.approx(-0.1)
    assert not out["admitted"]
    same = gate.paired_check(cur, cur)
    assert same["admitted"]
    assert same["share_equal"] == 1
    with pytest.raises(ValueError, match="paired"):
        gate.paired_check(cur, cur[:2])


def test_prune_rule_needs_two_low_cycles():
    lo = {"k@1": {"usage": 0.0, "contribution": None}}
    hi = {"k@1": {"usage": 0.3, "contribution": 0.5}}
    assert evidence.prunable("k@1", lo, lo)
    assert not evidence.prunable("k@1", lo, None)
    assert not evidence.prunable("k@1", lo, hi)
    assert not evidence.prunable("k@1", hi, lo)


def test_stub_grown_operator_is_valid_python():
    compile(stub.GROWN.replace("$name", "x"), "x.py", "exec")
    assert Path(stub.__file__).exists()
