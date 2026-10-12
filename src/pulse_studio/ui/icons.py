"""Small line icons drawn with QPainter, so they follow the theme colours."""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def _canvas(size: int):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pm, p


def _pen(color: str, size: int) -> QPen:
    pen = QPen(QColor(color), size * 0.085)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _finish(pm: QPixmap, p: QPainter) -> QIcon:
    p.end()
    return QIcon(pm)


def home(color: str, size: int = 44) -> QIcon:
    pm, p = _canvas(size)
    p.setPen(_pen(color, size))
    s = size
    path = QPainterPath()
    path.moveTo(s * 0.18, s * 0.48)
    path.lineTo(s * 0.50, s * 0.20)
    path.lineTo(s * 0.82, s * 0.48)
    path.moveTo(s * 0.26, s * 0.44)
    path.lineTo(s * 0.26, s * 0.80)
    path.lineTo(s * 0.74, s * 0.80)
    path.lineTo(s * 0.74, s * 0.44)
    p.drawPath(path)
    p.drawLine(QPointF(s * 0.44, s * 0.80), QPointF(s * 0.44, s * 0.58))
    p.drawLine(QPointF(s * 0.56, s * 0.80), QPointF(s * 0.56, s * 0.58))
    p.drawLine(QPointF(s * 0.44, s * 0.58), QPointF(s * 0.56, s * 0.58))
    return _finish(pm, p)


def pulse(color: str, size: int = 44) -> QIcon:
    pm, p = _canvas(size)
    p.setPen(_pen(color, size))
    s = size
    pts = [(0.10, 0.52), (0.30, 0.52), (0.40, 0.28), (0.52, 0.78), (0.62, 0.40), (0.68, 0.52), (0.90, 0.52)]
    for a, b in zip(pts, pts[1:]):
        p.drawLine(QPointF(a[0] * s, a[1] * s), QPointF(b[0] * s, b[1] * s))
    return _finish(pm, p)


def stack(color: str, size: int = 44) -> QIcon:
    pm, p = _canvas(size)
    p.setPen(_pen(color, size))
    s = size
    x0, x1, w = s * 0.22, s * 0.78, s * 0.56
    for i, y in enumerate((0.28, 0.50, 0.72)):
        top = QRectF(x0, s * (y - 0.08), w, s * 0.16)
        if i == 0:
            p.drawEllipse(top)
        else:
            p.drawArc(top, 180 * 16, 180 * 16)
    p.drawLine(QPointF(x0, s * 0.28), QPointF(x0, s * 0.72))
    p.drawLine(QPointF(x1, s * 0.28), QPointF(x1, s * 0.72))
    p.drawArc(QRectF(x0, s * 0.64, w, s * 0.16), 180 * 16, 180 * 16)
    return _finish(pm, p)


def gear(color: str, size: int = 44) -> QIcon:
    pm, p = _canvas(size)
    p.setPen(_pen(color, size))
    s = size
    c = QPointF(s / 2, s / 2)
    p.drawEllipse(c, s * 0.15, s * 0.15)
    p.drawEllipse(c, s * 0.28, s * 0.28)
    for k in range(8):
        a = k * math.pi / 4
        p.drawLine(
            QPointF(c.x() + math.cos(a) * s * 0.28, c.y() + math.sin(a) * s * 0.28),
            QPointF(c.x() + math.cos(a) * s * 0.38, c.y() + math.sin(a) * s * 0.38),
        )
    return _finish(pm, p)


def heart_outline(color: str, size: int = 44) -> QIcon:
    pm, p = _canvas(size)
    p.setPen(_pen(color, size))
    s = size
    path = QPainterPath()
    path.moveTo(s * 0.5, s * 0.80)
    path.cubicTo(s * 0.12, s * 0.55, s * 0.12, s * 0.22, s * 0.32, s * 0.22)
    path.cubicTo(s * 0.42, s * 0.22, s * 0.48, s * 0.28, s * 0.5, s * 0.34)
    path.cubicTo(s * 0.52, s * 0.28, s * 0.58, s * 0.22, s * 0.68, s * 0.22)
    path.cubicTo(s * 0.88, s * 0.22, s * 0.88, s * 0.55, s * 0.5, s * 0.80)
    p.drawPath(path)
    return _finish(pm, p)


def bars(color: str, size: int = 44) -> QIcon:
    pm, p = _canvas(size)
    p.setPen(_pen(color, size))
    s = size
    for x, h in ((0.28, 0.25), (0.42, 0.40), (0.56, 0.55), (0.70, 0.70)):
        p.drawLine(QPointF(s * x, s * 0.82), QPointF(s * x, s * (0.82 - h * 0.7)))
    return _finish(pm, p)


def clock(color: str, size: int = 44) -> QIcon:
    pm, p = _canvas(size)
    p.setPen(_pen(color, size))
    s = size
    c = QPointF(s / 2, s / 2)
    p.drawEllipse(c, s * 0.30, s * 0.30)
    p.drawLine(c, QPointF(s * 0.5, s * 0.30))
    p.drawLine(c, QPointF(s * 0.64, s * 0.56))
    return _finish(pm, p)
