"""Matplotlib-based visualisation for EEG session data."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # non-interactive backend (works without a display)

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from src.models import EEGRecord
from src.utils import moving_average

logger = logging.getLogger(__name__)

# How many seconds per tick on the x-axis
_X_TICK_INTERVAL_SECONDS = 60

# Moving-average window in number of samples
_MA_WINDOW = 10


def render(records: list[EEGRecord], plots_dir: Path) -> dict[str, Path]:
    """Generate all charts and return a mapping of {chart_name: file_path}.

    Creates four files:
    - ``concentration_vs_time.png``
    - ``relaxation_vs_time.png``
    - ``fatigue_vs_time.png``
    - ``combined_metrics.png``
    """
    plots_dir.mkdir(parents=True, exist_ok=True)

    if not records:
        logger.warning("No records to plot — skipping visualisation.")
        return {}

    paths: dict[str, Path] = {}

    paths["concentration"] = _plot_single(
        records=records,
        metric="concentration",
        title="Concentration over Time",
        color="#2196F3",
        output_path=plots_dir / "concentration_vs_time.png",
    )
    paths["relaxation"] = _plot_single(
        records=records,
        metric="relaxation",
        title="Relaxation over Time",
        color="#4CAF50",
        output_path=plots_dir / "relaxation_vs_time.png",
    )
    paths["fatigue"] = _plot_single(
        records=records,
        metric="fatigue",
        title="Fatigue over Time",
        color="#F44336",
        output_path=plots_dir / "fatigue_vs_time.png",
    )
    paths["combined"] = _plot_combined(
        records=records,
        output_path=plots_dir / "combined_metrics.png",
    )

    for name, path in paths.items():
        logger.info("Saved plot %s → %s", name, path)

    return paths


# ---------------------------------------------------------------------------
# Individual metric chart
# ---------------------------------------------------------------------------

def _plot_single(
    *,
    records: list[EEGRecord],
    metric: str,
    title: str,
    color: str,
    output_path: Path,
) -> Path:
    times, values, artifacts = _extract(records, metric)
    t0 = times[0]
    rel_times = [t - t0 for t in times]
    ma = moving_average(values, _MA_WINDOW)

    fig, ax = plt.subplots(figsize=(12, 4))

    # Raw trace
    ax.plot(rel_times, values, color=color, alpha=0.35, linewidth=0.8, label="Raw")
    # Moving average
    ax.plot(rel_times, ma, color=color, linewidth=1.8, label=f"MA({_MA_WINDOW})")
    # Artifact markers
    art_times = [rel_times[i] for i, a in enumerate(artifacts) if a]
    art_vals  = [values[i]    for i, a in enumerate(artifacts) if a]
    if art_times:
        ax.scatter(art_times, art_vals, color="#FF9800", s=20, zorder=5,
                   label="Artifact", marker="x")

    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Score [0–1]")
    ax.set_ylim(-0.05, 1.05)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(_X_TICK_INTERVAL_SECONDS))
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(loc="upper right", fontsize=9)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


# ---------------------------------------------------------------------------
# Combined chart (all three metrics on one figure)
# ---------------------------------------------------------------------------

def _plot_combined(
    *,
    records: list[EEGRecord],
    output_path: Path,
) -> Path:
    t0 = records[0].timestamp
    rel_times = [r.timestamp - t0 for r in records]

    metrics = [
        ("concentration", "Concentration", "#2196F3"),
        ("relaxation",    "Relaxation",    "#4CAF50"),
        ("fatigue",       "Fatigue",       "#F44336"),
    ]

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    fig.suptitle("EEG Session — All Metrics", fontsize=14, fontweight="bold")

    for ax, (attr, label, color) in zip(axes, metrics):
        values = [getattr(r, attr) for r in records]
        artifacts = [r.artifact for r in records]
        ma = moving_average(values, _MA_WINDOW)

        ax.plot(rel_times, values, color=color, alpha=0.35, linewidth=0.8)
        ax.plot(rel_times, ma, color=color, linewidth=1.8, label=label)

        art_times = [rel_times[i] for i, a in enumerate(artifacts) if a]
        art_vals  = [values[i]    for i, a in enumerate(artifacts) if a]
        if art_times:
            ax.scatter(art_times, art_vals, color="#FF9800", s=15, zorder=5, marker="x")

        ax.set_ylabel(label, fontsize=10)
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.legend(loc="upper right", fontsize=9)

    axes[-1].set_xlabel("Time (s)")
    axes[-1].xaxis.set_major_locator(ticker.MultipleLocator(_X_TICK_INTERVAL_SECONDS))

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract(
    records: list[EEGRecord], metric: str
) -> tuple[list[float], list[float], list[bool]]:
    times     = [r.timestamp for r in records]
    values    = [float(getattr(r, metric)) for r in records]
    artifacts = [r.artifact for r in records]
    return times, values, artifacts
