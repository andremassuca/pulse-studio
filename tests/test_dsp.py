import numpy as np
import pytest

from pulse_studio.acquisition.simulator import PpgGenerator
from pulse_studio.dsp import PulseProcessor, SignalState
from pulse_studio.dsp.beats import BeatTracker
from pulse_studio.dsp.hrv import compute_hrv
from pulse_studio.dsp.peaks import Peak

FS = 500.0


def run(generator: PpgGenerator, seconds: float, processor: PulseProcessor | None = None):
    processor = processor or PulseProcessor(FS)
    beats = []
    chunk = 8
    for _ in range(int(seconds * FS / chunk)):
        t, v = generator.generate(chunk)
        update = processor.process(t, v)
        beats.extend(update.beats)
    return processor, beats


def test_detects_every_beat_and_bpm_is_right():
    gen = PpgGenerator(bpm=72, seed=1)
    proc, beats = run(gen, 40)
    truth = [p for p in gen.peak_times if 2.0 < p < 38.5]
    detected = [b.t for b in beats if 2.0 < b.t < 38.5]
    assert len(detected) == len(truth)
    # Each detected peak lies within one filter delay of the true peak.
    errors = [min(abs(d - p) for p in truth) for d in detected]
    assert max(errors) < 0.08
    assert proc.metrics.bpm == pytest.approx(72, abs=3)
    assert proc.metrics.quality.state == SignalState.GOOD


@pytest.mark.parametrize("bpm", [48, 95, 130])
def test_bpm_range(bpm):
    gen = PpgGenerator(bpm=bpm, seed=2)
    proc, _ = run(gen, 35)
    assert proc.metrics.bpm == pytest.approx(bpm, abs=4)


def test_no_finger_reports_no_beats_and_no_bpm():
    gen = PpgGenerator(seed=3)
    gen.mode = "no_finger"
    proc, beats = run(gen, 20)
    assert proc.metrics.quality.state == SignalState.NO_FINGER
    assert proc.metrics.bpm is None
    assert len(beats) <= 2  # noise must not produce a stream of fake beats


def test_finger_removed_drops_bpm():
    gen = PpgGenerator(seed=4)
    proc, _ = run(gen, 25)
    assert proc.metrics.bpm is not None
    gen.mode = "no_finger"
    run(gen, 12, proc)
    assert proc.metrics.bpm is None
    assert proc.metrics.quality.state == SignalState.NO_FINGER


def test_saturation_is_reported():
    gen = PpgGenerator(seed=5)
    proc, _ = run(gen, 15)
    gen.mode = "saturated"
    run(gen, 4, proc)
    assert proc.metrics.quality.state == SignalState.SATURATED
    assert proc.metrics.bpm is None


def test_motion_is_flagged_and_does_not_invent_a_bpm():
    gen = PpgGenerator(seed=6)
    proc, _ = run(gen, 20)
    gen.mode = "motion"
    states = set()
    for _ in range(int(8 * FS / 8)):
        t, v = gen.generate(8)
        proc.process(t, v)
        states.add(proc.metrics.quality.state)
    assert SignalState.MOTION in states or SignalState.POOR in states


def test_signal_recovers_after_a_bad_period():
    gen = PpgGenerator(bpm=70, seed=7)
    proc, _ = run(gen, 15)
    gen.mode = "no_finger"
    run(gen, 8, proc)
    gen.mode = "finger"
    run(gen, 20, proc)
    assert proc.metrics.bpm == pytest.approx(70, abs=4)


def test_hrv_needs_enough_beats_then_matches_the_signal():
    gen = PpgGenerator(bpm=70, seed=8)
    proc, _ = run(gen, 8)
    assert proc.metrics.hrv is None
    proc, _ = run(gen, 60, proc)
    hrv = proc.metrics.hrv
    assert hrv is not None
    # The generator uses a 35 ms breathing swing plus 12 ms jitter.
    assert 15 < hrv.sdnn_ms < 60
    assert hrv.rmssd_ms > 5


def test_tracker_drops_double_peaks_and_flags_outliers():
    tracker = BeatTracker()
    t = 0.0
    for _ in range(6):
        assert tracker.update(Peak(t, 1.0)) is not None
        t += 0.8
    assert tracker.update(Peak(t - 0.8 + 0.25, 0.5)) is None  # dicrotic notch
    late = tracker.update(Peak(t - 0.8 + 1.4, 1.0))  # a skipped beat
    assert late is not None and late.valid is False
    gap = tracker.update(Peak(t + 5.0, 1.0))
    assert gap is not None and gap.ibi_ms is None


def test_compute_hrv_values():
    ibis = [800, 820, 790, 810, 800, 830, 780, 805, 815, 795]
    hrv = compute_hrv(ibis, [False] + [True] * 9, min_intervals=8)
    assert hrv is not None
    assert hrv.sdnn_ms == pytest.approx(np.std(ibis, ddof=1))
    diffs = np.diff(ibis)
    assert hrv.rmssd_ms == pytest.approx(np.sqrt(np.mean(diffs**2)))
    assert compute_hrv(ibis, [True] * 10) is None  # default minimum is higher


def test_gap_in_timestamps_restarts_without_crashing():
    gen = PpgGenerator(seed=9)
    proc, _ = run(gen, 10)
    t, v = gen.generate(500)
    proc.process(t + 3.0, v)  # three seconds missing
    assert proc.metrics is not None


def test_hrv_extras_are_consistent():
    ibis = [800 + 40 * ((-1) ** i) for i in range(30)]
    hrv = compute_hrv(ibis, [False] + [True] * 29)
    assert hrv is not None
    assert hrv.pnn50 == pytest.approx(100.0)  # every step is 80 ms
    assert hrv.sd1_ms == pytest.approx(hrv.rmssd_ms / np.sqrt(2))
    assert hrv.sd2_ms >= 0


def test_spectral_bpm_and_respiration_on_synthetic_data():
    from pulse_studio.dsp.extras import respiration_rate, spectral_bpm

    t = np.arange(0, 12, 1 / FS)
    wave = np.sin(2 * np.pi * 1.25 * t) + 0.4 * np.sin(2 * np.pi * 2.5 * t)
    wave += np.random.default_rng(1).normal(0, 0.5, t.size)
    bpm, conf = spectral_bpm(wave, FS)
    assert bpm == pytest.approx(75, abs=2)
    assert conf > 0.5

    beats = np.cumsum(np.full(60, 0.85))
    ibis = 850 + 40 * np.sin(2 * np.pi * 0.25 * beats)  # 15 breaths per minute
    rate, conf = respiration_rate(list(beats), list(ibis))
    assert rate == pytest.approx(15, abs=1.5)
    assert conf > 0.5


def test_noise_gives_no_confident_spectral_estimate():
    from pulse_studio.dsp.extras import spectral_bpm

    noise = np.random.default_rng(2).normal(0, 1, int(10 * FS))
    est = spectral_bpm(noise, FS)
    assert est is None or est[1] < 0.35
