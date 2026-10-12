"""Parsing of the lines sent by the Arduino firmware."""

from dataclasses import dataclass

WRAP_US = 1 << 32


@dataclass(frozen=True)
class Sample:
    t: float  # seconds since the stream started, unwrapped
    value: float  # ADC counts (0-1023, fractional when oversampled)
    device_beat: bool  # the firmware's own detector flagged a beat


class LineParser:
    """Turns serial lines into samples.

    Handles both firmware formats: 1.0 sends plain ADC counts, 1.1 and later
    send the sum of 16 readings (announced by the banner). Banner lines reset
    the clock, because the Arduino restarts every time the port is opened.
    Anything that does not look like a sample is ignored.
    """

    def __init__(self):
        self.firmware_version: str | None = None
        self._divisor = 1.0
        self._prev_us: int | None = None
        self._wraps = 0

    def parse(self, line: str) -> Sample | None:
        line = line.strip()
        if not line:
            return None
        if line.startswith("#"):
            self._read_comment(line)
            return None

        parts = line.split(",")
        if len(parts) not in (2, 3):
            return None
        try:
            t_us = int(parts[0])
            value = int(parts[1])
            flag = len(parts) == 3 and parts[2] == "1"
        except ValueError:
            return None
        if t_us < 0 or t_us >= WRAP_US or value < 0 or value > 16368:
            return None

        if self._prev_us is not None and t_us < self._prev_us - WRAP_US // 2:
            self._wraps += 1
        self._prev_us = t_us
        t = (t_us + self._wraps * WRAP_US) / 1e6
        return Sample(t, value / self._divisor, flag)

    def _read_comment(self, line: str) -> None:
        if not line.startswith("# pulse_sensor"):
            return
        self._prev_us = None
        self._wraps = 0
        self._divisor = 1.0
        for token in line.split():
            if token.startswith("fw="):
                self.firmware_version = token[3:]
            elif token.startswith("oversample="):
                try:
                    self._divisor = float(token[len("oversample=") :]) or 1.0
                except ValueError:
                    pass
