"""Tests for src/visualization/visualizer.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import AppConfig
from src.models import EEGRecord
from src.visualization import visualizer


class TestRender:
    def test_creates_four_plots(
        self, tmp_path: Path, sample_records: list[EEGRecord]
    ) -> None:
        plots_dir = tmp_path / "plots"
        paths = visualizer.render(sample_records, plots_dir)

        assert "concentration" in paths
        assert "relaxation" in paths
        assert "fatigue" in paths
        assert "combined" in paths

    def test_output_files_exist(
        self, tmp_path: Path, sample_records: list[EEGRecord]
    ) -> None:
        plots_dir = tmp_path / "plots"
        paths = visualizer.render(sample_records, plots_dir)

        for name, path in paths.items():
            assert path.exists(), f"Plot file missing: {name} → {path}"
            assert path.stat().st_size > 0, f"Plot file empty: {name} → {path}"

    def test_expected_filenames(
        self, tmp_path: Path, sample_records: list[EEGRecord]
    ) -> None:
        plots_dir = tmp_path / "plots"
        visualizer.render(sample_records, plots_dir)

        assert (plots_dir / "concentration_vs_time.png").exists()
        assert (plots_dir / "relaxation_vs_time.png").exists()
        assert (plots_dir / "fatigue_vs_time.png").exists()
        assert (plots_dir / "combined_metrics.png").exists()

    def test_empty_records_returns_empty_dict(self, tmp_path: Path) -> None:
        """render() with no records should return an empty dict without error."""
        plots_dir = tmp_path / "plots"
        result = visualizer.render([], plots_dir)
        assert result == {}

    def test_single_record_does_not_crash(self, tmp_path: Path) -> None:
        """render() should succeed even with just one record."""
        plots_dir = tmp_path / "plots"
        records = [EEGRecord(timestamp=1_700_000_000.0, concentration=0.5,
                             relaxation=0.6, fatigue=0.3)]
        paths = visualizer.render(records, plots_dir)
        assert len(paths) == 4

    def test_plots_dir_created_automatically(
        self, tmp_path: Path, sample_records: list[EEGRecord]
    ) -> None:
        """render() should create the plots directory if it doesn't exist."""
        plots_dir = tmp_path / "deep" / "nested" / "plots"
        assert not plots_dir.exists()
        visualizer.render(sample_records, plots_dir)
        assert plots_dir.exists()

    def test_artifacts_do_not_crash_plot(self, tmp_path: Path) -> None:
        """Plots with artifact markers must not raise."""
        base = 1_700_000_000.0
        records = [
            EEGRecord(timestamp=base + i, concentration=0.5, relaxation=0.5,
                      fatigue=0.1, artifact=(i % 2 == 0))
            for i in range(20)
        ]
        plots_dir = tmp_path / "plots"
        # Should not raise
        visualizer.render(records, plots_dir)
