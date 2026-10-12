"""A live session: a sample source, the processor and the data for the display."""

from pathlib import Path

import numpy as np

from .dsp import Beat, Metrics, PulseProcessor
from .recording import SessionRecorder

KEEP_S = 45.0  # how much signal is kept for the plots
BEAT_KEEP_S = 150.0


class Session:
    def __init__(self):
        self.processor = PulseProcessor()
        self.source = None
        self.recorder: SessionRecorder | None = None
        self._clear()

    def _clear(self) -> None:
        self.t = np.empty(0)
        self.raw = np.empty(0)
        self.filtered = np.empty(0)
        self.beats: list[Beat] = []
        self.latest_t = 0.0
        self.processor.reset()

    @property
    def metrics(self) -> Metrics:
        return self.processor.metrics

    @property
    def active(self) -> bool:
        return self.source is not None

    @property
    def error(self) -> str | None:
        return getattr(self.source, "error", None) if self.source else None

    def start(self, source) -> None:
        self.stop()
        self._clear()
        source.start()
        self.source = source

    def stop(self) -> None:
        if self.recorder is not None:
            self.stop_recording()
        if self.source is not None:
            self.source.stop()
            self.source = None

    def start_recording(self, folder: Path) -> Path:
        self.recorder = SessionRecorder(folder)
        return self.recorder.samples_path

    def stop_recording(self) -> tuple[Path, Path] | None:
        if self.recorder is None:
            return None
        paths = self.recorder.close()
        self.recorder = None
        return paths

    def poll(self) -> list[Beat]:
        """Moves new samples through the processor. Returns the new beats."""
        if self.source is None:
            return []
        samples = self.source.drain()
        if not samples:
            return []
        t = np.fromiter((s.t for s in samples), float, len(samples))
        v = np.fromiter((s.value for s in samples), float, len(samples))
        update = self.processor.process(t, v)

        keep = int(KEEP_S * self.processor.fs)
        self.t = np.concatenate([self.t, update.t])[-keep:]
        self.raw = np.concatenate([self.raw, update.raw])[-keep:]
        self.filtered = np.concatenate([self.filtered, update.filtered])[-keep:]
        self.latest_t = float(self.t[-1])

        self.beats.extend(update.beats)
        cutoff = self.latest_t - BEAT_KEEP_S
        if self.beats and self.beats[0].t < cutoff:
            self.beats = [b for b in self.beats if b.t >= cutoff]

        if self.recorder is not None:
            self.recorder.add(update.t, update.raw, update.filtered, update.beats)
        return update.beats
