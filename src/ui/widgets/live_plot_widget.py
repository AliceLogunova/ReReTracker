"""Live interactive chart widget using pyqtgraph.

Three stacked PlotWidgets — one each for concentration, relaxation, and
fatigue — update in real time as EEGRecords arrive.

Interactive features
--------------------
- Raw trace (semi-transparent) + 10-sample moving average on every chart.
- Orange × markers on samples flagged as artifacts.
- Crosshair (dashed vertical + horizontal lines) follows the mouse.
- Tooltip text item showing timestamp, metric name, value, and artifact flag
  for the data point nearest the cursor.

The moving-average helper is reused directly from ``src.utils`` — no new
smoothing logic here.
"""

from __future__ import annotations

import datetime
from typing import Optional

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.models import EEGRecord
from src.utils import moving_average

# (attribute on EEGRecord,  display label,  hex colour)
_METRICS: list[tuple[str, str, str]] = [
    ("concentration", "Concentration", "#2196F3"),
    ("relaxation",    "Relaxation",    "#4CAF50"),
    ("fatigue",       "Fatigue",       "#F44336"),
]

_MA_WINDOW = 10          # samples — matches the MVP visualiser constant
_CROSSHAIR_PEN = dict(color="#888888", width=1, style=Qt.PenStyle.DashLine)


