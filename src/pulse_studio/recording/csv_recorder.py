"""Session recording to CSV: raw samples and detected beats."""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from ..dsp import Beat

HOLD_BACK_S = 0.5  # samples wait for the beats that are confirmed a bit later


def default_folder() -> Path:
    return Path.home() / "Documents" / "Pulse Studio"


class SessionRecorder:
    """Writes two files per session in the chosen folder.

    <name>_samples.csv has t_s, adc (counts), filtered and beat (1 on the
    sample where a peak was detected). <name>_beats.csv has one row per beat
    with its interval, instantaneous BPM, height and whether it was accepted
    for BPM and HRV.
    """

    def __init__(self, folder: Path, started: datetime | None = None):
        folder.mkdir(parents=True, exist_ok=True)
        stamp = (started or datetime.now()).strftime("%Y%m%d_%H%M%S")
        self.samples_path = folder / f"pulse_{stamp}_samples.csv"
        self.beats_path = folder / f"pulse_{stamp}_beats.csv"
        self._samples_file = open(self.samples_path, "w", newline="", encoding="utf-8")
        self._beats_file = open(self.beats_path, "w", newline="", encoding="utf-8")
        self._samples = csv.writer(self._samples_file)
        self._beats = csv.writer(self._beats_file)
        self._samples.writerow(["t_s", "adc", "filtered", "beat"])
        self._beats.writerow(["t_s", "ibi_ms", "bpm", "height", "valid"])
        self._t = np.empty(0)
        self._raw = np.empty(0)
        self._filt = np.empty(0)
        self._beat_keys: set[int] = set()
        self.sample_count = 0
        self.beat_count = 0
        self.first_t: float | None = None
        self.last_t: float = 0.0

    @property
    def duration(self) -> float:
        return 0.0 if self.first_t is None else self.last_t - self.first_t

    def add(self, t: np.ndarray, raw: np.ndarray, filtered: np.ndarray, beats: list[Beat]) -> None:
        if t.size:
            if self.first_t is None:
                self.first_t = float(t[0])
            self.last_t = float(t[-1])
            self._t = np.concatenate([self._t, t])
            self._raw = np.concatenate([self._raw, raw])
            self._filt = np.concatenate([self._filt, filtered])
        for b in beats:
            self._beat_keys.add(round(b.t * 1e6))
            bpm = "" if b.ibi_ms is None else f"{60000.0 / b.ibi_ms:.1f}"
            ibi = "" if b.ibi_ms is None else f"{b.ibi_ms:.1f}"
            self._beats.writerow([f"{b.t:.6f}", ibi, bpm, f"{b.height:.4f}", int(b.valid)])
            self.beat_count += 1
        self._write_ready(final=False)

    def _write_ready(self, final: bool) -> None:
        if self._t.size == 0:
            return
        limit = self._t[-1] + 1 if final else self._t[-1] - HOLD_BACK_S
        n = int(np.searchsorted(self._t, limit))
        for i in range(n):
            key = round(self._t[i] * 1e6)
            self._samples.writerow(
                [f"{self._t[i]:.6f}", f"{self._raw[i]:.3f}", f"{self._filt[i]:.4f}",
                 int(key in self._beat_keys)]
            )
            self._beat_keys.discard(key)
        self.sample_count += n
        self._t, self._raw, self._filt = self._t[n:], self._raw[n:], self._filt[n:]
        self._samples_file.flush()
        self._beats_file.flush()

    def close(self) -> tuple[Path, Path]:
        self._write_ready(final=True)
        self._samples_file.close()
        self._beats_file.close()
        return self.samples_path, self.beats_path


@dataclass(frozen=True)
class SessionInfo:
    samples_path: Path
    started: datetime | None
    duration_s: float
    size_bytes: int
    beats: int


def _last_time(path: Path) -> float:
    """t_s of the last row, read from the end of the file."""
    with open(path, "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - 400))
        lines = f.read().decode("utf-8", errors="ignore").splitlines()
    for line in reversed(lines):
        head = line.split(",")[0]
        try:
            return float(head)
        except ValueError:
            continue
    return 0.0


def list_sessions(folder: Path) -> list[SessionInfo]:
    """Recordings in a folder, newest first."""
    found: list[SessionInfo] = []
    if not folder.exists():
        return found
    for path in folder.glob("pulse_*_samples.csv"):
        stamp = path.name[len("pulse_") : -len("_samples.csv")]
        try:
            started = datetime.strptime(stamp, "%Y%m%d_%H%M%S")
        except ValueError:
            started = None
        beats_file = path.with_name(path.name.replace("_samples.csv", "_beats.csv"))
        beats = 0
        if beats_file.exists():
            with open(beats_file, encoding="utf-8", errors="ignore") as f:
                beats = max(0, sum(1 for _ in f) - 1)
        first = 0.0
        try:
            with open(path, encoding="utf-8") as f:
                f.readline()
                first = float(f.readline().split(",")[0])
        except (ValueError, OSError):
            pass
        found.append(SessionInfo(path, started, max(0.0, _last_time(path) - first), path.stat().st_size, beats))
    found.sort(key=lambda s: s.started or datetime.min, reverse=True)
    return found
