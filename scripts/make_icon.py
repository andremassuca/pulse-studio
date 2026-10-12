"""Renders the app icon to assets/icon.png and assets/icon.ico.

Run from the project root: python scripts/make_icon.py
"""

import io
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QGuiApplication

from pulse_studio.ui.branding import ICON_SIZES, icon_pixmap


def to_pil(size: int) -> Image.Image:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    icon_pixmap(size).save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA")


def main() -> None:
    app = QGuiApplication(sys.argv)
    out = Path(__file__).resolve().parent.parent / "assets"
    out.mkdir(exist_ok=True)
    images = [to_pil(s) for s in ICON_SIZES]
    images[-1].save(out / "icon.png")
    images[-1].save(
        out / "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in ICON_SIZES],
        append_images=images[:-1],
    )
    print("wrote", out / "icon.ico")
    del app


if __name__ == "__main__":
    main()
