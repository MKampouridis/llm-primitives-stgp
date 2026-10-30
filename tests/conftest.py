"""Shared test configuration.

Tests marked ``realdata`` need the local processed Tier A data and are skipped when it is absent
(always the case in CI). Hypothesis runs without a deadline (numba compilation would trip it) and
keeps its example database in the configured cache directory, outside the repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck
from hypothesis import settings as hypothesis_settings
from hypothesis.database import DirectoryBasedExampleDatabase

from lpstgp.config import ConfigError, load_paths


def _local_paths():
    try:
        return load_paths()
    except ConfigError:
        return None


LOCAL_PATHS = _local_paths()


def _has_tier_a() -> bool:
    if LOCAL_PATHS is None:
        return False
    processed: Path = LOCAL_PATHS.tier_dir("A") / "processed"
    return any(processed.glob("*.parquet"))


HAS_TIER_A = _has_tier_a()

hypothesis_settings.register_profile(
    "lpstgp",
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
    database=(
        DirectoryBasedExampleDatabase(str(LOCAL_PATHS.cache_dir / "hypothesis"))
        if LOCAL_PATHS
        else None
    ),
)
hypothesis_settings.load_profile("lpstgp")


def pytest_collection_modifyitems(config, items):
    if HAS_TIER_A:
        return
    skip = pytest.mark.skip(reason="local Tier A data not available")
    for item in items:
        if "realdata" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def tier_a_dir() -> Path:
    if not HAS_TIER_A:
        pytest.skip("local Tier A data not available")
    return LOCAL_PATHS.tier_dir("A")
