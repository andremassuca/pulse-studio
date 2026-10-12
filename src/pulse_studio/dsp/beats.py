"""Beat validation: plausible intervals and rejection of outliers."""

from collections import deque
from dataclasses import dataclass
from statistics import median

from .peaks import Peak

MIN_IBI_S = 0.30  # 200 BPM
MAX_IBI_S = 2.00  # 30 BPM
MAX_DEVIATION = 0.30  # relative to the median of recent valid intervals


@dataclass(frozen=True)
class Beat:
    t: float
    height: float
    ibi_ms: float | None  # interval since the previous beat, None if unknown
    valid: bool  # interval is plausible and consistent, usable for BPM and HRV


class BeatTracker:
    """Turns raw peaks into beats and decides which intervals can be trusted.

    A peak that arrives too soon after the previous one (a dicrotic notch or
    noise) is dropped. A long silence breaks the chain so no interval is
    invented across it. Intervals far from the recent median are kept as
    beats but flagged invalid; three in a row mean the rhythm really changed
    and the history restarts.
    """

    def __init__(self):
        self._last: Beat | None = None
        self._recent: deque[float] = deque(maxlen=8)
        self._outliers_in_a_row = 0
        self._boot_prev: float | None = None

    def reset(self) -> None:
        self._last = None
        self._recent.clear()
        self._outliers_in_a_row = 0
        self._boot_prev = None

    @property
    def last_beat(self) -> Beat | None:
        return self._last

    def _min_interval(self) -> float:
        if len(self._recent) >= 3:
            return max(MIN_IBI_S, 0.5 * median(self._recent))
        return MIN_IBI_S

    def update(self, peak: Peak) -> Beat | None:
        if self._last is None:
            self._last = Beat(peak.t, peak.height, None, False)
            return self._last

        dt = peak.t - self._last.t
        if dt < self._min_interval():
            return None
        if dt > MAX_IBI_S:
            self._recent.clear()
            self._outliers_in_a_row = 0
            self._boot_prev = None
            self._last = Beat(peak.t, peak.height, None, False)
            return self._last

        if len(self._recent) < 3:
            # No history yet: trust an interval only when it agrees with the
            # one before it.
            prev = self._boot_prev
            self._boot_prev = dt
            valid = prev is not None and abs(dt - prev) <= MAX_DEVIATION * prev
            if valid:
                self._recent.append(dt)
            self._last = Beat(peak.t, peak.height, dt * 1000.0, valid)
            return self._last

        ref = median(self._recent)
        valid = abs(dt - ref) <= MAX_DEVIATION * ref
        if valid:
            self._recent.append(dt)
            self._outliers_in_a_row = 0
        else:
            self._outliers_in_a_row += 1
            if self._outliers_in_a_row >= 3:
                self._recent.clear()
                self._recent.append(dt)
                self._outliers_in_a_row = 0
                valid = True
        self._last = Beat(peak.t, peak.height, dt * 1000.0, valid)
        return self._last
