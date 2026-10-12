"""Reads the Arduino stream on a background thread."""

import threading
import time
from collections import deque

import serial

from .protocol import LineParser, Sample

BAUD = 115200


class SerialSource:
    """Same interface as SimulatedSource: start, stop, drain, error."""

    def __init__(self, port: str, description: str = ""):
        self.port = port
        self.description = description or port
        self.error: str | None = None
        self.firmware_version: str | None = None
        self._lock = threading.Lock()
        self._samples: deque[Sample] = deque()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._opened = threading.Event()

    def start(self) -> None:
        """Opens the port. Raises RuntimeError with a readable message on failure."""
        try:
            ser = serial.Serial(self.port, BAUD, timeout=0.1)
        except serial.SerialException as exc:
            text = str(exc)
            if "PermissionError" in text or "Access is denied" in text or "denied" in text.lower():
                raise RuntimeError(
                    f"{self.port} is busy. Close the Arduino Serial Monitor or Plotter "
                    "and any other program using it, then try again."
                ) from exc
            raise RuntimeError(f"Could not open {self.port}: {text}") from exc
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(ser,), name="serial", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def drain(self) -> list[Sample]:
        with self._lock:
            out = list(self._samples)
            self._samples.clear()
        return out

    def _run(self, ser: serial.Serial) -> None:
        parser = LineParser()
        buffer = b""
        opened = time.monotonic()
        # The banner tells which scale the values use (plain counts or the sum
        # of 16 readings), so nothing is accepted before it. Opening the port
        # usually resets the Uno and the banner comes by itself after about two
        # seconds. If it does not, or the board was left in Serial Plotter
        # mode, ask for it: the C command prints it and selects the compact
        # format. A board that never sends one is taken to be the old
        # firmware after a few seconds.
        next_ask = opened + 0.4
        try:
            ser.reset_input_buffer()
            while not self._stop.is_set():
                now = time.monotonic()
                if parser.firmware_version is None and now >= next_ask:
                    ser.write(b"C")
                    next_ask = now + 1.0
                chunk = ser.read(max(1, ser.in_waiting))
                if not chunk:
                    continue
                buffer += chunk
                *lines, buffer = buffer.split(b"\n")
                batch: list[Sample] = []
                for raw in lines:
                    sample = parser.parse(raw.decode("ascii", errors="ignore"))
                    if sample is not None:
                        batch.append(sample)
                self.firmware_version = parser.firmware_version
                ready = parser.firmware_version is not None or time.monotonic() - opened > 4.0
                if batch and ready:
                    with self._lock:
                        self._samples.extend(batch)
        except (serial.SerialException, OSError) as exc:
            self.error = f"Connection to {self.port} lost: {exc}"
        finally:
            try:
                ser.close()
            except Exception:
                pass
