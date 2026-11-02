"""Gates for authored operators, run in the sandboxed worker: each fault is caught by its gate."""

import shutil
from pathlib import Path

import pytest

from lpstgp.authoring import generation, mcp_tools
from lpstgp.strategies import execute

FIX = Path(__file__).parent / "fixtures"
W = mcp_tools.WORKER


def gates(name, tmp_path):
    return execute.run("gates", FIX / f"{name}.py", tmp_path / name, worker=W)


def failing(report):
    return [r["check"] for r in report["results"] if not r["passed"]]


def test_valid_operators_pass(tmp_path):
    for name in ("toy_operator", "new_kind"):
        report = gates(name, tmp_path)
        assert report["ok"], report
        assert report["passed"], failing(report)


@pytest.mark.parametrize(
    ("name", "gate"),
    [
        ("bad_lookahead", "prefix-invariant"),
        ("bad_lookback", "exact lookback"),
        ("bad_scale", "declared invariances"),
    ],
)
def test_each_fault_is_caught_by_its_gate(tmp_path, name, gate):
    report = gates(name, tmp_path)
    assert report["ok"]
    assert not report["passed"]
    assert any(check.startswith(gate) for check in failing(report))


def test_source_policy_stops_the_module_before_it_runs(tmp_path):
    report = gates("bad_import", tmp_path)
    assert not report["ok"]
    assert report["stage"] == "load"
    assert "import os" in report["error"]


def test_output_hash_is_identical_across_thread_counts(tmp_path):
    hashes = {
        execute.run("hash", FIX / "toy_operator.py", tmp_path / f"h{t}", worker=W, threads=t)[
            "hash"
        ]
        for t in (1, 4)
    }
    assert len(hashes) == 1


def test_meta_reports_signature_and_declared_kind(tmp_path):
    meta = execute.run("meta", FIX / "new_kind.py", tmp_path / "m", worker=W)["operator"]
    assert meta["signature"] == "toy_concentration(Hist, power: Power) -> Real"
    assert meta["params"]["power"] == {"kind": "LlmPower", "grid": [0.5, 2.0]}


def _folder(tmp_path, names):
    folder = tmp_path / "session"
    folder.mkdir()
    shutil.copyfile(generation.operator_api.__file__, folder / mcp_tools.API_FILE)
    for i, name in enumerate(names):
        text = (FIX / f"{name}.py").read_text()
        if name == "toy_operator":
            text = text.replace("toy_tstat", f"toy_tstat_{i}")
        (folder / f"op{i}.py").write_text(text)
    return folder


def test_finalize_accepts_four_passing_operators(tmp_path):
    folder = _folder(tmp_path, ["toy_operator", "toy_operator", "toy_operator", "new_kind"])
    result = generation.finalize(folder, tmp_path / "archive", None, set(), {})
    assert result["accepted"], result["problems"]
    assert result["kinds"] == {"Power": [0.5, 2.0]}
    assert len(result["operators"]) == 4


def test_finalize_rejects_wrong_count_taken_names_and_kind_conflicts(tmp_path):
    folder = _folder(tmp_path, ["toy_operator", "new_kind", "bad_lookahead"])
    result = generation.finalize(
        folder, tmp_path / "archive", None, {"toy_concentration"}, {"Power": (1.0, 3.0)}
    )
    problems = " | ".join(result["problems"])
    assert not result["accepted"]
    assert "exactly 4" in problems
    assert "already in use" in problems
    assert "another grid" in problems
    assert "fails check" in problems
