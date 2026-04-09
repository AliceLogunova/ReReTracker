"""Tests for src/core/data_collector.py."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from src.config import AppConfig
from src.core.data_collector import DataCollector
from src.models import EEGRecord, read_csv


class TestDataCollector:
    def test_begin_session_creates_directories(self, tmp_config: AppConfig) -> None:
        collector = DataCollector(tmp_config, mode="mock")
        collector.begin_session()
        assert tmp_config.raw_dir.exists()
        assert tmp_config.processed_dir.exists()

    def test_add_record_accumulates(
        self, tmp_config: AppConfig, sample_records: list[EEGRecord]
    ) -> None:
        collector = DataCollector(tmp_config, mode="mock")
        collector.begin_session()
        for rec in sample_records:
            collector.add_record(rec)
        assert len(collector.records) == len(sample_records)

    def test_records_snapshot_is_copy(
        self, tmp_config: AppConfig, sample_records: list[EEGRecord]
    ) -> None:
        """Mutating the returned snapshot must not affect internal state."""
        collector = DataCollector(tmp_config, mode="mock")
        collector.begin_session()
        for rec in sample_records:
            collector.add_record(rec)
        snap = collector.records
        snap.clear()
        assert len(collector.records) == len(sample_records)

    def test_end_session_writes_csv(
        self, tmp_config: AppConfig, sample_records: list[EEGRecord]
    ) -> None:
        collector = DataCollector(tmp_config, mode="mock")
        sid = collector.begin_session()
        for rec in sample_records:
            collector.add_record(rec)

        summary = collector.end_session()

        csv_path = tmp_config.raw_dir / f"{sid}.csv"
        assert csv_path.exists(), f"CSV not found at {csv_path}"
        loaded = read_csv(csv_path)
        assert len(loaded) == len(sample_records)

    def test_end_session_writes_json_summary(
        self, tmp_config: AppConfig, sample_records: list[EEGRecord]
    ) -> None:
        collector = DataCollector(tmp_config, mode="mock")
        sid = collector.begin_session()
        for rec in sample_records:
            collector.add_record(rec)
        collector.end_session()

        json_path = tmp_config.processed_dir / f"{sid}_summary.json"
        assert json_path.exists(), f"JSON not found at {json_path}"
        with open(json_path) as fh:
            data = json.load(fh)
        assert data["record_count"] == len(sample_records)
        assert data["mode"] == "mock"

    def test_end_session_summary_values(
        self, tmp_config: AppConfig, sample_records: list[EEGRecord]
    ) -> None:
        collector = DataCollector(tmp_config, mode="mock")
        collector.begin_session()
        for rec in sample_records:
            collector.add_record(rec)
        summary = collector.end_session()

        n = len(sample_records)
        expected_mean_conc = sum(r.concentration for r in sample_records) / n
        assert abs(summary.mean_concentration - expected_mean_conc) < 1e-6

        expected_artifact_ratio = sum(1 for r in sample_records if r.artifact) / n
        assert abs(summary.artifact_ratio - expected_artifact_ratio) < 1e-6

    def test_csv_round_trip_preserves_values(
        self, tmp_config: AppConfig, sample_records: list[EEGRecord]
    ) -> None:
        collector = DataCollector(tmp_config, mode="mock")
        sid = collector.begin_session()
        for rec in sample_records:
            collector.add_record(rec)
        collector.end_session()

        csv_path = tmp_config.raw_dir / f"{sid}.csv"
        loaded = read_csv(csv_path)

        for original, loaded_rec in zip(sample_records, loaded):
            assert abs(original.timestamp - loaded_rec.timestamp) < 1e-6
            assert abs(original.concentration - loaded_rec.concentration) < 1e-6
            assert abs(original.relaxation - loaded_rec.relaxation) < 1e-6
            assert abs(original.fatigue - loaded_rec.fatigue) < 1e-6
            assert original.artifact == loaded_rec.artifact

    def test_empty_session_handled_gracefully(self, tmp_config: AppConfig) -> None:
        collector = DataCollector(tmp_config, mode="mock")
        collector.begin_session()
        summary = collector.end_session()
        assert summary.record_count == 0
        assert summary.mean_concentration == 0.0

    def test_flush_writes_on_batch_boundary(self, tmp_config: AppConfig) -> None:
        """Records should be flushed to CSV when the batch threshold is reached."""
        collector = DataCollector(tmp_config, mode="mock")
        collector._flush_batch_size = 5  # override default for test speed
        sid = collector.begin_session()

        csv_path = tmp_config.raw_dir / f"{sid}.csv"

        base_ts = 1_700_000_000.0
        for i in range(5):
            rec = EEGRecord(timestamp=base_ts + i, concentration=0.5,
                            relaxation=0.5, fatigue=0.1)
            collector.add_record(rec)

        # After 5 records the batch should have been flushed
        assert csv_path.exists()

    def test_mode_stored_in_summary(self, tmp_config: AppConfig) -> None:
        for mode in ("real", "mock"):
            collector = DataCollector(tmp_config, mode=mode)
            collector.begin_session()
            summary = collector.end_session()
            assert summary.mode == mode
