"""Desktop application entry point.

Run the GUI with::

    python src/ui/app.py

or (from any directory) with the project root on PYTHONPATH::

    python -m src.ui.app

The PYQTGRAPH_QT_LIB environment variable is set to ``PySide6`` before
any Qt import so that pyqtgraph uses the correct binding automatically.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Tell pyqtgraph which Qt binding to use before it is imported anywhere else.
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")

# Ensure the project root (parent of src/) is on sys.path so that
# ``from src.xxx import ...`` works when this script is run directly.
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from PySide6.QtWidgets import QApplication  # noqa: E402  (import after path fix)

from src.ui.main_window import MainWindow   # noqa: E402


def run() -> int:
    """Create the QApplication, show the main window, and enter the event loop."""
    app = QApplication(sys.argv)
    app.setApplicationName("ReReTracker")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Neiry")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
