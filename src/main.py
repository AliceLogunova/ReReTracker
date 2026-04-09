"""ReReTracker — EEG brain activity tracker.

Usage examples::

    # Run in mock mode for 60 seconds (no hardware required)
    python src/main.py --mode mock --duration 60


    # Run with a real Neiry device (auto-discover)
    python src/main.py --mode real

    # Run with a specific device and custom output directory
    python src/main.py --mode real --device AA:BB:CC:DD:EE:FF --output /tmp/eeg_data

    # Skip plot generation
    python src/main.py --mode mock --duration 30 --no-plots
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root (parent of src/) is on sys.path when this file is
# run directly as  `python src/main.py`.
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from src.config import AppConfig
from src.core.capsule_client import CapsuleDLLSource, MockSource
from src.core.data_collector import DataCollector
from src.visualization import visualizer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reretracker",
        description="EEG brain activity tracker — collects concentration, relaxation, fatigue.",
    )
    parser.add_argument(
        "--mode",
        choices=["real", "mock"],
        default="mock",
        help="Data source: 'real' uses CapsuleAPI DLL; 'mock' generates synthetic data. "
             "Default: mock",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help="Session duration in seconds. 0 = run until Ctrl-C. Default: 0",
    )
    parser.add_argument(
        "--device",
        default=None,
        metavar="DEVICE_ID",
        help="Bluetooth MAC address of the target Neiry device. "
             "If omitted, the first discovered device is used (real mode only).",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="DIR",
        help="Override the data output directory (default: <project>/data).",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip generating matplotlib charts after the session.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity. Default: INFO",
    )
    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Build config, optionally overriding the data directory
    config = AppConfig()
    if args.output:
        config.data_dir = Path(args.output)

    config.ensure_dirs()

    print(f"[ReReTracker] Mode: {args.mode}")
    if args.duration > 0:
        print(f"[ReReTracker] Duration: {args.duration:.0f} s")
    else:
        print("[ReReTracker] Duration: unlimited (press Ctrl-C to stop)")

    # Build data source
    if args.mode == "real":
        if not config.dll_path.exists():
            print(
                f"[ERROR] DLL not found at {config.dll_path}\n"
                "        Make sure CapsuleAPI/bin/CapsuleClient.dll is present.",
                file=sys.stderr,
            )
            return 1
        source = CapsuleDLLSource(config, device_id=args.device)
    else:
        source = MockSource(config)

    collector = DataCollector(config, mode=args.mode)
    sid = collector.begin_session()
    print(f"[ReReTracker] Session ID: {sid}")

    # Graceful shutdown on Ctrl-C
    stop_event = _StopEvent()
    signal.signal(signal.SIGINT, stop_event.trigger)
    signal.signal(signal.SIGTERM, stop_event.trigger)

    # Start data source
    try:
        source.start(on_data=collector.add_record)
    except Exception as exc:
        logger.error("Failed to start data source: %s", exc)
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print("[ReReTracker] Recording... (Ctrl-C to stop)")

    # Wait loop
    start = time.monotonic()
    try:
        while not stop_event.is_set():
            elapsed = time.monotonic() - start
            if args.duration > 0 and elapsed >= args.duration:
                break
            _print_status(collector, elapsed)
            time.sleep(1.0)
    finally:
        source.stop()

    # Finalise
    summary = collector.end_session()
    print(
        f"\n[ReReTracker] Session complete.\n"
        f"  Records : {summary.record_count}\n"
        f"  Duration: {summary.duration_seconds:.1f} s\n"
        f"  Conc    : {summary.mean_concentration:.3f}\n"
        f"  Relax   : {summary.mean_relaxation:.3f}\n"
        f"  Fatigue : {summary.mean_fatigue:.3f}\n"
        f"  Artifacts: {summary.artifact_ratio * 100:.1f}%\n"
        f"  CSV     : {summary.raw_csv_path}"
    )

    if not args.no_plots and summary.record_count > 0:
        print("[ReReTracker] Generating plots...")
        paths = visualizer.render(collector.records, config.plots_dir)
        for name, path in paths.items():
            print(f"  [{name}] -> {path}")
    elif summary.record_count == 0:
        print("[ReReTracker] No records collected — skipping plots.")

    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _StopEvent:
    """Thin wrapper so signal handlers can set a stop flag."""

    def __init__(self) -> None:
        self._flag = False

    def trigger(self, *_) -> None:
        print("\n[ReReTracker] Stop requested.")
        self._flag = True

    def is_set(self) -> bool:
        return self._flag


def _print_status(collector: DataCollector, elapsed: float) -> None:
    records = collector.records
    n = len(records)
    if n == 0:
        print(f"\r  Elapsed {elapsed:6.0f}s | waiting for data...", end="", flush=True)
        return
    last = records[-1]
    print(
        f"\r  Elapsed {elapsed:6.0f}s | n={n:5d} | "
        f"conc={last.concentration:.2f} relax={last.relaxation:.2f} "
        f"fatigue={last.fatigue:.2f}",
        end="",
        flush=True,
    )


if __name__ == "__main__":
    sys.exit(main())
