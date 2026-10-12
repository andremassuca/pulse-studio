"""Ties filtering, peak detection, beat tracking, HRV and quality together."""

from collections import deque
from dataclasses import dataclass, field

import numpy as np

from .beats import Beat, BeatTracker
from .filtering import BandpassFilter
from .hrv import Hrv, compute_hrv
from .peaks import PeakDetector
from .quality import Quality, SignalState, assess

FS = 500.0
HRV_WINDOW_S = 90.0
BPM_BEATS = 6  # moving average length for the BPM
STALE_S = 3.0  # no beat for this long: do not show a BPM
MAX_IBI_SPREAD = 0.20  # recent intervals must agree within this (std / mean)
GAP_S = 0.05  # a longer hole in the timestamps restarts the filters


@dataclass
class Metrics:
    bpm: float | None = None
    ibi_ms: float | None = None
    amplitude: float = 0.0
    quality: Quality = field(
        default_factory=lambda: Quality(SignalState.WARMING_UP, 0.0, 0.0, 0.0)
    )
    hrv: Hrv | None = None
    beat_count: int = 0


@dataclass
class Update:
    t: np.ndarray  # new sample times (s)
    raw: np.ndarray  # new raw values (ADC counts)
    filtered: np.ndarray  # new filtered values
    beats: list[Beat]  # beats confirmed during this update
    metrics: Metrics


class PulseProcessor:
    """Streaming processor. Feed it chunks of (time, ADC counts)."""

    def __init__(self, fs: float = FS):
        self.fs = fs
        self._filter = BandpassFilter(fs)
        self._detector = PeakDetector(fs)
        self._tracker = BeatTracker()
        self.reset()

    @property
    def detection_latency_s(self) -> float:
        return self._detector.latency_s

    def reset(self) -> None:
        self._filter.reset()
        self._detector.reset()
        self._tracker.reset()
        n = int(6 * self.fs)
        self._raw_tail: deque[float] = deque(maxlen=n)
        self._filt_tail: deque[float] = deque(maxlen=n)
        self._t0: float | None = None
        self._last_t: float | None = None
        # (beat time, interval in ms, interval directly follows the previous one)
        self._ibis: deque[tuple[float, float, bool]] = deque()
        self._prev_valid_t: float | None = None
        self._recent_flags: deque[bool] = deque(maxlen=8)
        self._beat_count = 0
        self._last_valid_beat_t: float | None = None
        self.metrics = Metrics()

    def process(self, t: np.ndarray, raw: np.ndarray) -> Update:
        t = np.asarray(t, dtype=float)
        raw = np.asarray(raw, dtype=float)
        if t.size == 0:
            return Update(t, raw, raw, [], self.metrics)
        if self._t0 is None:
            self._t0 = float(t[0])
        if self._last_t is not None and t[0] - self._last_t > GAP_S:
            self._restart_stream()

        filtered = self._filter.process(raw)
        self._raw_tail.extend(raw)
        self._filt_tail.extend(filtered)
        self._last_t = float(t[-1])

        beats: list[Beat] = []
        for peak in self._detector.process(t, filtered):
            beat = self._tracker.update(peak)
            if beat is None:
                continue
            beats.append(beat)
            self._register(beat)

        self.metrics = self._build_metrics(float(t[-1]))
        return Update(t, raw, filtered, beats, self.metrics)

    def _restart_stream(self) -> None:
        self._filter.reset()
        self._detector.reset()
        self._tracker.reset()
        self._prev_valid_t = None
        self._recent_flags.clear()

    def _register(self, beat: Beat) -> None:
        self._beat_count += 1
        self._recent_flags.append(beat.valid)
        if beat.valid and beat.ibi_ms is not None:
            follows = self._prev_valid_t is not None and (
                abs(beat.t - beat.ibi_ms / 1000.0 - self._prev_valid_t) < 1e-3
            )
            self._ibis.append((beat.t, beat.ibi_ms, follows))
            self._last_valid_beat_t = beat.t
            self._prev_valid_t = beat.t
        else:
            self._prev_valid_t = None

    def _build_metrics(self, now: float) -> Metrics:
        while self._ibis and now - self._ibis[0][0] > HRV_WINDOW_S:
            self._ibis.popleft()

        n5 = int(5 * self.fs)
        raw = np.fromiter(self._raw_tail, float, len(self._raw_tail))[-n5:]
        filt = np.fromiter(self._filt_tail, float, len(self._filt_tail))[-n5:]
        ratio = (
            sum(self._recent_flags) / len(self._recent_flags) if self._recent_flags else 0.0
        )
        started = self._t0 if self._t0 is not None else now
        quality = assess(raw, filt, self.fs, ratio, now - started)

        bpm = ibi = None
        fresh = self._last_valid_beat_t is not None and now - self._last_valid_beat_t <= STALE_S
        usable = quality.state in (SignalState.GOOD, SignalState.POOR)
        if fresh and usable and len(self._ibis) >= 3:
            last = np.array([x[1] for x in list(self._ibis)[-BPM_BEATS:]])
            # Scattered intervals mean the detector is following noise: show
            # nothing rather than a number that looks plausible but is not.
            if len(last) >= 3 and np.std(last) / np.mean(last) <= MAX_IBI_SPREAD:
                bpm = 60000.0 / float(np.mean(last))
                ibi = self._ibis[-1][1]

        hrv = None
        if usable and self._ibis:
            hrv = compute_hrv([x[1] for x in self._ibis], [x[2] for x in self._ibis])

        return Metrics(
            bpm=bpm,
            ibi_ms=ibi,
            amplitude=quality.amplitude if usable else 0.0,
            quality=quality,
            hrv=hrv,
            beat_count=self._beat_count,
        )
