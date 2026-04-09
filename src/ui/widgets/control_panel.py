"""Session control panel widget.

Exposes:
- Device type selector (Neiry Any — SDK constant clC_DT_NeiryAny = 4)
- Optional device ID / MAC address field
- Duration field (seconds; 0 = unlimited)
- Output directory selector with file browser
- "Disable plot export" checkbox
- Start Mock Session / Start Real Session / Stop Recording buttons
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# SDK device-type constants exposed in the selector.
# The value is the clC_DT_* integer used by CapsuleDLLSource internally.
_DEVICE_TYPES: list[tuple[str, int]] = [
    ("Neiry (Any)", 4),
]


class ControlPanel(QWidget):
    """Form-based session configuration and start/stop controls."""

    start_mock_requested: Signal = Signal()
    start_real_requested: Signal = Signal()
    stop_requested: Signal = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._wire_signals()
        self._set_recording(False)

    # ── Public accessors (read by MainWindow before starting a session) ───────

    @property
    def device_id(self) -> Optional[str]:
        """MAC address entered by the user, or *None* for auto-discover."""
        text = self._device_id_edit.text().strip()
        return text if text else None

    @property
    def duration(self) -> float:
        """Session duration in seconds; ``0`` means unlimited."""
        return float(self._duration_spin.value())

    @property
    def output_dir(self) -> Optional[str]:
        """Custom output directory path, or *None* to use the default."""
        text = self._output_edit.text().strip()
        return text if text else None

    @property
    def no_plots(self) -> bool:
        """*True* when the user wants to suppress automatic plot generation."""
        return self._no_plots_check.isChecked()

    # ── State helpers ─────────────────────────────────────────────────────────

    def set_recording(self, recording: bool) -> None:
        """Enable or disable controls depending on whether a session is active."""
        self._set_recording(recording)

    # ── Private ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ── Session parameters ────────────────────────────────────────────────
        params_group = QGroupBox("Session Parameters")
        form = QFormLayout(params_group)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setContentsMargins(8, 12, 8, 8)
        form.setSpacing(8)

        self._device_type_combo = QComboBox()
        for label, _ in _DEVICE_TYPES:
            self._device_type_combo.addItem(label)
        form.addRow("Device type:", self._device_type_combo)

        self._device_id_edit = QLineEdit()
        self._device_id_edit.setPlaceholderText(
            "AA:BB:CC:DD:EE:FF  (blank = auto-discover)"
        )
        form.addRow("Device ID / MAC:", self._device_id_edit)

        self._duration_spin = QSpinBox()
        self._duration_spin.setRange(0, 86400)
        self._duration_spin.setValue(60)
        self._duration_spin.setSuffix(" s")
        self._duration_spin.setSpecialValueText("Unlimited")
        form.addRow("Duration:", self._duration_spin)

        # Output directory row: text field + Browse button
        output_row_widget = QWidget()
        output_row = QHBoxLayout(output_row_widget)
        output_row.setContentsMargins(0, 0, 0, 0)
        output_row.setSpacing(4)
        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("(default: <project>/data)")
        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.setFixedWidth(72)
        output_row.addWidget(self._output_edit)
        output_row.addWidget(self._browse_btn)
        form.addRow("Output directory:", output_row_widget)

        self._no_plots_check = QCheckBox("Disable automatic plot export")
        form.addRow("", self._no_plots_check)

        root.addWidget(params_group)

        # ── Start / Stop buttons ──────────────────────────────────────────────
        ctrl_group = QGroupBox("Session Control")
        ctrl_layout = QVBoxLayout(ctrl_group)
        ctrl_layout.setContentsMargins(8, 12, 8, 8)
        ctrl_layout.setSpacing(6)

        self._start_mock_btn = QPushButton("Start Mock Session")
        self._start_mock_btn.setToolTip(
            "Equivalent to: python src/main.py --mode mock --duration <N>"
        )
        self._start_real_btn = QPushButton("Start Real Session")
        self._start_real_btn.setToolTip(
            "Equivalent to: python src/main.py --mode real [--device MAC]"
        )
        self._stop_btn = QPushButton("Stop Recording")
        self._stop_btn.setEnabled(False)

        ctrl_layout.addWidget(self._start_mock_btn)
        ctrl_layout.addWidget(self._start_real_btn)
        ctrl_layout.addWidget(self._stop_btn)

        root.addWidget(ctrl_group)
        root.addStretch()

    def _wire_signals(self) -> None:
        self._start_mock_btn.clicked.connect(self.start_mock_requested)
        self._start_real_btn.clicked.connect(self.start_real_requested)
        self._stop_btn.clicked.connect(self.stop_requested)
        self._browse_btn.clicked.connect(self._on_browse)

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder:
            self._output_edit.setText(folder)

    def _set_recording(self, recording: bool) -> None:
        self._start_mock_btn.setEnabled(not recording)
        self._start_real_btn.setEnabled(not recording)
        self._stop_btn.setEnabled(recording)
        # Lock configuration fields while recording
        for widget in (
            self._device_id_edit,
            self._device_type_combo,
            self._duration_spin,
            self._output_edit,
            self._browse_btn,
            self._no_plots_check,
        ):
            widget.setEnabled(not recording)
