"""The illustrated heart: one shape shared by the interface and the app icon."""

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


def heart_path() -> QPainterPath:
    """Heart centred on the origin, about 2 units wide and 2 units tall."""
    p = QPainterPath()
    p.moveTo(0.0, 0.92)
    p.cubicTo(-0.30, 0.66, -1.02, 0.22, -1.02, -0.36)
    p.cubicTo(-1.02, -0.86, -0.50, -1.04, 0.0, -0.52)
    p.cubicTo(0.50, -1.04, 1.02, -0.86, 1.02, -0.36)
    p.cubicTo(1.02, 0.22, 0.30, 0.66, 0.0, 0.92)
    p.closeSubpath()
    return p


def paint_heart(painter: QPainter, size: float, top: QColor, bottom: QColor, highlight: bool = True) -> None:
    """Draws the heart centred on the origin, scaled so it is `size` wide."""
    painter.save()
    painter.scale(size / 2.1, size / 2.1)
    path = heart_path()
    grad = QLinearGradient(QPointF(-0.6, -1.0), QPointF(0.6, 1.0))
    grad.setColorAt(0.0, top)
    grad.setColorAt(1.0, bottom)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(grad))
    painter.drawPath(path)
    if highlight:
        shine = QPainterPath()
        shine.moveTo(-0.72, -0.30)
        shine.cubicTo(-0.74, -0.62, -0.52, -0.78, -0.30, -0.66)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor(255, 255, 255, 120), 0.07)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawPath(shine)
    painter.restore()


class HeartWidget(QWidget):
    """Contracts on each detected beat and relaxes until the next one.

    The caller calls pulse() at the moment the peak is shown on the plot. The
    scale follows a fast attack and an exponential release, so the motion is
    continuous and never jumps.
    """

    ATTACK_S = 0.07
    RELEASE_TAU_S = 0.26
    DEPTH = 0.15

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(190, 190)
        self._last_pulse = -10.0
        self._active = False
        self._top = QColor("#FF6B81")
        self._bottom = QColor("#D3243E")
        self._idle = QColor("#B9BFCD")
        self._glow = QColor("#FF5A74")

    def set_colors(self, top: str, bottom: str, idle: str, glow: str) -> None:
        self._top, self._bottom = QColor(top), QColor(bottom)
        self._idle, self._glow = QColor(idle), QColor(glow)
        self.update()

    def set_active(self, active: bool) -> None:
        if active != self._active:
            self._active = active
            self.update()

    def pulse(self) -> None:
        self._last_pulse = time.perf_counter()
        self._active = True

    def _contraction(self, dt: float) -> float:
        if dt < 0:
            return 0.0
        if dt < self.ATTACK_S:
            x = dt / self.ATTACK_S
            return 1.0 - (1.0 - x) ** 3  # ease out
        return math.exp(-(dt - self.ATTACK_S) / self.RELEASE_TAU_S)

    def paintEvent(self, _event) -> None:
        dt = time.perf_counter() - self._last_pulse
        c = self._contraction(dt) if self._active else 0.0
        scale = 1.0 - self.DEPTH * c

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self.width() / 2, self.height() / 2 + 4)
        base = min(self.width(), self.height()) * 0.66

        if self._active and dt < 0.7:
            ring = dt / 0.7
            color = QColor(self._glow)
            color.setAlphaF(0.30 * (1.0 - ring) ** 2)
            p.setPen(Qt.PenStyle.NoPen)
            glow = QRadialGradient(QPointF(0, 0), base * (0.55 + 0.5 * ring))
            glow.setColorAt(0.0, color)
            transparent = QColor(color)
            transparent.setAlpha(0)
            glow.setColorAt(1.0, transparent)
            p.setBrush(QBrush(glow))
            p.drawEllipse(QRectF(-base, -base, 2 * base, 2 * base))

        p.scale(scale, scale)
        if self._active:
            paint_heart(p, base, self._top, self._bottom)
        else:
            paint_heart(p, base, self._idle, self._idle.darker(112), highlight=False)
        p.end()
