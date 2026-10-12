"""Read raw lines from the Arduino for a fixed time and save them to a file.

Usage: python scripts/capture.py COM7 10 out.txt

The Uno resets when the port is opened, so the first lines include the
firmware banner. Close the Arduino Serial Monitor/Plotter first.
"""

import sys
import time

import serial


def capture(port: str, seconds: float, out_path: str) -> int:
    with serial.Serial(port, 115200, timeout=0.2) as ser:
        ser.reset_input_buffer()
        end = time.monotonic() + seconds
        lines = 0
        with open(out_path, "w", encoding="ascii", errors="replace") as out:
            while time.monotonic() < end:
                raw = ser.readline()
                if raw:
                    out.write(raw.decode("ascii", errors="replace").rstrip("\r\n") + "\n")
                    lines += 1
    return lines


if __name__ == "__main__":
    port, seconds, out_path = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    print(f"{capture(port, seconds, out_path)} lines saved to {out_path}")
