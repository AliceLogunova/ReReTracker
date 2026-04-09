"""Tests for src/core/capsule_client.py (MockSource and error paths)."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import AppConfig
from src.core.capsule_client import MockSource, _clamp, _noise
from src.models import EEGRecord


# ---------------------------------------------------------------------------
# MockSource tests
# ---------------------------------------------------------------------------

class TestMockSource:
    def test_emits_records(self, tmp_config: AppConfig) -> None:
        """MockSource should call on_data at least once within a short window."""
        received: list[EEGRecord] = []
        source = MockSource(tmp_config)
        source.start(on_data=received.append)
        time.sleep(0.5)
        source.stop()
        assert len(received) > 0

    def test_record_fields_in_range(self, tmp_config: AppConfig) -> None:
        """All metric scores must be within [0, 1]."""
        received: list[EEGRecord] = []
        source = MockSource(tmp_config)
        source.start(on_data=received.append)
        time.sleep(0.5)
        source.stop()

        for rec in received:
            assert 0.0 <= rec.concentration <= 1.0, f"concentration out of range: {rec}"
            assert 0.0 <= rec.relaxation <= 1.0, f"relaxation out of range: {rec}"
            assert 0.0 <= rec.fatigue <= 1.0, f"fatigue out of range: {rec}"

    def test_stop_halts_emission(self, tmp_config: AppConfig) -> None:
        """No records should arrive after stop() is called."""
        received: list[EEGRecord] = []
        source = MockSource(tmp_config)
        source.start(on_data=received.append)
        time.sleep(0.3)
        source.stop()
        count_at_stop = len(received)
        time.sleep(0.3)
        # Allow one in-flight record, but not a continuous stream
        assert len(received) <= count_at_stop + 1

    def test_timestamps_monotone(self, tmp_config: AppConfig) -> None:
        """Timestamps must be non-decreasing."""
        received: list[EEGRecord] = []
        source = MockSource(tmp_config)
        source.start(on_data=received.append)
        time.sleep(0.5)
        source.stop()

        timestamps = [r.timestamp for r in received]
        assert timestamps == sorted(timestamps)

    def test_emit_rate_respected(self, tmp_config: AppConfig) -> None:
        """Emission rate should be within 50%–200% of mock_emit_hz."""
        tmp_config.mock_emit_hz = 5.0
        received: list[EEGRecord] = []
        source = MockSource(tmp_config)
        source.start(on_data=received.append)
        duration = 1.0
        time.sleep(duration)
        source.stop()

        expected = tmp_config.mock_emit_hz * duration
        assert expected * 0.5 <= len(received) <= expected * 2.0


# ---------------------------------------------------------------------------
# CapsuleDLLSource error path
# ---------------------------------------------------------------------------

class TestCapsuleDLLSourceErrors:
    def test_missing_dll_raises(self, tmp_config: AppConfig) -> None:
        """CapsuleDLLSource.start() must raise if the DLL file does not exist."""
        from src.core.capsule_client import CapsuleDLLSource

        tmp_config.dll_path = Path("/nonexistent/CapsuleClient.dll")
        source = CapsuleDLLSource(tmp_config)

        with pytest.raises((OSError, FileNotFoundError, Exception)):
            source.start(on_data=lambda r: None)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_clamp_within_bounds(self) -> None:
        assert _clamp(0.5) == 0.5
        assert _clamp(-0.1) == 0.0
        assert _clamp(1.1) == 1.0
        assert _clamp(0.5, 0.2, 0.8) == 0.5
        assert _clamp(0.1, 0.2, 0.8) == 0.2
        assert _clamp(0.9, 0.2, 0.8) == 0.8

    def test_noise_within_amplitude(self) -> None:
        amplitude = 0.1
        for _ in range(1000):
            n = _noise(amplitude)
            assert -amplitude <= n <= amplitude
