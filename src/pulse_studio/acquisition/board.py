"""One-off commands to the Arduino firmware."""

import time

import serial

BAUD = 115200


def send_command(port: str, command: bytes, settle_s: float = 2.4) -> None:
    """Opens the port, waits for the Uno to finish resetting, sends one command.

    Raises serial.SerialException when the port cannot be opened, for example
    because the Serial Monitor or another program is using it.
    """
    with serial.Serial(port, BAUD, timeout=0.3) as ser:
        time.sleep(settle_s)  # the Uno resets when the port opens
        ser.write(command)
        ser.flush()
        time.sleep(0.4)
