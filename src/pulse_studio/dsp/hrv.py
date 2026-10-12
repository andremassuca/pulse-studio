"""Heart rate variability from a run of valid beat intervals."""

from dataclasses import dataclass

import numpy as np

MIN_INTERVALS = 20


@dataclass(frozen=True)
class Hrv:
    sdnn_ms: float
    rmssd_ms: float
    mean_ibi_ms: float
    count: int


def compute_hrv(
    ibis_ms: list[float], consecutive: list[bool], min_intervals: int = MIN_INTERVALS
) -> Hrv | None:
    """SDNN and RMSSD over the given intervals.

    consecutive[i] tells whether interval i directly follows interval i-1, so
    RMSSD never uses a difference that spans a rejected beat. Returns None
    when there are not enough intervals for the numbers to mean anything.
    """
    if len(ibis_ms) < min_intervals:
        return None
    ibi = np.asarray(ibis_ms, dtype=float)
    diffs = [ibi[i] - ibi[i - 1] for i in range(1, len(ibi)) if consecutive[i]]
    if len(diffs) < min_intervals - 2:
        return None
    return Hrv(
        sdnn_ms=float(np.std(ibi, ddof=1)),
        rmssd_ms=float(np.sqrt(np.mean(np.square(diffs)))),
        mean_ibi_ms=float(np.mean(ibi)),
        count=len(ibi),
    )
