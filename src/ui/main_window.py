"""Main application window.

Assembles the ControlPanel (left sidebar), MetricsPanel (left sidebar),
and LivePlotWidget (right area) inside a QSplitter.  A post-session action
bar is revealed after a session ends, exposing Save Charts, Open Folder,
and Show Summary actions.
"""

from __future__ import annotations

import datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.models import SessionSummary
from src.ui.controllers.session_controller import SessionController
from src.ui.widgets.control_panel import ControlPanel
from src.ui.widgets.live_plot_widget import LivePlotWidget
from src.ui.widgets.metrics_panel import MetricsPanel


class MainWindow(QMainWindow):
    """Top-level window for the ReReTracker desktop application."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ReReTracker — EEG Brain Activity Tracker")
        self.resize(1440, 860)

        self._controller = SessionController(parent=self)
        self._build_ui()
        self._connect_signals()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Main horizontal split ─────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left sidebar: control + metrics panels
        sidebar = QWidget()
        sidebar.setMinimumWidth(280)
        sidebar.setMaximumWidth(360)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(6)

        self._control_panel = ControlPanel()
        self._metrics_panel = MetricsPanel()
        sb_layout.addWidget(self._control_panel, stretch=3)
        sb_layout.addWidget(self._metrics_panel, stretch=2)

        splitter.addWidget(sidebar)

        # Right area: live charts
        self._plot_widget = LivePlotWidget()
        splitter.addWidget(self._plot_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, stretch=1)

        # ── Post-session action bar (hidden until session ends) ───────────────
        self._action_bar = self._build_action_bar()
        root.addWidget(self._action_bar)
        self._action_bar.hide()

        # ── Status bar ────────────────────────────────────────────────────────
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready — choose a mode and press Start.")

    def _build_action_bar(self) -> QGroupBox:
        group = QGroupBox("Post-Session Actions")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._save_plots_btn = QPushButton("Save Charts as PNG")
        self._save_plots_btn.setToolTip(
            "Re-render and save concentration / relaxation / fatigue charts"
        )
        self._open_folder_btn = QPushButton("Open Output Folder")
        self._open_folder_btn.setToolTip("Open the data directory in the file manager")
        self._show_summary_btn = QPushButton("Show Session Summary")
        self._show_summary_btn.setToolTip("Display aggregated statistics for this session")

        for btn in (self._save_plots_btn, self._open_folder_btn, self._show_summary_btn):
            layout.addWidget(btn)
        layout.addStretch()

        return group

    # ── Signal wiring ─────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        # Control panel → controller
        self._control_panel.start_mock_requested.connect(self._on_start_mock)
        self._control_panel.start_real_requested.connect(self._on_start_real)
        self._control_panel.stop_requested.connect(self._controller.stop_session)

        # Controller → panels
        self._controller.session_started.connect(self._on_session_started)
        self._controller.record_received.connect(self._plot_widget.add_record)
        self._controller.record_received.connect(self._metrics_panel.on_record_received)
        self._controller.session_finished.connect(self._on_session_finished)
        self._controller.error_occurred.connect(self._on_error)
        self._controller.status_changed.connect(self._status_bar.showMessage)

        # Post-session actions
        self._save_plots_btn.clicked.connect(self._on_save_plots)
        self._open_folder_btn.clicked.connect(self._controller.open_output_folder)
        self._show_summary_btn.clicked.connect(self._on_show_summary)

    # ── Slot handlers ─────────────────────────────────────────────────────────

    def _on_start_mock(self) -> None:
        self._plot_widget.clear()
        self._controller.start_session(
            mode="mock",
            duration=self._control_panel.duration,
            output_dir=self._control_panel.output_dir,
            no_plots=self._control_panel.no_plots,
        )

    def _on_start_real(self) -> None:
        self._plot_widget.clear()
        self._controller.start_session(
            mode="real",
            device_id=self._control_panel.device_id,
            duration=self._control_panel.duration,
            output_dir=self._control_panel.output_dir,
            no_plots=self._control_panel.no_plots,
        )

    def _on_session_started(self, session_id: str) -> None:
        self._control_panel.set_recording(True)
        self._metrics_panel.on_session_started()
        self._action_bar.hide()

    def _on_session_finished(self, summary: SessionSummary) -> None:
        self._control_panel.set_recording(False)
        self._metrics_panel.on_session_finished()
        self._action_bar.show()

    def _on_error(self, message: str) -> None:
        self._control_panel.set_recording(False)
        self._metrics_panel.on_idle()
        QMessageBox.critical(self, "Session Error", message)

    def _on_save_plots(self) -> None:
        paths = self._controller.save_plots()
        if paths:
            lines = "\n".join(f"  {name}: {path}" for name, path in paths.items())
            QMessageBox.information(self, "Charts Saved", f"Saved to:\n{lines}")
        else:
            QMessageBox.warning(self, "No Data", "No records to export.")

    def _on_show_summary(self) -> None:
        summary = self._controller.last_summary
        if summary is None:
            return
        _SummaryDialog(summary, parent=self).exec()


# ---------------------------------------------------------------------------
# Session summary dialog
# ---------------------------------------------------------------------------

class _SummaryDialog(QDialog):
    """Read-only dialog displaying aggregated session statistics."""

    def __init__(self, summary: SessionSummary, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Session Summary")
        self.setMinimumSize(440, 300)
        self.resize(460, 340)

        layout = QVBoxLayout(self)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setFontFamily("Courier New")
        text.setPlainText(self._format(summary))
        layout.addWidget(text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    @staticmethod
    def _format(s: SessionSummary) -> str:
        fmt = "%Y-%m-%d %H:%M:%S"
        start_str = datetime.datetime.fromtimestamp(s.start_time).strftime(fmt)
        end_str   = datetime.datetime.fromtimestamp(s.end_time).strftime(fmt)
        return (
            f"Session ID         {s.session_id}\n"
            f"Mode               {s.mode}\n"
            f"Start              {start_str}\n"
            f"End                {end_str}\n"
            f"Duration           {s.duration_seconds:.1f} s\n"
            f"Records collected  {s.record_count}\n"
            f"\n"
            f"Mean Concentration {s.mean_concentration:.4f}\n"
            f"Mean Relaxation    {s.mean_relaxation:.4f}\n"
            f"Mean Fatigue       {s.mean_fatigue:.4f}\n"
            f"Artifact ratio     {s.artifact_ratio * 100:.1f}%\n"
            f"\n"
            f"CSV output         {s.raw_csv_path}\n"
        )
