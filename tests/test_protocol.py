import pytest

from pulse_studio.acquisition.protocol import LineParser


def test_parses_plain_and_beat_lines():
    p = LineParser()
    s = p.parse("2000,509\r\n")
    assert s is not None and s.t == pytest.approx(0.002) and s.value == 509
    assert not s.device_beat
    assert p.parse("4000,510,1").device_beat


def test_oversampled_values_are_scaled_by_the_banner():
    p = LineParser()
    p.parse("# pulse_sensor fw=1.1.0 fs=500 baud=115200 format=t_us,adc16[,beat] oversample=16")
    assert p.firmware_version == "1.1.0"
    assert p.parse("2000,8192").value == pytest.approx(512.0)


@pytest.mark.parametrize(
    "line", ["", "# stats drops=1 resyncs=0", "garbage", "12,", "a,b", "1,2,3,4", "-5,10", "10,99999", "3?????"]
)
def test_ignores_noise(line):
    assert LineParser().parse(line) is None


def test_timestamp_wraps_and_banner_resets():
    p = LineParser()
    a = p.parse("4294960000,500")
    b = p.parse("5000,500")
    assert b.t > a.t
    assert b.t == pytest.approx((5000 + 2**32) / 1e6)
    p.parse("# pulse_sensor fw=1.1.0 oversample=16")
    c = p.parse("2000,8000")
    assert c.t == pytest.approx(0.002)
