import time

import numpy as np

from pulse_studio.acquisition import ReplaySource
from pulse_studio.dsp import PulseProcessor
from pulse_studio.recording import SessionRecorder
from pulse_studio.resources import sample_recording


def test_sample_recording_gives_a_sensible_bpm():
    from pulse_studio.acquisition.replay import load_recording

    path = sample_recording()
    assert path is not None
    t, v = load_recording(path)
    proc = PulseProcessor(500.0)
    for i in range(0, len(t), 8):
        proc.process(t[i : i + 8], v[i : i + 8])
    assert 60 < proc.metrics.bpm < 100


def test_replay_source_streams_in_real_time_and_loops():
    src = ReplaySource(sample_recording())
    src.start()
    time.sleep(0.6)
    got = src.drain()
    src.stop()
    assert 200 < len(got) < 400  # about 0.6 s at 500 Hz
    assert all(b.t > a.t for a, b in zip(got, got[1:]))


def test_recorder_writes_samples_and_beats_with_flags(tmp_path):
    rec = SessionRecorder(tmp_path)
    proc = PulseProcessor(500.0)
    from pulse_studio.acquisition.simulator import PpgGenerator

    gen = PpgGenerator(seed=3)
    for _ in range(int(12 * 500 / 8)):
        t, v = gen.generate(8)
        u = proc.process(t, v)
        rec.add(u.t, u.raw, u.filtered, u.beats)
    samples_path, beats_path = rec.close()

    rows = samples_path.read_text().splitlines()
    beats = beats_path.read_text().splitlines()
    assert rows[0] == "t_s,adc,filtered,beat"
    assert beats[0] == "t_s,ibi_ms,bpm,height,valid"
    assert len(rows) - 1 == 12 * 500
    flagged = [r for r in rows[1:] if r.endswith(",1")]
    assert len(flagged) == len(beats) - 1 > 5
    # The flag sits on the exact sample of the beat time.
    first_beat_t = float(beats[1].split(",")[0])
    assert any(abs(float(r.split(",")[0]) - first_beat_t) < 1e-6 for r in flagged)
