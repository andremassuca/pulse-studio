"""Extra measurements: spectral BPM and respiration estimate."""

import numpy as np


def spectral_bpm(filtered: np.ndarray, fs: float) -> tuple[float, float] | None:
    """BPM from the strongest frequency of the filtered signal.

    Works when single beats are too noisy to track but the pulse is still the
    dominant rhythm. Returns (bpm, confidence) with confidence in 0-1: the
    share of the 0.5-4 Hz power that sits in the main peak and its harmonic.
    """
    n = int(8 * fs)
    if filtered.size < n:
        return None
    x = filtered[-n:] - np.mean(filtered[-n:])
    if float(np.dot(x, x)) < 1e-9:
        return None
    size = 1 << 14
    spec = np.abs(np.fft.rfft(x * np.hanning(n), size)) ** 2
    freqs = np.fft.rfftfreq(size, 1 / fs)
    band = (freqs >= 0.5) & (freqs <= 4.0)
    pulse = (freqs >= 0.7) & (freqs <= 3.0)
    total = float(spec[band].sum())
    if total <= 0:
        return None
    idx = np.flatnonzero(pulse)[int(np.argmax(spec[pulse]))]
    f0 = float(freqs[idx])
    near = lambda f: (freqs >= f - 0.15) & (freqs <= f + 0.15)  # noqa: E731
    power = float(spec[near(f0)].sum()) + float(spec[near(2 * f0)].sum() if 2 * f0 <= 4.0 else 0.0)
    return f0 * 60.0, min(1.0, power / total)


def respiration_rate(
    beat_times: list[float], ibis_ms: list[float], min_beats: int = 25
) -> tuple[float, float] | None:
    """Breaths per minute from respiratory sinus arrhythmia.

    The heart speeds up when breathing in and slows down when breathing out,
    so the interval series oscillates at the breathing rate. Needs a steady
    series of about half a minute. Returns (breaths per minute, confidence).
    This is an estimate, not a measurement.
    """
    if len(ibis_ms) < min_beats:
        return None
    t = np.asarray(beat_times, dtype=float)
    y = np.asarray(ibis_ms, dtype=float)
    if t[-1] - t[0] < 25.0:
        return None
    grid = np.arange(t[0], t[-1], 0.25)
    series = np.interp(grid, t, y)
    series = series - np.polyval(np.polyfit(grid, series, 1), grid)  # remove the trend
    size = 1 << 12
    spec = np.abs(np.fft.rfft(series * np.hanning(series.size), size)) ** 2
    freqs = np.fft.rfftfreq(size, 0.25)
    band = (freqs >= 0.1) & (freqs <= 0.5)
    if float(spec[band].sum()) <= 0:
        return None
    idx = np.flatnonzero(band)[int(np.argmax(spec[band]))]
    near = (freqs >= freqs[idx] - 0.04) & (freqs <= freqs[idx] + 0.04)
    confidence = float(spec[near].sum() / spec[band].sum())
    return float(freqs[idx] * 60.0), min(1.0, confidence)
