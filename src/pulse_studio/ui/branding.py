"""App icon and splash screen, drawn from the same heart as the interface."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSplashScreen

from .heart import paint_heart

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def icon_pixmap(size: int) -> QPixmap:
    """Rounded dark tile with the heart and a pulse line."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    tile = QLinearGradient(0, 0, size, size)
    tile.setColorAt(0.0, QColor("#232C44"))
    tile.setColorAt(1.0, QColor("#0C101A"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(tile)
    r = size * 0.22
    p.drawRoundedRect(QRectF(0, 0, size, size), r, r)

    p.translate(size / 2, size * 0.47)
    paint_heart(p, size * 0.60, QColor("#FF7A8E"), QColor("#D3243E"), highlight=size >= 48)
    p.resetTransform()

    if size >= 32:
        pen = QPen(QColor(255, 255, 255, 235), max(1.2, size * 0.032))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        y = size * 0.50
        x0, x1 = size * 0.20, size * 0.80
        w = x1 - x0
        pts = [(0.0, 0), (0.28, 0), (0.38, -0.10), (0.47, 0.12), (0.56, -0.20), (0.65, 0.0), (1.0, 0)]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            p.drawLine(int(x0 + ax * w), int(y + ay * size),
                       int(x0 + bx * w), int(y + by * size))
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for s in ICON_SIZES:
        icon.addPixmap(icon_pixmap(s))
    return icon


def make_splash() -> QSplashScreen:
    w, h = 460, 260
    pm = QPixmap(w, h)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    bg = QLinearGradient(0, 0, w, h)
    bg.setColorAt(0.0, QColor("#1A2136"))
    bg.setColorAt(1.0, QColor("#0C101A"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(QRectF(0, 0, w, h), 22, 22)
    p.save()
    p.translate(w * 0.5, 100)
    paint_heart(p, 104, QColor("#FF7A8E"), QColor("#D3243E"))
    p.restore()
    p.setPen(QColor("#EEF1F8"))
    font = p.font()
    font.setFamily("Segoe UI Variable Display")
    font.setPixelSize(26)
    font.setWeight(font.Weight.DemiBold)
    p.setFont(font)
    p.drawText(QRectF(0, 168, w, 40), Qt.AlignmentFlag.AlignCenter, "Pulse Studio")
    font.setPixelSize(12)
    font.setWeight(font.Weight.Normal)
    p.setFont(font)
    p.setPen(QColor("#8D96AC"))
    p.drawText(QRectF(0, 208, w, 24), Qt.AlignmentFlag.AlignCenter, "Starting...")
    p.end()
    splash = QSplashScreen(pm, Qt.WindowType.WindowStaysOnTopHint)
    return splash
