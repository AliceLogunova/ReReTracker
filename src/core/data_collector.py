"""Thread-safe data collector — buffers EEGRecords and persists them to disk."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Optional

from src.config import AppConfig
from src.models import EEGRecord, SessionSummary, write_csv
from src.utils import (
    format_duration,
    processed_json_path,
    raw_csv_path,
    session_id,
)

logger = logging.getLogger(__name__)


class DataCollector:
    """Collects EEGRecords from any data source and saves results to disk.

    Usage::

        collector = DataCollector(config, mode="mock")
        collector.begin_session()

        # Register as the on_data callback for a source:
        source.start(on_data=collector.add_record)

        # ... session runs ...

        source.stop()
        summary = collector.end_session()
        visualizer.render(collector.records, config.plots_dir)
    """

    def __init__(self, config: AppConfig, mode: str = "mock") -> None:
        self._config = config
        self._mode = mode

        self._records: list[EEGRecord] = []
        self._lock = threading.Lock()
        self._session_id: str = ""
        self._start_time: float = 0.0
        self._csv_path: Optional[Path] = None

        # Write to CSV in batches of this size to avoid excessive I/O
        self._flush_batch_size: int = 20
        self._unflushed: list[EEGRecord] = []

    # ── Public interface ──────────────────────────────────────────────────────

    @property
    def records(self) -> list[EEGRecord]:
        """Return a snapshot of all collected records (thread-safe)."""
        with self._lock:
            return list(self._records)

    def begin_session(self) -> str:
        """Initialise a new session; returns the session ID."""
        self._config.ensure_dirs()
        self._session_id = session_id()
        self._start_time = time.time()
        self._csv_path = raw_csv_path(self._config.raw_dir, self._session_id)
        with self._lock:
            self._records.clear()
            self._unflushed.clear()
        logger.info("Session started: %s", self._session_id)
        return self._session_id

    def add_record(self, record: EEGRecord) -> None:
        """Callback-compatible method — appends a record and flushes periodically."""
        with self._lock:
            self._records.append(record)
            self._unflushed.append(record)
            should_flush = len(self._unflushed) >= self._flush_batch_size

        if should_flush:
            self._flush_to_csv()

    def end_session(self) -> SessionSummary:
        """Flush remaining records, write summary JSON, and return a SessionSummary."""
        self._flush_to_csv()  # Write any remaining buffered records

        end_time = time.time()
        records_snapshot = self.records

        relative_csv = str(self._csv_path.relative_to(self._config.data_dir.parent))

        summary = SessionSummary.from_records(
            session_id=self._session_id,
            start_time=self._start_time,
            end_time=end_time,
            records=records_snapshot,
            raw_csv_path=relative_csv,
            mode=self._mode,
        )

        json_path = processed_json_path(self._config.processed_dir, self._session_id)
        summary.save_json(json_path)

        duration_str = format_duration(summary.duration_seconds)
        logger.info(
            "Session ended: %s | %d records | duration %s | "
            "mean conc=%.3f relax=%.3f fatigue=%.3f artifact_ratio=%.1f%%",
            self._session_id,
            summary.record_count,
            duration_str,
            summary.mean_concentration,
            summary.mean_relaxation,
            summary.mean_fatigue,
            summary.artifact_ratio * 100,
        )
        return summary

    # ── Private ───────────────────────────────────────────────────────────────

    def _flush_to_csv(self) -> None:
        """Write any pending records to the CSV file."""
        with self._lock:
            batch = list(self._unflushed)
            self._unflushed.clear()

        if not batch or self._csv_path is None:
            return

        # Append-mode: header only on the very first write
        append = self._csv_path.exists()
        write_csv(self._csv_path, iter(batch), append=append)
        logger.debug("Flushed %d records to %s", len(batch), self._csv_path)
