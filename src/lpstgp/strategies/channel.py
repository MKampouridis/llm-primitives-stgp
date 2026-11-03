"""The host–worker channel for untrusted LLM code (D-081).

The host sends the worker a one-time secret and the input arrays through **stdin**, never as a
file: the worker reads them completely before it imports the untrusted module, so the module
cannot open the inputs (the sandbox no longer lets it read them) or reach the secret (the source
policy refuses introspection). The worker signs its result with the secret (HMAC-SHA256) and the
host refuses a result whose signature does not match, so a result file written by the untrusted
code itself is detected, not trusted.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import secrets
import sys
from pathlib import Path

import numpy as np

Inputs = dict[str, tuple[np.ndarray, np.ndarray, int]]


def new_secret() -> str:
    return secrets.token_hex(32)


def message(secret: str, inputs_path: Path | None) -> bytes:
    """What the host writes to the worker's stdin: the secret line, then the npz bytes (if any)."""
    payload = Path(inputs_path).read_bytes() if inputs_path else b""
    return secret.encode() + b"\n" + payload


def receive(stream=None) -> tuple[str, Inputs]:
    """Worker side: read the secret and the inputs from stdin (call before loading any LLM code)."""
    data = (stream or sys.stdin.buffer).read()
    line, _, payload = data.partition(b"\n")
    return line.decode(), _inputs(payload)


def _inputs(payload: bytes) -> Inputs:
    if not payload:
        return {}
    with np.load(io.BytesIO(payload), allow_pickle=False) as npz:
        names = sorted(k.split("::", 1)[1] for k in npz.files if k.startswith("lp::"))
        return {n: (npz[f"lp::{n}"], npz[f"lr::{n}"], int(npz[f"start::{n}"])) for n in names}


def signature(secret: str, data: bytes) -> str:
    return hmac.new(secret.encode(), data, hashlib.sha256).hexdigest()


def sig_path(path: Path) -> Path:
    return path.with_name(path.name + ".sig")


def write_signed(path: Path, data: bytes, secret: str) -> None:
    path.write_bytes(data)
    sig_path(path).write_text(signature(secret, data))


def read_verified(path: Path, secret: str) -> bytes | None:
    """The result's bytes if the worker signed them with this secret, else None."""
    sig = sig_path(path)
    if not path.exists() or not sig.exists():
        return None
    data = path.read_bytes()
    return data if hmac.compare_digest(sig.read_text(), signature(secret, data)) else None
