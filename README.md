# ReReTracker — EEG Brain Activity Tracker

> Real-time collection and visualization of EEG-based concentration, relaxation, and fatigue metrics via the Neiry CapsuleAPI SDK.

---

## Table of Contents

- [ReReTracker — EEG Brain Activity Tracker](#reretracker--eeg-brain-activity-tracker)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Features](#features)
  - [Architecture](#architecture)
  - [Project Structure](#project-structure)
  - [Requirements](#requirements)
  - [Installation](#installation)
  - [CapsuleAPI Setup](#capsuleapi-setup)
  - [Running the Desktop UI](#running-the-desktop-ui)
    - [UI walkthrough](#ui-walkthrough)
    - [Equivalent CLI operations from the UI](#equivalent-cli-operations-from-the-ui)
  - [Running the CLI](#running-the-cli)
  - [Running Tests](#running-tests)
  - [Data Output](#data-output)
    - [CSV format](#csv-format)
    - [JSON summary format](#json-summary-format)
  - [CLI Reference](#cli-reference)

---

## Overview

ReReTracker connects to a Neiry EEG headset through the CapsuleAPI C SDK (loaded via `ctypes`) and streams three neurofeedback productivity metrics in real time:

| Metric | Description |
|---|---|
| **Concentration** | Cognitive focus score `[0.0 – 1.0]` |
| **Relaxation** | Mental calm score `[0.0 – 1.0]` |
| **Fatigue** | Accumulated tiredness score `[0.0 – 1.0]` |

A **Mock mode** is included that generates realistic sine-wave synthetic data so the full application can be run and tested without any hardware.

---

## Features

- **Desktop GUI** (PySide6) with live interactive charts
- **Mock mode** — no EEG hardware needed for development or demos
- **Real device mode** — auto-discovery or explicit Bluetooth MAC address
- **Live charts** — three pyqtgraph plots updating in real time with moving average, artifact markers, and interactive hover tooltips
- **Background recording** — the UI never freezes; all SDK and I/O work runs in worker threads
- **Automatic export** — raw CSV + JSON session summary written after every session
- **PNG chart export** — concentration, relaxation, fatigue, and combined charts saved to disk
- **CLI interface** — fully functional headless operation without the GUI

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Desktop UI  (PySide6)                    │
│  MainWindow                                                     │
│  ├── ControlPanel    mode / device / duration / start / stop   │
│  ├── MetricsPanel    live values, elapsed time, artifact flag  │
│  └── LivePlotWidget  3 × pyqtgraph charts with tooltips        │
│                                                                 │
│  SessionController   orchestrates backend from the UI thread   │
│  RecordingWorker     QThread — drives source, emits signals    │
└───────────────────────────────┬─────────────────────────────────┘
                                │  calls existing MVP modules
┌───────────────────────────────▼─────────────────────────────────┐
│                          MVP Backend                            │
│  MockSource / CapsuleDLLSource   data acquisition              │
│  DataCollector                   thread-safe buffer + CSV I/O  │
│  visualizer.render()             matplotlib PNG export         │
│  EEGRecord / SessionSummary      data models                   │
└─────────────────────────────────────────────────────────────────┘
```

**Key design rules:**
- The GUI is a thin orchestration layer — no business logic lives in widgets.
- All SDK interaction stays in `src/core/capsule_client.py`.
- All collection / CSV / JSON logic stays in `src/core/data_collector.py`.
- All chart export logic stays in `src/visualization/visualizer.py`.
- Long-running operations (recording, SDK calls) run in `RecordingWorker` so the UI thread is never blocked.

---

## Project Structure

```
ReReTracker/
│
├── src/
│   ├── main.py                        CLI entry point
│   ├── config.py                      AppConfig dataclass (paths, SDK params)
│   ├── models.py                      EEGRecord, SessionSummary, CSV helpers
│   ├── utils.py                       session_id(), moving_average(), etc.
│   │
│   ├── core/
│   │   ├── capsule_client.py          CapsuleDLLSource + MockSource
│   │   └── data_collector.py          Thread-safe buffer, CSV flush, JSON summary
│   │
│   ├── visualization/
│   │   └── visualizer.py             matplotlib PNG charts (Agg backend)
│   │
│   └── ui/                            Desktop GUI (PySide6)
│       ├── app.py                     QApplication entry point
│       ├── main_window.py             Top-level QMainWindow
│       ├── controllers/
│       │   └── session_controller.py  Session lifecycle bridge
│       ├── workers/
│       │   └── recording_worker.py    QThread background recorder
│       └── widgets/
│           ├── control_panel.py       Mode / device / duration / buttons
│           ├── metrics_panel.py       Live values + elapsed timer
│           └── live_plot_widget.py    pyqtgraph interactive charts
│
├── tests/
│   ├── conftest.py
│   ├── test_capsule_client.py
│   ├── test_data_collector.py
│   └── test_visualizer.py
│
├── CapsuleAPI/
│   ├── bin/
│   │   └── CapsuleClient.dll          Neiry SDK runtime (required for real mode)
│   ├── Include/                       C headers
│   └── Lib/                           Import library
│
├── data/
│   ├── raw/                           session_YYYYMMDD_HHMMSS.csv
│   ├── processed/                     session_YYYYMMDD_HHMMSS_summary.json
│   └── plots/                         concentration_vs_time.png, etc.
│
├── requirements.txt
└── README.md
```

---

## Requirements

| Dependency | Purpose |
|---|---|
| Python 3.11+ | Runtime |
| PySide6 | Desktop GUI framework |
| pyqtgraph | Live interactive charts |
| matplotlib | Static PNG chart export |
| pandas | Data handling |
| plotly | (optional) additional visualisation |
| pytest | Test runner |

---

## Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd ReReTracker

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## CapsuleAPI Setup

Real-device mode requires the Neiry CapsuleAPI SDK runtime:

1. Obtain the CapsuleAPI distribution from Neiry.
2. Place `CapsuleClient.dll` at:
   ```
   CapsuleAPI/bin/CapsuleClient.dll
   ```
3. C headers (for reference) go in `CapsuleAPI/Include/`.

> **Mock mode does not need the DLL** — you can run the full application, record synthetic data, and export charts without any hardware or SDK files.

---

## Running the Desktop UI

```bash
python src/ui/app.py
```

### UI walkthrough

| Zone | Description |
|---|---|
| **Session Parameters** | Set device type, optional MAC address, duration (0 = unlimited), output directory, and whether to suppress plot export |
| **Session Control** | **Start Mock Session** — synthetic data; **Start Real Session** — live EEG device; **Stop Recording** — graceful stop at any time |
| **Live Metrics** | Current concentration / relaxation / fatigue values, recording status, elapsed time, and artifact indicator |
| **Live Charts** | Three interactive pyqtgraph plots updating in real time. Hover over any chart to see a tooltip with timestamp, metric value, and artifact flag |
| **Post-Session Actions** | Appear after a session ends: **Save Charts as PNG**, **Open Output Folder**, **Show Session Summary** |

### Equivalent CLI operations from the UI

| Button | Equivalent CLI command |
|---|---|
| Start Mock Session (60 s) | `python src/main.py --mode mock --duration 60` |
| Start Real Session (auto-discover) | `python src/main.py --mode real` |
| Start Real Session + MAC + custom output | `python src/main.py --mode real --device AA:BB:CC:DD:EE:FF --output /path/to/dir` |

---

## Running the CLI

The CLI exposes the same backend functionality without the GUI:

```bash
# Mock mode — 60 seconds, no hardware needed
python src/main.py --mode mock --duration 60

# Real device — auto-discover the first available Neiry headset
python src/main.py --mode real

# Real device — explicit MAC address, custom output dir, skip plot generation
python src/main.py --mode real --device AA:BB:CC:DD:EE:FF --output /tmp/eeg --no-plots

# Unlimited session — runs until Ctrl-C
python src/main.py --mode mock

# Verbose logging
python src/main.py --mode mock --duration 30 --log-level DEBUG
```

---

## Running Tests

```bash
# Run all 25 tests
pytest

# Verbose output
pytest -v

# Run a specific test file
pytest tests/test_capsule_client.py
```

All tests use `MockSource` — no DLL or hardware is required.

---

## Data Output

After each session the following files are written automatically:

```
data/
├── raw/
│   └── session_20260410_143022.csv          # timestamped EEG records
├── processed/
│   └── session_20260410_143022_summary.json # aggregated statistics
└── plots/
    ├── concentration_vs_time.png
    ├── relaxation_vs_time.png
    ├── fatigue_vs_time.png
    └── combined_metrics.png
```

### CSV format

```
timestamp,concentration,relaxation,fatigue,artifact
1712750422.31,0.723,0.541,0.189,0
1712750422.81,0.738,0.529,0.201,0
...
```

### JSON summary format

```json
{
  "session_id": "session_20260410_143022",
  "mode": "mock",
  "start_time": 1712750422.0,
  "end_time": 1712750482.0,
  "duration_seconds": 60.0,
  "record_count": 120,
  "mean_concentration": 0.714,
  "mean_relaxation": 0.523,
  "mean_fatigue": 0.201,
  "artifact_ratio": 0.017,
  "raw_csv_path": "data/raw/session_20260410_143022.csv"
}
```

---

## CLI Reference

```
usage: reretracker [-h] [--mode {real,mock}] [--duration SECONDS]
                   [--device DEVICE_ID] [--output DIR] [--no-plots]
                   [--log-level {DEBUG,INFO,WARNING,ERROR}]

EEG brain activity tracker — collects concentration, relaxation, fatigue.

options:
  --mode {real,mock}    Data source. 'real' uses CapsuleAPI DLL; 'mock'
                        generates synthetic data. Default: mock
  --duration SECONDS    Session duration in seconds. 0 = run until Ctrl-C.
                        Default: 0
  --device DEVICE_ID    Bluetooth MAC address of the target Neiry device.
                        If omitted, the first discovered device is used.
  --output DIR          Override the data output directory.
  --no-plots            Skip generating matplotlib charts after the session.
  --log-level LEVEL     Logging verbosity. Default: INFO
```
