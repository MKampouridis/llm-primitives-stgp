"""The maintenance loop of protocol_wp3 §4 for one arm over walk-forward periods, resumable.

    L(p, 0) = L(p-1, C)       (L(first, 0) = arm 3's library)
    for c in 1..C:
        runs of L(p, c-1) on FIT (3 per instrument, paired seeds)  -> records
        evidence from those records (FIT only)                     -> table
        one LLM session                                            -> patch / rules
        gates 1-2, then the candidate's runs and gate 3            -> admitted or not

A batch of runs is identified by (period, library state, seeded rules), not by the arm, so arms
whose libraries coincide (every arm's first batch) share it, and the candidate's runs become the
next cycle's runs when admitted. Seeds come from (instrument, period, run) only (D-066). Every
step writes its result before the next starts; a re-run skips what is done.

Layout under ``<results>/wp3/maintenance/<campaign>/``: ``runs/`` (records, via the runner),
``<arm>/<period>/c<k>/`` (session archive, ``context.json``, ``cycle.json``), and
``<arm>/<period>/lineage.json``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from lpstgp.campaign.execute import is_complete
from lpstgp.campaign.plan import (
    data_digest,
    run_seed,
    settings_digest,
    source_digest,
    tier_digest,
)
from lpstgp.config import load_paths, load_settings
from lpstgp.data.tier_a import load_universe
from lpstgp.freeze import digest
from lpstgp.gp.pset import build
from lpstgp.maintenance import evidence, gate, patch, rules, session, state
from lpstgp.runner import RunTask, configs_from_settings, record_path, run_many, write_atomic
from lpstgp.splits import Stage, all_periods

# The WP2 go/no-go's instruments and calibrated GP parameters (protocol.md §6; D-047, D-056).
PILOT_INSTRUMENTS = (
    "SPX", "NDX", "SMI", "DAX", "CAC", "UKX", "NKY", "HSI", "KOSPI", "AS51",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP",
    "NATGAS", "GOLD", "SILVER", "COPPER",
)  # fmt: skip
GP_PARAMETERS = {"population": 250, "generations": 70, "tournament": 5}
RUNS_PER_INSTRUMENT = 3
CYCLES = 3  # per period (D-064; fixed at protocol 1.0, D-073)
ARMS = ("4-grow", "4-full", "5")
SPEC_SCHEMA = "wp3-maintenance-campaign/1"
REJECTED_BY_GATE = "the changed library's results on held-out data were clearly worse"


class CampaignMismatchError(RuntimeError):
    """A campaign's stored results were made under another specification."""


@dataclass(frozen=True)
class ArmState:
    state_id: str
    seed_rules: tuple[tuple[str, str], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"state_id": self.state_id, "seed_rules": [list(r) for r in self.seed_rules]}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> ArmState:
        return cls(d["state_id"], tuple(tuple(r) for r in d.get("seed_rules", ())))

    @property
    def batch_key(self) -> str:
        if not self.seed_rules:
            return self.state_id
        text = json.dumps([list(r) for r in self.seed_rules])
        return f"{self.state_id}-{hashlib.sha256(text.encode()).hexdigest()[:12]}"