class LivePlotWidget(QWidget):
    """Three stacked pyqtgraph charts that update live as records arrive."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        pg.setConfigOptions(antialias=True, foreground="k", background="w")

        # Raw data buffers — parallel lists, index-aligned
        self._timestamps: list[float] = []
        self._artifacts: list[bool] = []
        self._values: dict[str, list[float]] = {m[0]: [] for m in _METRICS}

        # Per-metric pyqtgraph items
        self._raw_curves: dict[str, pg.PlotDataItem] = {}
        self._ma_curves: dict[str, pg.PlotDataItem] = {}
        self._scatter_items: dict[str, pg.ScatterPlotItem] = {}
        self._vlines: dict[str, pg.InfiniteLine] = {}
        self._hlines: dict[str, pg.InfiniteLine] = {}
        self._tooltips: dict[str, pg.TextItem] = {}
        # Keep strong references to SignalProxy objects so they are not GC'd
        self._proxies: list[pg.SignalProxy] = []

        self._build_ui()

    # ── Public interface ──────────────────────────────────────────────────────

    def add_record(self, record: EEGRecord) -> None:
        """Append *record* to the internal buffers and refresh all charts."""
        self._timestamps.append(record.timestamp)
        self._artifacts.append(record.artifact)
        for attr, _, _ in _METRICS:
            self._values[attr].append(getattr(record, attr))
        self._redraw()

    def clear(self) -> None:
        """Clear all data buffers and reset the charts to an empty state."""
        self._timestamps.clear()
        self._artifacts.clear()
        for attr in self._values:
            self._values[attr].clear()
        for attr, _, _ in _METRICS:
            self._raw_curves[attr].setData([], [])
            self._ma_curves[attr].setData([], [])
            self._scatter_items[attr].setData(x=[], y=[])

    # ── Private ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(4, 4, 4, 4)

        for attr, label, color in _METRICS:
            pw = pg.PlotWidget()
            pw.setTitle(f"<b>{label}</b>", size="10pt")
            pw.setYRange(-0.05, 1.05)
            pw.showGrid(x=True, y=True, alpha=0.25)
            pw.setLabel("left",   "Score [0–1]", size="8pt")
            pw.setLabel("bottom", "Time (s)",    size="8pt")
            pw.setMinimumHeight(160)

            legend = pw.addLegend(offset=(8, 8), labelTextSize="8pt")

            # Raw trace (light / semi-transparent)
            raw_pen = pg.mkPen(color=color, width=1)
            raw_curve = pw.plot(pen=raw_pen, name="Raw")

            # Moving average (solid, thicker)
            ma_pen = pg.mkPen(color=color, width=2)
            ma_curve = pw.plot(pen=ma_pen, name=f"MA({_MA_WINDOW})")

            # Artifact markers (orange ×)
            scatter = pg.ScatterPlotItem(
                size=10,
                pen=pg.mkPen("#FF9800", width=2),
                brush=pg.mkBrush(None),
                symbol="x",
                name="Artifact",
            )
            pw.addItem(scatter)

            # Crosshair lines
            vline = pg.InfiniteLine(angle=90,  movable=False, pen=pg.mkPen(**_CROSSHAIR_PEN))
            hline = pg.InfiniteLine(angle=0,   movable=False, pen=pg.mkPen(**_CROSSHAIR_PEN))
            pw.addItem(vline, ignoreBounds=True)
            pw.addItem(hline, ignoreBounds=True)

            # Tooltip text box (hidden until mouse enters)
            tooltip = pg.TextItem(
                anchor=(0.0, 1.0),
                border=pg.mkPen("#cccccc"),
                fill=pg.mkBrush(255, 255, 255, 210),
            )
            tooltip.setZValue(10)
            tooltip.hide()
            pw.addItem(tooltip, ignoreBounds=True)

            # Mouse-tracking proxy (rate-limited to 30 fps)
            proxy = pg.SignalProxy(
                pw.scene().sigMouseMoved,
                rateLimit=30,
                slot=lambda evt, _pw=pw, _attr=attr: self._on_mouse_moved(evt, _pw, _attr),
            )
            self._proxies.append(proxy)  # keep alive

            # Store references
            self._raw_curves[attr]    = raw_curve
            self._ma_curves[attr]     = ma_curve
            self._scatter_items[attr] = scatter
            self._vlines[attr]        = vline
            self._hlines[attr]        = hline
            self._tooltips[attr]      = tooltip

            layout.addWidget(pw)

    def _redraw(self) -> None:
        if not self._timestamps:
            return

        t0 = self._timestamps[0]
        rel_times = [t - t0 for t in self._timestamps]

        for attr, _, _ in _METRICS:
            vals = self._values[attr]

            self._raw_curves[attr].setData(rel_times, vals)

            ma = moving_average(vals, _MA_WINDOW)
            self._ma_curves[attr].setData(rel_times, ma)

            art_x = [rel_times[i] for i, a in enumerate(self._artifacts) if a]
            art_y = [vals[i]      for i, a in enumerate(self._artifacts) if a]
            self._scatter_items[attr].setData(x=art_x, y=art_y)

    def _on_mouse_moved(
        self, evt: tuple, pw: pg.PlotWidget, attr: str
    ) -> None:
        """Update crosshair and tooltip for *attr*'s chart on mouse move."""
        pos = evt[0]
        scene_rect = pw.sceneBoundingRect()

        if not scene_rect.contains(pos):
            self._tooltips[attr].hide()
            return

        mouse_pt = pw.getPlotItem().vb.mapSceneToView(pos)
        x = mouse_pt.x()
        y = mouse_pt.y()

        self._vlines[attr].setPos(x)
        self._hlines[attr].setPos(y)

        if not self._timestamps:
            self._tooltips[attr].hide()
            return

        # Find the data point whose x-coordinate is nearest to the cursor
        t0 = self._timestamps[0]
        rel_times = [t - t0 for t in self._timestamps]
        dists = [abs(rt - x) for rt in rel_times]
        idx = dists.index(min(dists))

        nearest_val  = self._values[attr][idx]
        nearest_rt   = rel_times[idx]
        nearest_ts   = self._timestamps[idx]
        is_artifact  = self._artifacts[idx]

        dt_str   = datetime.datetime.fromtimestamp(nearest_ts).strftime("%H:%M:%S")
        art_str  = "  [ARTIFACT]" if is_artifact else ""
        tip_text = (
            f"t = {nearest_rt:.1f} s  ({dt_str})\n"
            f"{attr} = {nearest_val:.3f}{art_str}"
        )

        tooltip = self._tooltips[attr]
        tooltip.setText(tip_text)
        tooltip.setPos(x, y)
        tooltip.show()
