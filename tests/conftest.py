"""Shared pytest fixtures."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.config import AppConfig
from src.models import EEGRecord


@pytest.fixture()
def tmp_config(tmp_path: Path) -> AppConfig:
    """AppConfig with all data directories pointing to a temporary directory."""
    config = AppConfig()
    config.data_dir = tmp_path / "data"
    config.data_dir.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture()
def sample_records() -> list[EEGRecord]:
    """A small list of deterministic EEGRecords for use in tests."""
    base_ts = 1_700_000_000.0
    return [
        EEGRecord(timestamp=base_ts + i, concentration=0.1 * i, relaxation=0.9 - 0.1 * i,
                  fatigue=0.05 * i, artifact=(i % 5 == 0))
        for i in range(10)
    ]