class Cycle:
    """The maintenance loop of one campaign (e.g. the WP3 dry run)."""

    def __init__(
        self,
        campaign: str,
        periods: Sequence[str],
        instruments: Sequence[str] | Mapping[str, Sequence[str]] = PILOT_INSTRUMENTS,
        runs: int = RUNS_PER_INSTRUMENT,
        cycles: int = CYCLES,
        workers: int = 6,
        gp_overrides: Mapping[str, Any] | None = None,
        claude_version: str = "",
        session_runner=None,  # tests: a stand-in for session.run (same signature)
        check: bool = True,  # False: only compute the specification (WP4's check; D-088)
    ) -> None:
        self.paths, self.settings = load_paths(), load_settings()
        self.campaign = campaign
        self.periods = tuple(periods)
        # One list for every period, or each period's own (WP4: its eligible instruments, D-083).
        if isinstance(instruments, Mapping):
            self.by_period = {p: tuple(instruments[p]) for p in self.periods}
        else:
            self.by_period = {p: tuple(instruments) for p in self.periods}
        self.instruments = tuple(sorted({i for v in self.by_period.values() for i in v}))
        self.runs = runs
        self.cycles = cycles
        self.workers = workers
        self.gp_cfg, self.fit_cfg = configs_from_settings(
            self.settings, **{**GP_PARAMETERS, **(gp_overrides or {})}
        )
        self.root = self.paths.results_dir / "wp3" / "maintenance" / campaign
        universe = {i.id: i.asset_class for i in load_universe()}
        self.asset_class = {i: universe[i] for i in self.instruments}
        self.claude_version = claude_version
        self.session_runner = session_runner or session.run
        self._check_periods(self.periods)
        self.spec = self.specification()
        self.spec_digest = digest(self.spec)
        if check:
            self._check_specification()

    # --- what a campaign's results depend on (D-074) ----------------------------------------

    def _check_periods(self, periods: Sequence[str]) -> None:
        """Each period inherits the previous one's library, so the order is part of the design:
        distinct periods, in chronological order (D-081)."""
        if len(set(periods)) != len(periods):
            raise ValueError(f"a period appears twice in {list(periods)}")
        settings = getattr(self, "settings", None) or load_settings()
        starts = [all_periods(settings)[p].fit_start for p in periods]
        if starts != sorted(starts):
            raise ValueError(f"periods must be in chronological order, not {list(periods)}")

    def specification(self) -> dict[str, Any]:
        """Everything a cycle's results depend on: settings, GP and fitness configuration,
        instruments, runs, cycles, period definitions, the data files and the package source."""
        periods = all_periods(self.settings)
        return {
            "schema": SPEC_SCHEMA,
            "campaign": self.campaign,
            "periods": [asdict(periods[p]) for p in self.periods],  # in order (D-081)
            "instruments": {p: list(v) for p, v in self.by_period.items()},
            "runs": self.runs,
            "cycles": self.cycles,
            "gp": asdict(self.gp_cfg),
            "fitness": asdict(self.fit_cfg),
            "settings_digest": settings_digest(self.settings),
            "data_digest": digest(data_digest(self.paths, self.instruments)),
            "tier_digest": tier_digest(self.paths),  # the describe tool's cohort too (D-081)
            "source_digest": source_digest(),
        }

    def _check_specification(self) -> None:
        """A campaign resumes only under the specification it started with; it is written on
        the first run and never silently replaced."""
        path = self.root / "campaign.json"
        spec = json.loads(json.dumps(self.spec, default=str))
        if path.exists():
            old = json.loads(path.read_text())
            changed = sorted(k for k in {*old, *spec} if old.get(k) != spec.get(k))
            if changed:
                raise CampaignMismatchError(
                    f"campaign {self.campaign} was started under another specification "
                    f"(changed: {', '.join(changed)}); start a new campaign"
                )
            return
        write_atomic(path, json.dumps(spec, indent=1, sort_keys=True) + "\n")

    # --- runs ------------------------------------------------------------------------------

    def tasks(self, period: str, arm_state: ArmState) -> list[RunTask]:
        library = state.PREFIX + arm_state.state_id
        out = []
        for inst in self.by_period[period]:
            for run in range(1, self.runs + 1):
                task_id = f"{arm_state.batch_key}/{period}/{inst}/r{run:02d}"
                out.append(
                    RunTask(
                        f"wp3-maintenance-{self.campaign}", library, (inst,), period,
                        run_seed((inst,), period, run), self.gp_cfg, self.fit_cfg,
                        campaign=(
                            ("task_id", task_id), ("run", str(run)),
                            ("spec_digest", self.spec_digest),
                        ),
                        knockouts=True, seed_rules=arm_state.seed_rules,
                    )
                )  # fmt: skip
        return out

    def batch(self, period: str, arm_state: ArmState) -> list[dict[str, Any]]:
        """The run records of a library state on a period (runs what is missing)."""
        tasks = self.tasks(period, arm_state)
        # A record counts only if it is complete and was made under this campaign's specification
        # (its campaign metadata carry the specification's digest); anything else is re-run.
        todo = [t for t in tasks if not is_complete(record_path(self.paths.results_dir, t), t)]
        if todo:
            run_many(todo, self.workers, self.paths.results_dir)
        return [json.loads(record_path(self.paths.results_dir, t).read_text()) for t in tasks]

    # --- one cycle -------------------------------------------------------------------------

    def _dir(self, arm: str, period: str, c: int) -> Path:
        return self.root / arm / period / f"c{c}"

    def start_state(self, arm: str, period: str) -> tuple[ArmState, dict | None]:
        """L(p, 0): arm 3's library for the first period, else the previous period's result.
        Returns it with the cycle record that produced it (None for arm 3's library)."""
        k = self.periods.index(period)
        if k == 0:
            first = state.arm3_state()
            state.save(first, {}, self.paths.results_dir)
            return ArmState(first.id), None
        last = self.cycle_record(arm, self.periods[k - 1], self.cycles)
        return ArmState.from_dict(last["state_out"]), last

    def cycle_record(self, arm: str, period: str, c: int) -> dict[str, Any]:
        path = self._dir(arm, period, c) / "cycle.json"
        if not path.exists():
            raise FileNotFoundError(f"{arm} {period} cycle {c} has not run")
        return self._checked(json.loads(path.read_text()), path)

    def _checked(self, record: dict[str, Any], path: Path) -> dict[str, Any]:
        if record.get("spec_digest") != self.spec_digest:
            raise CampaignMismatchError(f"{path} was made under another campaign specification")
        return record

    def run_cycle(self, arm: str, period: str, c: int) -> dict[str, Any]:
        out_dir = self._dir(arm, period, c)
        done = out_dir / "cycle.json"
        if done.exists():
            return self._checked(json.loads(done.read_text()), done)
        if c == 1:
            current, before = self.start_state(arm, period)
        else:
            before = self.cycle_record(arm, period, c - 1)
            current = ArmState.from_dict(before["state_out"])
        lib_state = state.read(current.state_id, self.paths.results_dir)
        specs = state.load_specs(current.state_id, str(self.paths.results_dir))
        names = evidence.gp_names(specs)
        records = self.batch(period, current)
        rows = evidence.operator_rows(records, names)
        history = self._history(arm, period, c)
        classes = {i: self.asset_class[i] for i in self.by_period[period]}
        elite = evidence.elite_rules(records, classes)
        summary = evidence.summary(records)
        lib = build(state.library(state.PREFIX + current.state_id))
        previous_rows = before.get("evidence") if before else None
        brief = session.render(
            arm, lib, rows, history, summary, elite, before and before.get("decision"),
            classes, self.runs, self.gp_cfg, previous_rows,
        )  # fmt: skip
        sess_dir = out_dir / "session"
        stored = {e.key: state.states_root(self.paths.results_dir) / lib_state.id / e.file
                  for e in lib_state.entries}  # fmt: skip
        initial = {f"{e.name}.py": e.name for e in lib_state.entries}
        used_names = self.used_names(arm, period, c)
        initial_sha = {f"{e.name}.py": e.sha256 for e in lib_state.entries}
        context = {
            "arm": arm,
            "state_id": current.state_id,
            "library": state.PREFIX + current.state_id,
            "results_dir": str(self.paths.results_dir),
            "initial": initial,
            "initial_sha": initial_sha,
            "evidence": rows,
            "previous_evidence": previous_rows,
            "used_names": used_names,
        }
        sess_dir.mkdir(parents=True, exist_ok=True)
        (sess_dir / "context.json").write_text(json.dumps(context, indent=1, default=float))
        dev = None
        if arm != "5":
            from lpstgp.strategies import devtool

            dev = devtool.build(self.paths, self.settings, Stage.FIT, sess_dir / "inputs")

        def setup(folder: Path) -> None:
            if arm != "5":
                patch.initial_files(lib_state, stored, folder)

        def finish(folder: Path) -> dict[str, Any]:
            if arm == "5":
                admitted, problems = rules.check_rules(
                    folder / rules.RULES_FILE, lib, self.gp_cfg.limits
                )
                return {"rules": admitted, "problems": problems}
            p = patch.read_patch(
                folder, arm, lib_state, initial, initial_sha, rows, previous_rows,
                used_names, sess_dir / "jobs", dev,
            )  # fmt: skip
            return p.as_dict()

        def repair(result: dict[str, Any]) -> str | None:
            if not result["problems"]:
                return None
            what = "rules.json" if arm == "5" else "your changes"
            return (
                f"The host's final check of {what} found problems. Fix them (you may use your "
                "tools within their remaining calls), or undo the changes concerned. Problems:\n"
                + json.dumps(result["problems"], default=str)[:4000]
            )

        record = self.session_runner(
            arm, sess_dir, brief, setup, finish, repair, self.claude_version
        )
        decision, candidate, gate_result = self._decide(arm, period, c, current, lib_state, record)
        if candidate is not None and decision["status"] == "pending":
            cand_records = self.batch(period, candidate)
            gate_result = gate.paired_check(records, cand_records)
            if gate_result["admitted"]:
                decision["status"] = "admitted"
            else:
                decision.update({"status": "rejected", "reason": REJECTED_BY_GATE})
        out = current if decision["status"] != "admitted" else candidate
        cycle = {
            "campaign": self.campaign,
            "spec_digest": self.spec_digest,
            "arm": arm,
            "period": period,
            "cycle": c,
            "state_in": current.as_dict(),
            "state_out": out.as_dict(),
            "batch_in": current.batch_key,
            "candidate": candidate.as_dict() if candidate else None,
            "decision": decision,
            "gate": gate_result,
            "evidence": rows,
            "summary": summary,
            "session": {
                k: record.get(k)
                for k in (
                    "session_id",
                    "brief_sha12",
                    "model_ok",
                    "models",
                    "completed",
                    "repaired",
                )
            },
            "session_result": record.get("result"),
            "usage": [r.get("usage") for r in record.get("runs", [])],
            "code_version": record.get("code_version"),
        }
        write_atomic(done, json.dumps(cycle, indent=1, default=float) + "\n")
        return cycle

    def _decide(self, arm, period, c, current, lib_state, record):
        """Gates 1-2 and the candidate (or why there is none)."""
        if not record.get("completed") or not record.get("model_ok"):
            reason = (
                "the session did not complete"
                if not record.get("completed")
                else (f"models used: {record.get('models')}")
            )
            return {"status": "none", "what": "session", "reason": reason}, None, None
        result = record["result"]
        if arm == "5":
            proposed = tuple(tuple(r) for r in result["rules"])
            if not proposed:
                return {"status": "none", "what": "proposal"}, None, None
            candidate = ArmState(current.state_id, proposed)
            if candidate == current:
                return {"status": "none", "what": "proposal"}, None, None
            what = f"proposal of {len(proposed)} rule pairs"
            return {"status": "pending", "what": what}, candidate, None
        p = patch.Patch(result["grows"], result["refines"], result["prunes"], result["problems"])
        what = f"patch ({len(p.grows)} grow, {len(p.refines)} refine, {len(p.prunes)} prune)"
        if p.empty and p.admissible:
            return {"status": "none", "what": "patch"}, None, None
        if not p.admissible:
            reason = "it did not pass the checks or the bounds: " + "; ".join(p.problems)[:600]
            return {"status": "rejected", "what": what, "reason": reason}, None, None
        folder = Path(record["folder"])
        entered = f"{arm}/{self.campaign}/{period}/c{c}"
        provenance = {
            "implemented_by": (
                f"{session.MODEL} via Claude Code {self.claude_version} (headless session "
                f"{record['session_id']}, effort {session.EFFORT})"
            ),
            "specified_by": f"WP3 maintenance protocol ({arm}), brief {record['brief_sha12']}",
            "date": record["finished_utc"][:10],
        }
        new_state, sources = patch.apply(lib_state, p, folder, entered, provenance)
        state.save(new_state, sources, self.paths.results_dir)
        return {"status": "pending", "what": what}, ArmState(new_state.id), None

    def used_names(self, arm: str, period: str, c: int) -> list[str]:
        """Every operator name in any library state of this arm's lineage before cycle ``c`` of
        ``period`` (arm 3's included): a grow must not reuse one (D-071, D-074)."""
        names = {e.name for e in state.arm3_state().entries}
        for p in self.periods[: self.periods.index(period) + 1]:
            for k in range(1, self.cycles + 1):
                if p == period and k >= c:
                    break
                cyc = self.cycle_record(arm, p, k)
                for key in ("state_in", "state_out"):
                    s = state.read(cyc[key]["state_id"], self.paths.results_dir)
                    names |= {e.name for e in s.entries}
        return sorted(names)

    def _history(self, arm: str, period: str, c: int) -> dict[str, list[dict]]:
        """Evidence rows of earlier cycles of this arm (all periods), oldest first."""
        history: dict[str, list[dict]] = {}
        for p in self.periods[: self.periods.index(period) + 1]:
            for k in range(1, self.cycles + 1):
                if p == period and k >= c:
                    break
                path = self._dir(arm, p, k) / "cycle.json"
                if path.exists():
                    for key, row in json.loads(path.read_text())["evidence"].items():
                        history.setdefault(key, []).append(row)
        return history

    # --- whole arms ------------------------------------------------------------------------

    def run_arm(self, arm: str) -> list[dict[str, Any]]:
        cycles = []
        for period in self.periods:
            for c in range(1, self.cycles + 1):
                cycles.append(self.run_cycle(arm, period, c))
            self.write_lineage(arm, period)
        return cycles

    def write_lineage(self, arm: str, period: str) -> Path:
        """Hashes of every state, patch, gate result and session of one arm and period (§5)."""
        rows = []
        for c in range(1, self.cycles + 1):
            cyc = self.cycle_record(arm, period, c)
            transcript = self._dir(arm, period, c) / "session" / "transcript.jsonl"
            rows.append(
                {
                    "cycle": c,
                    "state_in": cyc["state_in"]["state_id"],
                    "state_out": cyc["state_out"]["state_id"],
                    "rules_in": ArmState.from_dict(cyc["state_in"]).batch_key,
                    "rules_out": ArmState.from_dict(cyc["state_out"]).batch_key,
                    "decision": cyc["decision"],
                    "gate": cyc["gate"],
                    "session": cyc["session"],
                    "transcript_sha256": _sha(transcript) if transcript.exists() else None,
                    "code_version": cyc["code_version"],
                }
            )
        out = self.root / arm / period / "lineage.json"
        write_atomic(out, json.dumps({"arm": arm, "period": period, "cycles": rows}, indent=1))
        return out


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
