"""Session lifecycle controller — bridges the desktop UI and the MVP backend.

This is a thin orchestration layer.  It creates the correct data source
(real or mock), a DataCollector, and a RecordingWorker, then wires them
together.  Business logic (SDK interaction, CSV flushing, JSON summary,
plot rendering) all lives in the existing MVP modules.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from src.config import AppConfig
from src.core.capsule_client import CapsuleDLLSource, MockSource
from src.core.data_collector import DataCollector
from src.models import EEGRecord, SessionSummary
from src.visualization import visualizer
from src.ui.workers.recording_worker import RecordingWorker


class SessionController(QObject):
    """Manages the full EEG session lifecycle for the desktop UI.

    Signals
    -------
    session_started : Signal(str)
        Emitted when recording begins; carries the session ID string.
    record_received : Signal(object)
        Re-emits every :class:`~src.models.EEGRecord` from the worker so
        multiple UI panels can connect to a single signal.
    session_finished : Signal(object)
        Emitted after the session has been fully finalised; carries the
        :class:`~src.models.SessionSummary`.
    error_occurred : Signal(str)
        Emitted on any unrecoverable error (DLL missing, source failure, …).
    status_changed : Signal(str)
        Human-readable status messages suitable for a status bar.
    """

    session_started: Signal = Signal(str)
    record_received: Signal = Signal(object)   # EEGRecord
    session_finished: Signal = Signal(object)  # SessionSummary
    error_occurred: Signal = Signal(str)
    status_changed: Signal = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._worker: Optional[RecordingWorker] = None
        self._collector: Optional[DataCollector] = None
        self._config: Optional[AppConfig] = None
        self._no_plots: bool = False
        self._last_summary: Optional[SessionSummary] = None

    # ── Public interface ──────────────────────────────────────────────────────

    @property
    def last_summary(self) -> Optional[SessionSummary]:
        """The :class:`SessionSummary` from the most recently finished session."""
        return self._last_summary

    @property
    def plots_dir(self) -> Optional[Path]:
        """Directory where plots are saved, or *None* if no session has run."""
        return self._config.plots_dir if self._config else None

    def start_session(
        self,
        *,
        mode: str,
        device_id: Optional[str] = None,
        duration: float = 0.0,
        output_dir: Optional[str] = None,
        no_plots: bool = False,
    ) -> None:
        """Start a new recording session.

        Parameters
        ----------
        mode:
            ``"mock"`` for synthetic data or ``"real"`` for CapsuleAPI DLL.
        device_id:
            Optional Bluetooth MAC address for the target Neiry device.
            *None* means auto-discover (real mode only).
        duration:
            Session length in seconds; ``0`` means unlimited.
        output_dir:
            Override the data output directory.  *None* uses the default.
        no_plots:
            If *True*, skip automatic plot generation after the session.
        """
        if self._worker is not None and self._worker.isRunning():
            self.status_changed.emit("A session is already running.")
            return

        config = AppConfig()
        if output_dir:
            config.data_dir = Path(output_dir)
        config.ensure_dirs()

        self._config = config
        self._no_plots = no_plots

        if mode == "real":
            if not config.dll_path.exists():
                self.error_occurred.emit(
                    f"DLL not found at:\n  {config.dll_path}\n\n"
                    "Ensure CapsuleAPI/bin/CapsuleClient.dll is present."
                )
                return
            source = CapsuleDLLSource(config, device_id=device_id)
        else:
            source = MockSource(config)

        collector = DataCollector(config, mode=mode)
        sid = collector.begin_session()
        self._collector = collector

        worker = RecordingWorker(source, duration=duration, parent=self)
        worker.record_received.connect(self.record_received)
        worker.error_occurred.connect(self._on_worker_error)
        worker.finished_recording.connect(self._on_recording_finished)
        self._worker = worker

        worker.start()
        self.session_started.emit(sid)
        self.status_changed.emit(f"Recording — session {sid}")

    def stop_session(self) -> None:
        """Request a graceful stop of the active recording session."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_stop()
            self.status_changed.emit("Stop requested…")

    def save_plots(self) -> dict[str, Path]:
        """(Re-)render and save final charts to PNG.

        Returns a ``{chart_name: file_path}`` mapping, or an empty dict if
        there are no records to plot.
        """
        if self._collector is None or self._config is None:
            return {}
        records = self._collector.records
        if not records:
            return {}
        return visualizer.render(records, self._config.plots_dir)

    def open_output_folder(self) -> None:
        """Open the data output directory in the system file manager."""
        if self._config is None:
            return
        folder = str(self._config.data_dir)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", folder])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])

    # ── Private ───────────────────────────────────────────────────────────────

    def _on_worker_error(self, message: str) -> None:
        self.error_occurred.emit(message)
        self.status_changed.emit(f"Error: {message}")

    def _on_recording_finished(self) -> None:
        """Finalise the session: flush CSV, write JSON, optionally render plots."""
        if self._collector is None or self._config is None:
            return

        summary = self._collector.end_session()
        self._last_summary = summary

        if not self._no_plots and summary.record_count > 0:
            try:
                visualizer.render(self._collector.records, self._config.plots_dir)
            except Exception as exc:  # noqa: BLE001
                self.error_occurred.emit(f"Plot export failed: {exc}")

        self.session_finished.emit(summary)
        self.status_changed.emit(
            f"Session complete — {summary.record_count} records, "
            f"{summary.duration_seconds:.1f} s"
        )
