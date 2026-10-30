"""Configuration: machine paths (``config/paths.toml``) and experiment settings (``config/settings.toml``)."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
PATH_KEYS = ("data_dir", "results_dir", "reports_dir", "cache_dir")

# Path fragments of cloud-synced folders; caches must never live inside one.
CLOUD_SYNC_MARKERS = ("Library/CloudStorage", "Library/Mobile Documents", "Dropbox", "OneDrive")


class ConfigError(RuntimeError):
    """Missing or invalid configuration."""


@dataclass(frozen=True)
class Paths:
    data_dir: Path
    results_dir: Path
    reports_dir: Path
    cache_dir: Path

    def tier_dir(self, tier: str) -> Path:
        return self.data_dir / f"tier{tier}"


def _expand(value: str) -> Path:
    return Path(os.path.expanduser(value)).resolve()


def is_cloud_synced(path: Path) -> bool:
    text = str(path)
    return any(marker in text for marker in CLOUD_SYNC_MARKERS)


def load_paths(path: Path | str | None = None) -> Paths:
    """Load machine paths from ``path``, ``$LPSTGP_PATHS`` or ``config/paths.toml``."""
    source = Path(path or os.environ.get("LPSTGP_PATHS") or CONFIG_DIR / "paths.toml")
    if not source.is_file():
        raise ConfigError(
            f"{source} not found; copy config/paths.example.toml to config/paths.toml"
        )
    raw = tomllib.loads(source.read_text(encoding="utf-8"))
    missing = [key for key in PATH_KEYS if key not in raw]
    if missing:
        raise ConfigError(f"{source}: missing keys {missing}")
    paths = Paths(**{key: _expand(raw[key]) for key in PATH_KEYS})
    if is_cloud_synced(paths.cache_dir):
        raise ConfigError(f"cache_dir {paths.cache_dir} is inside a cloud-synced folder")
    return paths


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def load_settings(path: Path | str | None = None) -> Mapping[str, Any]:
    """Experiment settings as a read-only nested mapping."""
    source = Path(path or CONFIG_DIR / "settings.toml")
    return _freeze(tomllib.loads(source.read_text(encoding="utf-8")))
