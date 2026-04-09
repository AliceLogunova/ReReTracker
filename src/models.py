"""Data models for EEG session records and summaries."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass
class EEGRecord:
    """Single timestamped EEG measurement from the SDK."""

    timestamp: float        # Unix time (seconds)
    concentration: float    # concentrationScore  [0..1]
    relaxation: float       # relaxationScore     [0..1]
    fatigue: float          # fatigueScore        [0..1]
    artifact: bool = False  # True when SDK flagged a signal artifact

    def to_row(self) -> list[str]:
        return [
            str(self.timestamp),
            str(self.concentration),
            str(self.relaxation),
            str(self.fatigue),
            str(int(self.artifact)),
        ]

    @classmethod
    def csv_header(cls) -> list[str]:
        return ["timestamp", "concentration", "relaxation", "fatigue", "artifact"]

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "EEGRecord":
        return cls(
            timestamp=float(row["timestamp"]),
            concentration=float(row["concentration"]),
            relaxation=float(row["relaxation"]),
            fatigue=float(row["fatigue"]),
            artifact=bool(int(row["artifact"])),
        )


@dataclass
class SessionSummary:
    """Aggregated statistics for a completed EEG session."""

    session_id: str
    start_time: float
    end_time: float
    record_count: int
    mean_concentration: float
    mean_relaxation: float
    mean_fatigue: float
    artifact_ratio: float   # fraction of records with artifacts
    raw_csv_path: str       # path to raw CSV (relative to project root)
    mode: str               # "real" or "mock"

    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time

    def to_dict(self) -> dict:
        d = asdict(self)
        d["duration_seconds"] = self.duration_seconds
        return d

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def from_records(
        cls,
        *,
        session_id: str,
        start_time: float,
        end_time: float,
        records: list[EEGRecord],
        raw_csv_path: str,
        mode: str,
    ) -> "SessionSummary":
        n = len(records)
        if n == 0:
            return cls(
                session_id=session_id,
                start_time=start_time,
                end_time=end_time,
                record_count=0,
                mean_concentration=0.0,
                mean_relaxation=0.0,
                mean_fatigue=0.0,
                artifact_ratio=0.0,
                raw_csv_path=raw_csv_path,
                mode=mode,
            )
        return cls(
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            record_count=n,
            mean_concentration=sum(r.concentration for r in records) / n,
            mean_relaxation=sum(r.relaxation for r in records) / n,
            mean_fatigue=sum(r.fatigue for r in records) / n,
            artifact_ratio=sum(1 for r in records if r.artifact) / n,
            raw_csv_path=raw_csv_path,
            mode=mode,
        )


def write_csv(path: Path, records: Iterator[EEGRecord], *, append: bool = False) -> None:
    """Write (or append) EEGRecords to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    open_mode = "a" if append else "w"
    with open(path, open_mode, newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if not append:
            writer.writerow(EEGRecord.csv_header())
        for rec in records:
            writer.writerow(rec.to_row())


def read_csv(path: Path) -> list[EEGRecord]:
    """Read EEGRecords from a CSV file."""
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return [EEGRecord.from_row(row) for row in reader]
