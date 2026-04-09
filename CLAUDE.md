
## 1. Project Description

This project collects EEG-based brain activity metrics (concentration, relaxation, fatigue) using CapsuleAPI (Neiry SDK).

The system connects to a device, initializes a session, trains neurofeedback (NFB), and streams metrics over time.

---

## 2. Docs

Refer to `design_document.md` for:
- architecture
- data flow
- API structure
- system behavior

Refer to `MVP_implementation_1.md` for:
- full list of files created in the first MVP iteration
- key design decisions (DLL wrapper, MockSource, DataCollector, Visualizer)
- CLI usage and test instructions

---

## 3. Technologies Stack

- Python 3.11+
- CapsuleAPI (C SDK via DLL)
- ctypes / cffi
- pandas
- matplotlib / plotly

---

## 4. Project Structure
ReReTracker/
│
├── CLAUDE.md
├── design_document.md
├── README.md
│
├── capsule_api/                      ← сюда распаковать CapsuleAPI
│   ├── Include/                      ← .h заголовки SDK
│   │   ├── CClientAPI.h
│   │   ├── CClient.h
│   │   ├── CDevice.h
│   │   ├── CSession.h
│   │   ├── CNFB.h
│   │   ├── CNFBMetricsProductivity.h
│   │   └── ...
│   │
│   ├── Lib/                          ← .lib файлы SDK
│   │   ├── CapsuleClient.lib
│   │   └── ...
│   │
│   ├── CapsuleClient.dll             ← если найдёшь DLL, положить сюда
│   └── NOTES.md                      ← опционально: описание, где что взято
│
├── src/                              ← сюда Claude Code будет генерировать код
│   ├── main.py                       ← точка входа
│   ├── capsule_client.py             ← Python-обёртка над CapsuleAPI
│   ├── data_collector.py             ← сбор и запись concentration/relaxation
│   ├── visualizer.py                 ← построение графиков
│   ├── models.py                     ← структуры данных / dataclass / pydantic
│   ├── config.py                     ← пути, настройки, интервалы
│   └── utils.py                      ← вспомогательные функции
│
├── data/                             ← сюда сохраняются результаты работы
│   ├── raw/                          ← сырые логи
│   │   ├── session_001.csv
│   │   └── ...
│   │
│   ├── processed/                    ← обработанные данные
│   │   ├── session_001_summary.json
│   │   └── ...
│   │
│   └── plots/                        ← графики
│       ├── concentration_vs_time.png
│       ├── relaxation_vs_time.png
│       └── combined_metrics.png
│
├── tests/
│   ├── test_capsule_client.py
│   ├── test_data_collector.py
│   ├── test_visualizer.py
│   └── conftest.py
│
└── .gitignore

---

## 5. Code Style

- Use PEP8
- Type hints required
- Modular structure
- No hardcoded paths
- Clear separation of logic layers

---

## 6. Tests

- Unit tests for:
  - data processing
  - storage
- Mock CapsuleAPI for testing
- Use pytest

---

## 7. Commands

Run project:
    python src/main.py


Run tests:
    pytest

---

## 8. Version Control
Commit format:
    feat: new feature
    fix: bug fix
    refactor: code improvement
Small commits preferred

---

## 9. .gitignore Rules

The following Claude Code and documentation artifacts must NEVER be committed.
Add them to `.gitignore` (and remove from tracking if already staged):

    # Claude Code internals
    .claude/

    # Claude / AI working documents
    CLAUDE.md
    design_document.md
    MVP_implementation_1.md
    MVP_implementation_*.md

    # Any future implementation notes or AI session files
    *.implementation_notes.md

These files are for local development guidance only and should not appear
in the repository history.

---

## CapsuleAPI Integration

CapsuleAPI is located in:
    capsule_api/

Use DLL from `CapsuleAPI/bin/CapsuleClient.dll`.
Headers are located in `CapsuleAPI/Include/`.

Claude MUST:
    use headers from Include/
    load CapsuleClient.dll
    create Python wrapper over C API
    use event-based callbacks

IMPORTANT:
Do NOT reimplement EEG processing — use SDK outputs:
    concentrationScore
    relaxationScore
    fatigueScore

---

## 10. V1 Desktop UI

V1 of this project must provide a desktop GUI on top of the existing MVP CLI/data pipeline. The UI is a thin orchestration and visualization layer over the already implemented backend modules and CLI-equivalent flows; do not rewrite the core data collection logic, CapsuleAPI integration, or storage logic — reuse the existing sources, collector, models, and visualizer architecture from the MVP. :contentReference[oaicite:0]{index=0} :contentReference[oaicite:1]{index=1}

### UI goal

The desktop application must allow the user to:
- start EEG recording in mock mode
- start EEG recording in real-device mode
- select a specific supported device type / target device
- optionally specify a concrete device identifier / MAC address
- stop an active recording session
- watch concentration / relaxation / fatigue charts update in real time
- save the final charts to PNG after recording ends

