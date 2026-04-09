"""Real-time metrics display panel.

Shows current concentration / relaxation / fatigue values, recording status,
elapsed time, record count, and an artifact indicator — all updated live as
records arrive from the data source.
"""

from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.models import EEGRecord


class MetricsPanel(QWidget):
    """Displays live EEG metric values and session status."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._session_start: Optional[float] = None
        self._record_count: int = 0
        self._artifact_count: int = 0

        # Timer that refreshes the elapsed-time counter every 500 ms
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._refresh_elapsed)

        self._build_ui()

    # ── Public slots / methods ────────────────────────────────────────────────

    def on_session_started(self) -> None:
        """Call when a session begins to reset counters and start the timer."""
        self._session_start = time.monotonic()
        self._record_count = 0
        self._artifact_count = 0
        self._reset_metric_labels()
        self._set_status("Recording", "color: #2e7d32; font-weight: bold;")
        self._timer.start()

    def on_record_received(self, record: EEGRecord) -> None:
        """Update displayed values with the latest EEGRecord."""
        self._record_count += 1
        if record.artifact:
            self._artifact_count += 1

        self._conc_val.setText(f"{record.concentration:.3f}")
        self._relax_val.setText(f"{record.relaxation:.3f}")
        self._fatigue_val.setText(f"{record.fatigue:.3f}")
        self._records_val.setText(str(self._record_count))

        art_ratio = (
            self._artifact_count / self._record_count * 100
            if self._record_count > 0
            else 0.0
        )
        if record.artifact:
            self._artifact_val.setText(f"YES  ({art_ratio:.1f}%)")
            self._artifact_val.setStyleSheet("color: #e65100; font-weight: bold;")
        else:
            self._artifact_val.setText(f"no  ({art_ratio:.1f}%)")
            self._artifact_val.setStyleSheet("")

    def on_session_finished(self) -> None:
        """Call when recording ends (by duration or stop request)."""
        self._timer.stop()
        self._set_status("Finished", "color: #1565c0; font-weight: bold;")

    def on_idle(self) -> None:
        """Reset to the idle / no-session state."""
        self._timer.stop()
        self._session_start = None
        self._elapsed_val.setText("--:--:--")
        self._reset_metric_labels()
        self._set_status("Idle", "color: gray;")

    # ── Private ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        group = QGroupBox("Live Metrics")
        grid = QGridLayout(group)
        grid.setContentsMargins(8, 12, 8, 8)
        grid.setSpacing(6)
        grid.setColumnStretch(1, 1)

        def _add_row(label_text: str, row: int) -> QLabel:
            lbl = QLabel(f"<b>{label_text}</b>")
            grid.addWidget(lbl, row, 0)
            val = QLabel("---")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(val, row, 1)
            return val

        self._status_val = _add_row("Status", 0)
        self._elapsed_val = _add_row("Elapsed", 1)
        self._conc_val = _add_row("Concentration", 2)
        self._relax_val = _add_row("Relaxation", 3)
        self._fatigue_val = _add_row("Fatigue", 4)
        self._records_val = _add_row("Records", 5)
        self._artifact_val = _add_row("Artifact", 6)

        root.addWidget(group)
        root.addStretch()

        # Set initial state
        self.on_idle()

    def _set_status(self, text: str, style: str) -> None:
        self._status_val.setText(text)
        self._status_val.setStyleSheet(style)

    def _reset_metric_labels(self) -> None:
        for lbl in (self._conc_val, self._relax_val, self._fatigue_val):
            lbl.setText("---")
        self._records_val.setText("0")
        self._artifact_val.setText("no  (0.0%)")
        self._artifact_val.setStyleSheet("")

    def _refresh_elapsed(self) -> None:
        if self._session_start is None:
            return
        elapsed = int(time.monotonic() - self._session_start)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self._elapsed_val.setText(f"{h:02d}:{m:02d}:{s:02d}")
