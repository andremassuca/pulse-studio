"""Finding the serial port of the Arduino."""

from dataclasses import dataclass

from serial.tools import list_ports

# USB vendor ids of Arduino boards and of the usual USB-serial chips on clones.
ARDUINO_VIDS = {0x2341, 0x2A03}
CLONE_VIDS = {0x1A86, 0x0403, 0x10C4}  # CH340, FTDI, CP210x


@dataclass(frozen=True)
class PortInfo:
    device: str
    description: str
    is_arduino: bool
    is_clone: bool

    @property
    def label(self) -> str:
        return f"{self.device}  {self.description}"


def list_serial_ports() -> list[PortInfo]:
    """All serial ports, Arduinos first. Bluetooth virtual ports are skipped."""
    found: list[PortInfo] = []
    for p in list_ports.comports():
        if (p.hwid or "").upper().startswith("BTHENUM"):
            continue
        is_arduino = p.vid in ARDUINO_VIDS
        is_clone = p.vid in CLONE_VIDS
        found.append(PortInfo(p.device, p.description or p.device, is_arduino, is_clone))
    found.sort(key=lambda p: (not p.is_arduino, not p.is_clone, p.device))
    return found


def pick_default(ports: list[PortInfo], remembered: str | None = None) -> PortInfo | None:
    if remembered:
        for p in ports:
            if p.device == remembered:
                return p
    for p in ports:
        if p.is_arduino or p.is_clone:
            return p
    return ports[0] if ports else None