### Required desktop actions

The GUI must expose buttons/actions equivalent to these existing CLI flows:
- Mock mode: `python src/main.py --mode mock --duration 60`
- Real device auto-discovery: `python src/main.py --mode real`
- Real device with explicit identifier and custom output, without plots: `python src/main.py --mode real --device AA:BB:CC:DD:EE:FF --output /tmp/eeg --no-plots` :contentReference[oaicite:2]{index=2}

The GUI should not shell out to subprocesses for these actions unless absolutely necessary; instead, call the existing Python modules/services directly and mirror the CLI behavior.

### Desktop framework

Preferred stack for V1 desktop UI:
- Python desktop GUI framework: **PySide6** (preferred) or PyQt6
- Interactive charts: **Plotly embedded in a Qt WebEngine view** or **pyqtgraph** if needed for smoother live updates
- Existing backend remains Python 3.11+ with CapsuleAPI via `ctypes` and the current modular structure :contentReference[oaicite:3]{index=3}

PySide6 is preferred because V1 is explicitly a desktop app and the current project scope already positions the system as Python CLI/Desktop rather than web-first. :contentReference[oaicite:4]{index=4}

### Required UI layout

The main desktop window should include these zones:

1. **Connection / session control panel**
   - mode selector: `mock` / `real`
   - device type selector
   - optional device identifier / MAC text field
   - duration field (seconds)
   - output directory selector
   - checkbox: disable plot export (`no-plots`)
   - button: **Start Mock Session**
   - button: **Start Real Session**
   - button: **Stop Recording**

2. **Supported device selector**
   The UI must expose device-type selection aligned with CapsuleAPI-supported device modes. Reuse the SDK-facing project assumptions and device concepts already present in the project/API docs rather than inventing new device categories. The user must be able to choose among supported device targets and optionally use auto-discovery or a concrete device ID/MAC. :contentReference[oaicite:5]{index=5}

3. **Real-time metrics area**
   - current concentration value
   - current relaxation value
   - current fatigue value
   - recording status
   - elapsed time
   - device connection state
   - optional artifact indicator

4. **Interactive charts area**
   - live concentration chart
   - live relaxation chart
   - live fatigue chart
   - combined chart view is optional in live mode but required for final export

5. **Post-session actions**
   - save charts as PNG
   - open output folder
   - show session summary

### Real-time chart requirements

Charts must be **interactive** and update while recording is running. At minimum, hovering over the chart must show a tooltip with:
- timestamp
- metric name
- metric value
- artifact flag if available

The live charts must render concentration, relaxation, and fatigue over time, matching the metric model already used in the MVP data flow and saved outputs. Do not replace the current data model; extend it into the UI. :contentReference[oaicite:6]{index=6} :contentReference[oaicite:7]{index=7}

### Save/export requirements

After recording ends, the user must be able to save final charts to PNG. Reuse the existing visualization/export logic where possible, instead of duplicating chart export behavior. The existing MVP already saves per-metric and combined PNG plots, so V1 UI should wrap or reuse that capability. :contentReference[oaicite:8]{index=8}

### Stop-recording behavior

A dedicated **Stop Recording** button is required. It must:
- stop the active source safely
- finalize the data collector
- flush pending records
- write final CSV/JSON outputs
- keep the final charts visible in the UI
- enable export actions after the session ends

This should follow the same lifecycle assumptions already used in the MVP collector/source design. :contentReference[oaicite:9]{index=9}

### Architecture rules for V1 UI

- The GUI must be added as a new layer on top of the existing MVP architecture, not as a replacement.
- Do not move business logic into widgets.
- Keep SDK integration in `src/core/capsule_client.py`.
- Keep collection/session logic in `src/core/data_collector.py`.
- Keep charts/export logic in visualization modules.
- The UI should call service/controller classes rather than directly manipulating low-level SDK objects.
- Use background workers/threads for recording so the GUI never freezes.
- All long-running operations must be non-blocking for the UI thread. :contentReference[oaicite:10]{index=10}

### Suggested V1 UI file structure

Add a desktop UI package such as:

```text
src/ui/
  app.py
  main_window.py
  controllers/
    session_controller.py
  widgets/
    control_panel.py
    metrics_panel.py
    live_plot_widget.py
  workers/
    recording_worker.py


This UI layer should orchestrate the existing modules, not duplicate them.

## Implementation priority for Claude Code

When implementing V1 desktop UI:

first reuse the current MVP services and CLI behavior
then add a desktop window with session controls
then add live interactive charts
then add stop/export behavior
finally add device selectors and session polish

Do not rebuild the project from scratch. Extend the MVP already described in MVP_implementation_1.md and the system architecture in design_document.md.