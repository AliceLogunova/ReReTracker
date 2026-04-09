"""Application configuration — paths, DLL location, tunable parameters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Project root is two levels above this file (src/config.py → src/ → project root)
_PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class AppConfig:
    # ── SDK ──────────────────────────────────────────────────────────────────
    dll_path: Path = field(
        default_factory=lambda: _PROJECT_ROOT / "CapsuleAPI" / "bin" / "CapsuleClient.dll"
    )
    capsule_address: str = "tcp://127.0.0.1:5666"
    app_name: str = "ReReTracker"
    app_version: str = "1.0.0"

    # ── NFB Metrics Productivity creation parameters ─────────────────────────
    # speed / maxSpeed / slowDown control how fast the classifier adapts
    nfb_speed: float = 0.2
    nfb_max_speed: float = 0.5
    nfb_slow_down: float = 0.8

    # ── Device discovery ─────────────────────────────────────────────────────
    device_search_seconds: int = 5

    # ── Update loop ──────────────────────────────────────────────────────────
    # How often clCClient_Update() is called (milliseconds)
    update_interval_ms: int = 50

    # ── Data directories ─────────────────────────────────────────────────────
    data_dir: Path = field(default_factory=lambda: _PROJECT_ROOT / "data")

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def plots_dir(self) -> Path:
        return self.data_dir / "plots"

    # ── Mock source ──────────────────────────────────────────────────────────
    # Emit rate for the pure-Python mock data source (Hz)
    mock_emit_hz: float = 2.0

    def ensure_dirs(self) -> None:
        """Create all output directories if they don't exist."""
        for d in (self.raw_dir, self.processed_dir, self.plots_dir):
            d.mkdir(parents=True, exist_ok=True)


# Shared default instance — import and use directly, or override per-run.
DEFAULT_CONFIG = AppConfig()
