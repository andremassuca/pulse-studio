"""Streaming peak detection on the filtered signal."""

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import maximum_filter1d


@dataclass(frozen=True)
class Peak:
    t: float
    height: float


class PeakDetector:
    """Finds the top of each pulse wave.

    A sample is a peak when it is the maximum of a window of +-window_s
    around it and it is tall enough compared to the recent signal. A peak is
    only confirmed window_s after it happened, so the detection latency is
    fixed and known. The interface displays the signal with a delay larger
    than that, which lets markers and the heart animation fire exactly when
    the trace reaches the peak.
    """

    def __init__(
        self,
        fs: float,
        window_s: float = 0.10,
        amplitude_window_s: float = 4.0,
        rel_threshold: float = 0.4,
        min_height: float = 0.5,
    ):
        self.fs = fs
        self.latency_s = window_s
        self._w = max(1, int(round(window_s * fs)))
        self._rel = rel_threshold
        self._min_height = min_height
        self._ring_len = int(amplitude_window_s * fs)
        self._t = np.empty(0)
        self._y = np.empty(0)
        self._ring = np.empty(0)
        self._first_unchecked = 0  # index in the buffer of the next centre to test
        self._reference = 0.0

    def reset(self) -> None:
        self._t = np.empty(0)
        self._y = np.empty(0)
        self._ring = np.empty(0)
        self._first_unchecked = 0
        self._reference = 0.0

    @property
    def reference_height(self) -> float:
        """Recent upper level of the signal, used for the relative threshold."""
        return self._reference

    def process(self, t: np.ndarray, y: np.ndarray) -> list[Peak]:
        if t.size == 0:
            return []
        w = self._w
        if self._t.size == 0:
            self._first_unchecked = w  # nothing to the left of the first samples
        self._t = np.concatenate([self._t, t])
        self._y = np.concatenate([self._y, y])
        self._ring = np.concatenate([self._ring, y])[-self._ring_len :]
        if self._ring.size >= self._w * 4:
            self._reference = float(np.percentile(self._ring, 95))

        peaks: list[Peak] = []
        last_centre = self._y.size - 1 - w
        if last_centre >= self._first_unchecked:
            size = 2 * w + 1
            local_max = maximum_filter1d(self._y, size=size, mode="nearest")
            lo, hi = self._first_unchecked, last_centre
            idx = np.arange(lo, hi + 1)
            is_max = self._y[idx] >= local_max[idx]
            # On a plateau keep only the first sample.
            left_strict = np.array(
                [self._y[i] > self._y[max(0, i - w) : i].max(initial=-np.inf) for i in idx]
            )
            threshold = max(self._min_height, self._rel * self._reference)
            for i in idx[is_max & left_strict]:
                if self._y[i] >= threshold:
                    peaks.append(Peak(float(self._t[i]), float(self._y[i])))
            self._first_unchecked = last_centre + 1

        # Keep enough samples on the left for the next windows.
        keep = 2 * w + 1
        if self._y.size > keep + self._first_unchecked - w:
            drop = self._first_unchecked - w - 1
            if drop > 0:
                self._t = self._t[drop:]
                self._y = self._y[drop:]
                self._first_unchecked -= drop
        return peaks
