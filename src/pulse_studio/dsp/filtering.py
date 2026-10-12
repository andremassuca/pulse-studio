"""Streaming band-pass filter for the raw PPG signal."""

import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi


class BandpassFilter:
    """Causal Butterworth band-pass that keeps its state between chunks.

    The pulse of a resting adult sits between roughly 0.7 and 3 Hz, so the
    default 0.5-5 Hz band removes the slow baseline drift and most of the
    high frequency noise while keeping the shape of each beat.
    """

    def __init__(self, fs: float, low: float = 0.5, high: float = 5.0, order: int = 2):
        self._sos = butter(order, [low, high], btype="band", fs=fs, output="sos")
        self._zi_unit = sosfilt_zi(self._sos)
        self._zi: np.ndarray | None = None

    def reset(self) -> None:
        self._zi = None

    def process(self, x: np.ndarray) -> np.ndarray:
        if x.size == 0:
            return x.astype(float)
        if self._zi is None:
            # Start from the steady state of the first value so the filter
            # does not ring when the first sample is far from zero.
            self._zi = self._zi_unit * float(x[0])
        y, self._zi = sosfilt(self._sos, x.astype(float), zi=self._zi)
        return y
