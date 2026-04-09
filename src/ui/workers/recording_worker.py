"""Background QThread that drives a data source and emits records to the UI.

The data source (MockSource or CapsuleDLLSource) runs its own internal
threading.Thread.  RecordingWorker's job is to:

1. Call ``source.start(on_data=self._on_record)`` — this starts the source's
   internal thread and returns immediately.
2. Wait (in its own QThread.run() loop) until the configured duration has
   elapsed or ``request_stop()`` is called.
3. Call ``source.stop()``, which joins the source thread cleanly.
4. Emit ``finished_recording`` so the main thread can finalise the session.

Because ``_on_record`` is called from the source's internal thread
(a plain threading.Thread), the ``record_received`` signal is emitted
cross-thread.  PySide6 automatically uses a queued connection for
cross-thread signal delivery, so the connected slots run in the main
thread's event loop.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

from src.models import EEGRecord

if TYPE_CHECKING:
    pass


class RecordingWorker(QThread):
    """Manages the full recording lifecycle in a background thread.

    Signals
    -------
    record_received : Signal(object)
        Emitted for every :class:`~src.models.EEGRecord` received from the
        source.  Delivered to the main thread via a queued connection.
    error_occurred : Signal(str)
        Emitted if the source raises an exception during ``start()``.
    finished_recording : Signal()
        Emitted after ``source.stop()`` completes — session can be finalised.
    """

    record_received: Signal = Signal(object)   # EEGRecord
    error_occurred: Signal = Signal(str)
    finished_recording: Signal = Signal()

    def __init__(self, source, duration: float = 0.0, parent=None) -> None:
        """
        Parameters
        ----------
        source:
            A MockSource or CapsuleDLLSource instance.
        duration:
            Session length in seconds.  ``0`` means run until
            ``request_stop()`` is called.
        """
        super().__init__(parent)
        self._source = source
        self._duration = duration
        self._stop_event = threading.Event()

    # ── Public ────────────────────────────────────────────────────────────────

    def request_stop(self) -> None:
        """Signal the worker to stop at the next opportunity."""
        self._stop_event.set()

    # ── QThread interface ─────────────────────────────────────────────────────

    def run(self) -> None:  # noqa: D102
        try:
            self._source.start(on_data=self._on_record)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(str(exc))
            return

        start = time.monotonic()
        while not self._stop_event.is_set():
            if self._duration > 0.0 and time.monotonic() - start >= self._duration:
                break
            time.sleep(0.05)

        self._source.stop()
        self.finished_recording.emit()

    # ── Private ───────────────────────────────────────────────────────────────

    def _on_record(self, record: EEGRecord) -> None:
        """Called from the source's internal thread; emits signal cross-thread."""
        self.record_received.emit(record)
