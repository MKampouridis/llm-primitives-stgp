"""Freezing accepted sessions: verbatim copy, lock with provenance, catalogue and report."""

import json
from pathlib import Path

import pytest

from lpstgp.strategies import freeze, registry

TOY = Path(__file__).parent / "fixtures" / "toy_reversal.py"


def _session(root: Path, slot: str, accepted: bool) -> None:
    archive = root / slot
    archive.mkdir(parents=True)
    (archive / "final_strategy.py").write_bytes(TOY.read_bytes())
    log = [{"tool": "check"}, {"tool": "backtest"}, {"tool": "backtest"}]
    (archive / "evaluations.jsonl").write_text("\n".join(json.dumps(e) for e in log) + "\n")
    meta = {
        "name": "toy_reversal",
        "hypothesis": "h",
        "definition": "d",
        "references": ["r"],
        "novelty": "n",
        "limitations": "l",
        "rule_lookback": 0,
        "lookback": 120,
        "signals": [
            {
                "name": "range_position",
                "inputs": ["log_price"],
                "lookback": 120,
                "params": {"window": {"kind": "LongWindow", "default": 120}},
            }
        ],
    }
    summary = {
        "slot": slot,
        "sid": slot[:3],
        "domain": "spectral",
        "session_id": "abc",
        "model": "claude-opus-5-5",
        "effort": "high",
        "claude_version": "2.1.316 (Claude Code)",
        "brief_sha12": "0123456789ab",
        "finished_utc": "2026-11-01T10:00:00+00:00",
        "accepted": accepted,
        "sha256": registry.file_hash(archive / "final_strategy.py"),
        "strategy": meta,
        "dev_fit": {"objective": 0.12},
        "dev_holdout": {"objective": 0.05},
        "runs": [
            {
                "models": ["claude-opus-5-5"],
                "num_turns": 40,
                "duration_ms": 1.2e6,
                "total_cost_usd": 3.1,
                "usage": {"output_tokens": 1000, "cache_read_input_tokens": 9},
            }
        ],
    }
    if not accepted:
        summary["reason"] = "gates"
    (archive / "summary.json").write_text(json.dumps(summary))


def test_freeze_copies_verbatim_locks_and_renders(tmp_path):
    root = tmp_path / "archives"
    _session(root, "s25_spectral_1", True)
    _session(root, "s26_spectral_2", False)
    sessions = freeze.summaries(root)
    assert [s["backtests_used"] for s in sessions] == [2, 2]
    accepted = [s for s in sessions if s["accepted"]]
    generated, lock = tmp_path / "generated", tmp_path / "lock.toml"
    entries = freeze.freeze(accepted, generated, lock)
    copied = generated / "spectral" / "s25__v1.py"
    assert copied.read_bytes() == TOY.read_bytes()
    assert entries["s25"]["provenance"]["implemented_by"].startswith(
        "claude-opus-5-5 via Claude Code"
    )
    (frozen,) = registry.load_frozen(generated, lock)
    assert frozen.provenance.date == "2026-11-01"
    assert "toy_reversal" in freeze.catalogue(accepted)
    text = freeze.report(sessions)
    assert "Sessions: 2; accepted: 1" in text
    assert "no: gates" in text


def test_freeze_refuses_a_file_that_changed_after_acceptance(tmp_path):
    root = tmp_path / "archives"
    _session(root, "s25_spectral_1", True)
    (root / "s25_spectral_1" / "final_strategy.py").write_text("# changed\n")
    with pytest.raises(RuntimeError, match="differs"):
        freeze.freeze(freeze.summaries(root), tmp_path / "g", tmp_path / "l.toml")
