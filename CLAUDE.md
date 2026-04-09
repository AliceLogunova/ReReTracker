
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