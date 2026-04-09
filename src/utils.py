"""Shared utility helpers — filenames, formatting, directory setup."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path


def session_id(prefix: str = "session") -> str:
    """Return a timestamped session identifier, e.g. ``session_20240409_153012``."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}"


def raw_csv_path(raw_dir: Path, sid: str) -> Path:
    """Canonical path for a raw CSV file given a session ID."""
    return raw_dir / f"{sid}.csv"


def processed_json_path(processed_dir: Path, sid: str) -> Path:
    """Canonical path for a processed summary JSON file given a session ID."""
    return processed_dir / f"{sid}_summary.json"


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as ``HH:MM:SS``."""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def moving_average(values: list[float], window: int) -> list[float]:
    """Compute a simple moving average over *values* with the given *window* size.

    The first ``window - 1`` elements are averaged over whatever is available
    so the output always has the same length as the input.
    """
    result: list[float] = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        chunk = values[start : i + 1]
        result.append(sum(chunk) / len(chunk))
    return result
