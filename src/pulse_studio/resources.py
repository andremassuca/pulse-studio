"""Locating bundled files, both in the source tree and in the packaged app."""

import sys
from pathlib import Path

SAMPLE_NAME = "sample_recording.csv"


def _roots() -> list[Path]:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return [base]
    return [Path(__file__).resolve().parents[2]]


def asset_path(name: str) -> Path | None:
    for root in _roots():
        p = root / "assets" / name
        if p.exists():
            return p
    return None


def sample_recording() -> Path | None:
    for root in _roots():
        for rel in (Path("sample") / SAMPLE_NAME, Path("docs") / "sample" / SAMPLE_NAME):
            p = root / rel
            if p.exists():
                return p
    return None
