"""WP2 strategy generation: one isolated, headless Claude Code session per strategy (D-035).

A session runs in a fresh folder outside the repository and Box that holds only ``BRIEF.md`` and
``strategy_api.py``. Its tools are the file tools (confined to that folder) and the two MCP tools
of ``mcp_devtool`` (check, backtest on anonymised development data). It has no shell, no web
tools, no other MCP servers, no skills and none of the user's settings. Everything is archived
under ``results/wp2/strategy_generation/<slot>/``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from string import Template
from typing import Any

from lpstgp.strategies import api, devtool, execute

PROMPTS = Path(__file__).resolve().parent / "prompts"
BRIEF = PROMPTS / "brief.md"
# Session folders: outside the repository (no CLAUDE.md above them) and neutrally named, so the
# working directory reveals nothing about the project.
GEN_ROOT = Path.home() / "Library" / "Caches" / "strategy-sessions"
MODEL = "claude-opus-5-5"
EFFORT = "high"
BUDGET = 40
MAX_CHECKS = 100
SLOTS_PER_DOMAIN = 4

DOMAINS: dict[str, tuple[str, str]] = {
    "information_theory": (
        "information theory",
        "entropy, mutual information, complexity and compressibility of the return process "
        "(for example Shannon or Rényi entropy, permutation entropy, Lempel–Ziv complexity, "
        "transfer entropy, rate–distortion).",
    ),
    "information_geometry": (
        "information geometry",
        "the geometry of families of probability distributions estimated from recent data "
        "(for example Fisher information, Fisher–Rao and other geodesic distances, "
        "α-divergences, curvature of statistical manifolds).",
    ),
    "optimal_transport": (
        "optimal transport",
        "distances and maps between probability distributions (for example Wasserstein "
        "distances, Sinkhorn divergences, transport plans and costs between recent and earlier "
        "return distributions).",
    ),
    "rough_paths": (
        "rough path theory",
        "the signature and other iterated-integral descriptions of the price path (for example "
        "signature terms, Lévy area, signature kernels, p-variation and path roughness).",
    ),
    "fractal": (
        "fractal analysis",
        "scaling, self-similarity and long memory (for example Hurst exponents by rescaled "
        "range or detrended fluctuation analysis, fractal dimensions, multifractal spectra).",
    ),
    "statistical_physics": (
        "statistical physics",
        "ideas from statistical mechanics and complex systems (for example critical slowing "
        "down and early-warning indicators, Kramers–Moyal drift and diffusion, Tsallis "
        "statistics, power-law tails, order parameters and phase transitions).",
    ),
    "spectral": (
        "spectral analysis",
        "frequency- and scale-domain descriptions of the series (for example periodograms and "
        "spectral entropy, spectral slopes, wavelet energy distributions, singular-spectrum "
        "analysis).",
    ),
}


@dataclass(frozen=True)
class Slot:
    domain: str
    k: int  # 1..SLOTS_PER_DOMAIN

    @property
    def sid(self) -> str:
        return f"s{list(DOMAINS).index(self.domain) * SLOTS_PER_DOMAIN + self.k:02d}"

    @property
    def name(self) -> str:
        return f"{self.sid}_{self.domain}_{self.k}"


def all_slots() -> list[Slot]:
    return [Slot(d, k) for d in DOMAINS for k in range(1, SLOTS_PER_DOMAIN + 1)]


def sha12(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def render_brief(
    slot: Slot,
    earlier: Sequence[Mapping[str, str]],
    fitness: Mapping[str, Any],
    dev: devtool.DevData,
    template: str | None = None,
) -> str:
    """The session prompt: domain scope, earlier strategies to differ from, contract, objective."""
    title, scope = DOMAINS[slot.domain]
    if earlier:
        lines = "\n".join(f"- **{e['name']}**: {e['hypothesis']}" for e in earlier)
        earlier_text = (
            "Earlier strategies from this field (yours must rest on a clearly different "
            f"mathematical idea):\n\n{lines}"
        )
    else:
        earlier_text = "You are the first to work on this field."
    classes: dict[str, int] = {}
    for cls in dev.asset_class.values():
        classes[cls] = classes.get(cls, 0) + 1
    names = {"equity_index": "equity indices", "fx": "currency pairs", "commodity": "commodities"}
    mix = ", ".join(f"{n} {names.get(c, c)}" for c, n in sorted(classes.items()))
    return Template(template or BRIEF.read_text(encoding="utf-8")).substitute(
        domain_title=title,
        domain_scope=scope,
        earlier=earlier_text,
        max_signals=api.MAX_SIGNALS,
        max_lookback=api.MAX_LOOKBACK,
        max_checks=MAX_CHECKS,
        budget=BUDGET,
        n_instruments=len(dev.instruments),
        class_mix=mix,
        years=8,
        min_exposure=fitness["min_exposure_bars"],
        lambda_dd=fitness["lambda_drawdown"],
        lambda_to=fitness["lambda_turnover"],
        no_trade=fitness["no_trade_value"],
    )


def prepare_session(folder: Path, brief: str) -> None:
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "BRIEF.md").write_text(brief, encoding="utf-8")
    shutil.copyfile(Path(api.__file__), folder / "strategy_api.py")


def mcp_config(folder: Path, archive: Path) -> dict:
    return {
        "mcpServers": {
            "devtool": {
                "type": "stdio",
                "command": sys.executable,
                "args": [
                    "-m",
                    "lpstgp.strategies.mcp_devtool",
                    "--session",
                    str(folder),
                    "--archive",
                    str(archive),
                    "--budget",
                    str(BUDGET),
                    "--max-checks",
                    str(MAX_CHECKS),
                ],
            }
        }
    }


ALLOWED_TOOLS = (
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "mcp__devtool__check",
    "mcp__devtool__backtest",
)
SESSION_SETTINGS = {"autoMemoryEnabled": False}
PROMPT = "Read BRIEF.md in this folder and carry out the task it describes."


def claude_command(
    folder: Path, archive: Path, session_id: str, resume: str | None = None
) -> list[str]:
    archive.mkdir(parents=True, exist_ok=True)
    cfg = archive / "mcp.json"
    cfg.write_text(json.dumps(mcp_config(folder, archive), indent=1), encoding="utf-8")
    cmd = [
        "claude",
        "-p",
        PROMPT if resume is None else resume,
        "--model",
        MODEL,
        "--effort",
        EFFORT,
        "--restricted",
        "--disable-slash-commands",
        "--strict-mcp-config",
        "--mcp-config",
        str(cfg),
        "--tools",
        "Read,Write,Edit,Glob,Grep",
        "--allowedTools",
        " ".join(ALLOWED_TOOLS),
        "--permission-mode",
        "dontAsk",
        "--settings",
        json.dumps(SESSION_SETTINGS),
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    cmd += ["--resume", session_id] if resume is not None else ["--session-id", session_id]
    return cmd


def session_env() -> dict[str, str]:
    """Scrubbed environment: subscription login (no API key), no auto-update, thread caps."""
    keep = ("PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "TMPDIR", "TERM")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env.update({"DISABLE_AUTOUPDATER": "1", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"})
    if "LPSTGP_PATHS" in os.environ:
        env["LPSTGP_PATHS"] = os.environ["LPSTGP_PATHS"]
    return env


def run_claude(cmd: Sequence[str], folder: Path, archive: Path, name: str, timeout: float) -> dict:
    """Run one ``claude -p`` invocation; stream-json goes to ``<name>.jsonl``."""
    stream, errors = archive / f"{name}.jsonl", archive / f"{name}.stderr.txt"
    with stream.open("w") as out, errors.open("w") as err:
        try:
            proc = subprocess.run(
                cmd, cwd=folder, env=session_env(), stdout=out, stderr=err, timeout=timeout
            )
            code = proc.returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
    return {"exit": code, **usage(stream)}


def usage(stream: Path) -> dict[str, Any]:
    """Final result and per-message models from a stream-json transcript."""
    result, models = {}, set()
    for line in stream.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "assistant":
            model = event.get("message", {}).get("model")
            if model:
                models.add(model)
        elif event.get("type") == "result":
            result = event
    keys = (
        "subtype",
        "is_error",
        "num_turns",
        "duration_ms",
        "total_cost_usd",
        "usage",
        "session_id",
    )
    return {"models": sorted(models), **{k: result.get(k) for k in keys}}


def copy_transcript(folder: Path, session_id: str, archive: Path) -> None:
    """Claude Code keeps the full session under ~/.claude/projects/<folder key>/<id>.jsonl."""
    key = re.sub(r"[^A-Za-z0-9]", "-", str(folder.resolve()))
    source = Path.home() / ".claude" / "projects" / key / f"{session_id}.jsonl"
    if source.exists():
        shutil.copyfile(source, archive / "transcript.jsonl")


def finalize(folder: Path, archive: Path, paths, settings) -> dict[str, Any]:
    """Gates, cross-process determinism, metadata, dev-fit and dev-holdout scores of the result."""
    from lpstgp.runner import configs_from_settings
    from lpstgp.splits import Stage

    final = folder / "strategy.py"
    if not final.exists():
        return {"accepted": False, "reason": "no strategy.py"}
    shutil.copyfile(final, archive / "final_strategy.py")
    work = archive / "final"
    _, fitness = configs_from_settings(settings)
    fit = devtool.build(paths, settings, Stage.FIT, work / "inputs")
    holdout = devtool.build(paths, settings, Stage.VALIDATE, work / "inputs")
    check = devtool.check(final, work / "check", fit)
    described = execute.run("describe", final, work / "describe")
    hashes = [execute.run("hash", final, work / f"hash{t}", threads=t).get("hash") for t in (1, 4)]
    deterministic = hashes[0] is not None and hashes[0] == hashes[1]
    accepted = bool(check.get("passed")) and deterministic and described.get("ok", False)
    out = {
        "accepted": accepted,
        "sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
        "check": check,
        "cross_process_deterministic": deterministic,
        "strategy": described.get("strategy"),
    }
    if accepted:
        out["dev_fit"] = devtool.backtest(final, work / "fit", fit, fitness)
        out["dev_holdout"] = devtool.backtest(final, work / "holdout", holdout, fitness)
    shutil.rmtree(work / "inputs", ignore_errors=True)
    return out


def run_session(
    slot: Slot,
    earlier: Sequence[Mapping[str, str]],
    root: Path,
    archive_root: Path,
    paths,
    settings,
    timeout: float = 3 * 3600,
    claude_version: str = "",
) -> dict[str, Any]:
    from lpstgp.runner import configs_from_settings
    from lpstgp.splits import Stage

    _, fitness = configs_from_settings(settings)
    archive = archive_root / slot.name
    archive.mkdir(parents=True, exist_ok=True)
    dev = devtool.build(paths, settings, Stage.FIT, archive / "inputs")
    template = BRIEF.read_text(encoding="utf-8")
    brief = render_brief(slot, earlier, vars(fitness), dev, template)
    session_id = str(uuid.uuid4())
    folder = root / session_id
    prepare_session(folder, brief)
    record: dict[str, Any] = {
        "slot": slot.name,
        "sid": slot.sid,
        "domain": slot.domain,
        "session_id": session_id,
        "folder": str(folder),
        "started_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": MODEL,
        "effort": EFFORT,
        "budget": BUDGET,
        "claude_version": claude_version,
        "brief_template_sha12": sha12(template),
        "brief_sha12": sha12(brief),
        "earlier": list(earlier),
    }
    (archive / "BRIEF.md").write_text(brief, encoding="utf-8")
    cmd = claude_command(folder, archive, session_id)
    record["command"] = cmd
    record["runs"] = [run_claude(cmd, folder, archive, "stream", timeout)]
    result = finalize(folder, archive, paths, settings)
    if not result["accepted"] and (folder / "strategy.py").exists():
        failures = json.dumps(result.get("check", {}).get("failures", []), default=float)[:4000]
        repair = (
            "The final check failed. Fix strategy.py so that it passes check (you may run check "
            f"again; do not use more backtests than you have left). Problems:\n{failures}"
        )
        cmd = claude_command(folder, archive, session_id, resume=repair)
        record["runs"].append(run_claude(cmd, folder, archive, "repair", timeout / 2))
        result = finalize(folder, archive, paths, settings)
        result["repaired"] = True
    copy_transcript(folder, session_id, archive)
    record.update(result)
    record["finished_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    (archive / "summary.json").write_text(
        json.dumps(record, indent=1, default=float), encoding="utf-8"
    )
    return record
