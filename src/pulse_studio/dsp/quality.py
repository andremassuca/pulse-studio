"""Signal quality and finger detection."""

from dataclasses import dataclass
from enum import Enum

import numpy as np


class SignalState(str, Enum):
    WARMING_UP = "warming_up"
    NO_FINGER = "no_finger"
    MOTION = "motion"
    SATURATED = "saturated"
    POOR = "poor"
    GOOD = "good"


@dataclass(frozen=True)
class Quality:
    state: SignalState
    score: float  # 0 to 1
    amplitude: float  # peak to peak of the filtered signal, ADC counts
    periodicity: float  # 0 to 1


# Starting values from real recordings: with a finger the filtered pulse is
# about 3 counts peak to peak. They are refined against more data later.
AMPLITUDE_FLOOR = 1.0
AMPLITUDE_GOOD = 4.0
RAIL_LOW = 3.0
RAIL_HIGH = 1020.0
WARMUP_S = 3.0


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def periodicity(y: np.ndarray, fs: float) -> float:
    """Strength of the main repetition between 40 and 180 BPM (0 to 1).

    Normalised autocorrelation at the best lag in that range, so a clean
    pulse trace scores high and random noise scores low.
    """
    if y.size < int(2.5 * fs):
        return 0.0
    y = y - y.mean()
    energy = float(np.dot(y, y))
    if energy <= 1e-12:
        return 0.0
    n = y.size
    spec = np.fft.rfft(y, 2 * n)
    ac = np.fft.irfft(spec * np.conj(spec))[:n]
    ac = ac / ac[0]
    lo, hi = int(fs * 60 / 180), min(int(fs * 60 / 40), n - 1)
    seg = ac[lo : hi + 1]
    return _clip01(float(seg.max())) if seg.size else 0.0


def assess(
    raw: np.ndarray,
    filtered: np.ndarray,
    fs: float,
    valid_beat_ratio: float,
    seconds_since_start: float,
) -> Quality:
    """Judge the last few seconds of signal.

    raw is in ADC counts and filtered is the band-passed signal over the same
    span (about 5 s).
    """
    if seconds_since_start < WARMUP_S or filtered.size < int(2 * fs):
        return Quality(SignalState.WARMING_UP, 0.0, 0.0, 0.0)

    amp = float(np.percentile(filtered, 97) - np.percentile(filtered, 3))
    per = periodicity(filtered, fs)

    last_s = raw[-int(fs) :]
    if last_s.size and np.mean((last_s <= RAIL_LOW) | (last_s >= RAIL_HIGH)) > 0.2:
        return Quality(SignalState.SATURATED, 0.0, amp, per)

    # A movement artifact is a short burst far larger than the usual pulse.
    recent = filtered[-int(fs) :]
    recent_amp = float(recent.max() - recent.min())
    if amp > 0 and recent_amp > 4.0 * amp and recent_amp > 4 * AMPLITUDE_GOOD:
        return Quality(SignalState.MOTION, 0.1, amp, per)

    if amp < AMPLITUDE_FLOOR:
        return Quality(SignalState.NO_FINGER, 0.0, amp, per)

    score = (
        0.35 * _clip01((amp - AMPLITUDE_FLOOR) / (AMPLITUDE_GOOD - AMPLITUDE_FLOOR))
        + 0.40 * _clip01((per - 0.25) / 0.5)
        + 0.25 * _clip01(valid_beat_ratio)
    )
    if score < 0.12:
        return Quality(SignalState.NO_FINGER, score, amp, per)
    state = SignalState.GOOD if score >= 0.5 else SignalState.POOR
    return Quality(state, score, amp, per)
