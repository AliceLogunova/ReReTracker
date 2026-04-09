# Design Document — ReReTracker (EEG)

---

## 1. Мета-информация

| Параметр | Значение |
|----------|----------|
| Название | Brain Activity Tracker |
| Цель | Сбор и анализ активности мозга пользователя (концентрация и релаксация) |
| Платформа | Python (CLI / Desktop app) |
| Источник данных | CapsuleAPI (Neiry EEG SDK) |
| Основные метрики | concentration, relaxation, fatigue |
| Длительность записи | до нескольких часов |
| Выход | CSV / JSON + графики |

---

## 2. Архитектура системы

### Слои:

| Слой | Описание |
|------|---------|
| Data Acquisition | CapsuleAPI (CapsuleClient.dll) |
| Processing Layer | Python wrapper над Capsule API |
| Storage | CSV / JSON |
| Visualization | matplotlib / plotly |
| Control Layer | CLI / main script |

---

## 3. API (CapsuleAPI integration)

### Внешний SDK:
- CapsuleClient.dll
- CClientAPI.h
- CNFB.h
- CNFBMetricsProductivity.h

### Основные события:

| Событие | Данные |
|--------|--------|
| OnProductivityUpdated | concentration, relaxation, fatigue |
| OnResistancesUpdated | качество контактов |
| OnArtifacts | шум |

---

## 4. User Flow

1. Пользователь запускает программу
2. Выбирает режим:
   - реальное устройство
   - тестовый режим
3. Подключение к устройству
4. Запуск сессии EEG
5. Калибровка (NFB Training)
6. Сбор данных в течение N часов
7. Сохранение результатов
8. Построение графиков

---

## 5. Data Flow

Device → CapsuleAPI → Python Wrapper → Event Handler → Storage → Visualization


---

## 6. Действия с данными

| Действие | Описание |
|--------|---------|
| Сбор | получение значений каждые ~100-1000 мс |
| Очистка | фильтрация артефактов |
| Агрегация | усреднение по окнам |
| Сохранение | CSV/JSON |
| Анализ | вычисление трендов |

---

## 7. Модель данных

```json
{
  "timestamp": float,
  "concentration": float,
  "relaxation": float,
  "fatigue": float,
  "artifact": bool
}

---

## 8. Технологический стек 

Python 3.11+
ctypes / cffi (для CapsuleAPI)
matplotlib / plotly
pandas
threading / asyncio

---

## 9. Scope
MVP:
    подключение к CapsuleAPI
    получение concentration / relaxation
    запись в файл
    базовый график
Advanced:
    live visualization
    фильтрация артефактов
    анализ сессии

---

## 10. Графики

Построить:
    concentration vs time
    relaxation vs time
    fatigue vs time
    combined chart

Дополнительно:
    moving average
    пики активности
    корреляция relaxation vs concentration

---

## CapsuleAPI SDK layout

- `CapsuleAPI/Include/` — C headers for SDK
- `CapsuleAPI/bin/CapsuleClient.dll` — runtime DLL to load from Python
- `CapsuleAPI/Lib/CapsuleClient.lib` — import library for C/C++

