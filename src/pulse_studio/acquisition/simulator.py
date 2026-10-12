"""Simulated pulse signal for the demo mode and for tests."""

import threading
import time
from collections import deque

import numpy as np

from .protocol import Sample

SYSTOLIC_PEAK_S = 0.15  # time from the foot of the wave to its top


def pulse_shape(tau: np.ndarray) -> np.ndarray:
    """One pulse wave: fast rise, slower fall and a small dicrotic bump."""
    tau = np.asarray(tau, dtype=float)
    out = np.zeros_like(tau)
    pos = tau > 0
    x = tau[pos] / SYSTOLIC_PEAK_S
    systolic = x**2 * np.exp(2.0 * (1.0 - x))
    dicrotic = 0.28 * np.exp(-0.5 * ((tau[pos] - 0.42) / 0.07) ** 2)
    out[pos] = systolic + dicrotic
    return out


class PpgGenerator:
    """Continuous synthetic PPG with natural beat to beat variation.

    The mode can be changed at any time to produce the bad cases the app has
    to recognise: "finger", "no_finger", "motion" and "saturated".
    """

    def __init__(
        self,
        fs: float = 500.0,
        bpm: float = 72.0,
        amplitude: float = 3.2,
        noise: float = 0.3,
        seed: int | None = None,
    ):
        self.fs = fs
        self.bpm = bpm
        self.amplitude = amplitude
        self.noise = noise
        self.mode = "finger"
        self._rng = np.random.default_rng(seed)
        self._n = 0
        self._beats: deque[float] = deque()
        self._next_beat = 0.2
        self.peak_times: list[float] = []  # ground truth, for tests
        self._motion_phase = 0.0

    def _extend_beats(self, until: float) -> None:
        while self._next_beat < until:
            self._beats.append(self._next_beat)
            self.peak_times.append(self._next_beat + SYSTOLIC_PEAK_S)
            t = self._next_beat
            # Breathing related variation plus a little random jitter.
            ibi = 60.0 / self.bpm + 0.035 * np.sin(2 * np.pi * 0.25 * t)
            ibi += self._rng.normal(0.0, 0.012)
            self._next_beat = t + max(0.35, ibi)

    def generate(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        idx = np.arange(self._n, self._n + n)
        t = idx / self.fs
        self._n += n
        self._extend_beats(t[-1] + 1.0)
        while self._beats and self._beats[0] < t[0] - 1.5:
            self._beats.popleft()

        wave = np.zeros(n)
        for b in self._beats:
            if b < t[-1] + 0.01 and b > t[0] - 1.5:
                wave += pulse_shape(t - b)

        drift = 1.5 * np.sin(2 * np.pi * 0.08 * t)
        noise = self._rng.normal(0.0, self.noise, n)

        if self.mode == "no_finger":
            signal = 511.0 + noise * 0.6
        elif self.mode == "saturated":
            signal = np.full(n, 1023.0) - np.abs(noise)
        elif self.mode == "motion":
            self._motion_phase += 1
            burst = 25.0 * np.sin(2 * np.pi * 1.7 * t) * np.sin(2 * np.pi * 0.4 * t)
            signal = 512.0 + drift + burst + self.amplitude * wave + noise
        else:
            signal = 512.0 + drift + self.amplitude * (wave - 0.35) + noise
        return t, np.clip(signal, 0, 1023)


class SimulatedSource:
    """Delivers generated samples in real time, like the serial reader."""

    def __init__(self, bpm: float = 72.0, seed: int | None = None):
        self._gen = PpgGenerator(bpm=bpm, seed=seed)
        self._lock = threading.Lock()
        self._samples: deque[Sample] = deque()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None
        self.description = "Demo (simulated signal)"
        self.firmware_version: str | None = "demo"

    @property
    def mode(self) -> str:
        return self._gen.mode

    @mode.setter
    def mode(self, value: str) -> None:
        self._gen.mode = value

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="simulator", daemon=True)
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
        produced = 0
        fs = self._gen.fs
        while not self._stop.is_set():
            due = int((time.perf_counter() - start) * fs)
            if due > produced:
                t, v = self._gen.generate(due - produced)
                produced = due
                batch = [Sample(float(a), float(b), False) for a, b in zip(t, v)]
                with self._lock:
                    self._samples.extend(batch)
            time.sleep(0.008)
