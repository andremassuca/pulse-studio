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
    pnn50: float  # percent of successive differences above 50 ms
    sd1_ms: float  # Poincare short axis (beat to beat variability)
    sd2_ms: float  # Poincare long axis (slower variability)


def correct_artifacts(ibis_ms: list[float], consecutive: list[bool], tolerance: float = 0.25):
    """Drops intervals that stray from the local median (usual HRV practice).

    A dropped interval also breaks the chain, so RMSSD never subtracts across
    the gap.
    """
    n = len(ibis_ms)
    keep_ibi: list[float] = []
    keep_cons: list[bool] = []
    broken = False
    for i in range(n):
        lo, hi = max(0, i - 3), min(n, i + 4)
        local = float(np.median(ibis_ms[lo:hi]))
        if abs(ibis_ms[i] - local) > tolerance * local:
            broken = True
            continue
        keep_ibi.append(ibis_ms[i])
        keep_cons.append(consecutive[i] and not broken and bool(keep_ibi[:-1]))
        broken = False
    return keep_ibi, keep_cons


def compute_hrv(
    ibis_ms: list[float], consecutive: list[bool], min_intervals: int = MIN_INTERVALS
) -> Hrv | None:
    """SDNN and RMSSD over the given intervals.

    consecutive[i] tells whether interval i directly follows interval i-1, so
    RMSSD never uses a difference that spans a rejected beat. Returns None
    when there are not enough intervals for the numbers to mean anything.
    """
    ibis_ms, consecutive = correct_artifacts(ibis_ms, consecutive)
    if len(ibis_ms) < min_intervals:
        return None
    ibi = np.asarray(ibis_ms, dtype=float)
    diffs = [ibi[i] - ibi[i - 1] for i in range(1, len(ibi)) if consecutive[i]]
    if len(diffs) < min_intervals - 2:
        return None
    sdnn = float(np.std(ibi, ddof=1))
    rmssd = float(np.sqrt(np.mean(np.square(diffs))))
    sd1 = rmssd / np.sqrt(2.0)
    sd2 = float(np.sqrt(max(0.0, 2.0 * sdnn**2 - sd1**2)))
    return Hrv(
        sdnn_ms=sdnn,
        rmssd_ms=rmssd,
        mean_ibi_ms=float(np.mean(ibi)),
        count=len(ibi),
        pnn50=float(100.0 * np.mean(np.abs(diffs) > 50.0)),
        sd1_ms=float(sd1),
        sd2_ms=sd2,
    )
