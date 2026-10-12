"""Plays a recorded session back in real time, in a loop."""

import csv
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np

from .protocol import Sample


def load_recording(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Reads t_s and adc from a samples CSV written by the app."""
    t, v = [], []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t.append(float(row["t_s"]))
            v.append(float(row["adc"]))
    return np.array(t), np.array(v)


class ReplaySource:
    """Same interface as the other sources: start, stop, drain, error."""

    def __init__(self, path: Path):
        self._t, self._v = load_recording(path)
        if self._t.size < 2:
            raise ValueError(f"{path} has no samples")
        self._t = self._t - self._t[0]
        step = float(np.median(np.diff(self._t)))
        self._length = float(self._t[-1]) + step
        self._lock = threading.Lock()
        self._samples: deque[Sample] = deque()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None
        self.description = "Demo (recorded sample)"
        self.firmware_version: str | None = "sample"

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="replay", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def drain(self) -> list[Sample]:
        with self._lock:
            out = list(self._samples)
            self._samples.clear()
        return out

    def _run(self) -> None:
        start = time.perf_counter()
        index = 0
        loops = 0
        n = self._t.size
        while not self._stop.is_set():
            elapsed = time.perf_counter() - start
            batch = []
            # Each pass over the file continues the clock, so the stream has
            # no jump in time. The seam may cost one beat.
            while True:
                t = self._t[index] + loops * self._length
                if t > elapsed:
                    break
                batch.append(Sample(float(t), float(self._v[index]), False))
                index += 1
                if index >= n:
                    index = 0
                    loops += 1
            if batch:
                with self._lock:
                    self._samples.extend(batch)
            time.sleep(0.008)
