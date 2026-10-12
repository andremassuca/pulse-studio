"""The illustrated heart.

paint_heart_icon is the flat heart used by the app icon and the splash screen.
HeartWidget draws a more anatomical heart for the main window: ventricles with
shading, aorta, pulmonary artery, vena cava and coronary arteries. It
contracts on each detected beat, and the great arteries swell a moment later,
like a pressure wave leaving the heart.
"""

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import QWidget


# ---- flat heart (icon, splash) ------------------------------------------


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
    """Flat heart centred on the origin, scaled so it is `size` wide."""
    painter.save()
    painter.scale(size / 2.1, size / 2.1)
    grad = QLinearGradient(QPointF(-0.6, -1.0), QPointF(0.6, 1.0))
    grad.setColorAt(0.0, top)
    grad.setColorAt(1.0, bottom)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(grad))
    painter.drawPath(heart_path())
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


# ---- anatomical heart -----------------------------------------------------


def _path(*segments) -> QPainterPath:
    p = QPainterPath()
    p.moveTo(*segments[0])
    for seg in segments[1:]:
        p.cubicTo(*seg)
    return p


def _body_path() -> QPainterPath:
    p = _path(
        (-0.15, -0.50),
        (-0.30, -0.80, -0.95, -0.75, -0.92, -0.15),
        (-0.90, 0.35, -0.45, 0.70, -0.12, 1.02),
        (0.20, 0.75, 0.88, 0.40, 0.90, -0.10),
        (0.92, -0.70, 0.35, -0.80, 0.15, -0.50),
        (0.08, -0.42, -0.08, -0.42, -0.15, -0.50),
    )
    p.closeSubpath()
    return p


AORTA = _path((0.12, -0.40), (0.12, -0.95, 0.30, -1.20, 0.55, -1.10), (0.78, -1.02, 0.72, -0.70, 0.66, -0.38))
AORTA_BRANCHES = [
    _path((0.26, -1.02), (0.27, -1.12, 0.27, -1.22, 0.26, -1.30)),
    _path((0.42, -1.12), (0.45, -1.20, 0.47, -1.28, 0.48, -1.34)),
]
PULMONARY = _path((-0.12, -0.40), (-0.20, -0.80, -0.30, -0.95, -0.48, -1.05))
PULMONARY_BRANCH = _path((-0.48, -1.05), (-0.65, -1.12, -0.85, -1.05, -1.00, -0.92))
VENA_CAVA = _path((0.62, -0.30), (0.70, -0.65, 0.88, -0.90, 0.94, -1.25))
CORONARIES = [
    (_path((0.05, -0.50), (0.00, -0.10, -0.02, 0.35, -0.10, 0.80)), 0.040),  # front descending
    (_path((-0.10, -0.48), (-0.40, -0.40, -0.68, -0.20, -0.76, 0.22)), 0.038),  # circumflex
    (_path((0.20, -0.52), (0.55, -0.45, 0.78, -0.15, 0.70, 0.35)), 0.038),  # right
    (_path((-0.02, -0.05), (-0.20, -0.02, -0.35, 0.10, -0.42, 0.34)), 0.026),
    (_path((0.03, 0.20), (0.20, 0.22, 0.36, 0.34, 0.42, 0.52)), 0.026),
    (_path((-0.50, -0.30), (-0.62, -0.42, -0.72, -0.50, -0.78, -0.58)), 0.024),
]


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
        round(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


class HeartPalette:
    """Colours of the anatomical heart. `life` fades them to grey when idle."""

    def __init__(self):
        self.body_light = QColor("#FF7A80")
        self.body_mid = QColor("#D12F3C")
        self.body_dark = QColor("#6E0C18")
        self.artery = QColor("#D8323E")
        self.vein_light = QColor("#6F8FD8")
        self.vein_dark = QColor("#2C4796")
        self.coronary = QColor("#FF5A5A")
        self.glow = QColor("#FF5A74")
        self.shade = 1.0  # strength of the inner shadows

    @classmethod
    def studio(cls) -> "HeartPalette":
        """Softer coral tones for the light theme."""
        pal = cls()
        pal.body_light = QColor("#FFD6CF")
        pal.body_mid = QColor("#F4908F")
        pal.body_dark = QColor("#D2606B")
        pal.artery = QColor("#F07C7E")
        pal.vein_light = QColor("#B4C4E6")
        pal.vein_dark = QColor("#6B83BC")
        pal.coronary = QColor("#CB4450")
        pal.glow = QColor("#E5484D")
        pal.shade = 0.35
        return pal

    def faded(self, life: float) -> "HeartPalette":
        grey = QColor("#9AA3B5")
        out = HeartPalette()
        for name in ("body_light", "body_mid", "body_dark", "artery", "vein_light", "vein_dark", "coronary"):
            base = getattr(self, name)
            dark = _mix(grey, QColor("#2A3040"), 0.6 if "dark" in name else 0.0)
            setattr(out, name, _mix(dark, base, life))
        out.glow = self.glow
        out.shade = self.shade
        return out


def _tube(p: QPainter, path: QPainterPath, width: float, dark: QColor, mid: QColor, light: QColor) -> None:
    pen = QPen(dark, width + 0.07)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    pen = QPen(mid, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawPath(path)
    pen = QPen(light, width * 0.28)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.save()
    p.translate(-width * 0.18, -width * 0.12)
    p.drawPath(path)
    p.restore()


def paint_anatomical_heart(
    p: QPainter, size: float, squeeze: float, pulse: float, palette: HeartPalette, life: float = 1.0
) -> None:
    """Draws the heart centred on the origin, `size` units tall overall.

    squeeze (0-1) is how contracted the ventricles are; pulse (0-1) is the
    swelling of the great arteries.
    """
    pal = palette.faded(life) if life < 1.0 else palette
    p.save()
    p.scale(size / 2.6, size / 2.6)
    p.translate(0.0, 0.18)

    # Soft contact shadow.
    shadow = QRadialGradient(QPointF(0.0, 1.2), 0.9)
    shadow.setColorAt(0.0, QColor(0, 0, 0, 70))
    shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(shadow))
    p.drawEllipse(QRectF(-0.9, 1.05, 1.8, 0.28))

    # Great vessels, behind the ventricles. The arteries swell with the pulse.
    swell = 1.0 + 0.38 * pulse
    vein_mid = _mix(pal.vein_dark, pal.vein_light, 0.45)
    _tube(p, VENA_CAVA, 0.16, pal.vein_dark, vein_mid, pal.vein_light)
    _tube(p, PULMONARY_BRANCH, 0.13 * (1 + 0.15 * pulse), pal.vein_dark, vein_mid, pal.vein_light)
    _tube(p, PULMONARY, 0.20 * (1 + 0.2 * pulse), pal.vein_dark, vein_mid, pal.vein_light)
    art_dark = _mix(pal.body_dark, pal.artery, 0.35)
    for branch in AORTA_BRANCHES:
        _tube(p, branch, 0.075 * swell, art_dark, pal.artery, pal.body_light)
    _tube(p, AORTA, 0.23 * swell, art_dark, pal.artery, pal.body_light)

    # Ventricles: squeeze toward the apex.
    p.save()
    p.translate(-0.05, 0.25)
    p.scale(1.0 - 0.10 * squeeze, 1.0 - 0.075 * squeeze)
    p.translate(0.05, -0.25)
    body = _body_path()

    tone = 1.0 - 0.18 * squeeze  # blanching: the muscle darkens a little when it tightens
    grad = QRadialGradient(QPointF(-0.38, -0.35), 1.55)
    grad.setColorAt(0.0, _mix(QColor(0, 0, 0), pal.body_light, tone))
    grad.setColorAt(0.45, _mix(QColor(0, 0, 0), pal.body_mid, tone))
    grad.setColorAt(1.0, _mix(QColor(0, 0, 0), pal.body_dark, 0.8 + 0.2 * tone))
    p.setPen(QPen(_mix(QColor(0, 0, 0), pal.body_dark, 0.9 if pal.shade > 0.5 else 0.97), 0.025))
    p.setBrush(QBrush(grad))
    p.drawPath(body)

    p.setClipPath(body)
    # Interventricular groove and a soft inner shadow on the lower right.
    groove = _path((0.02, -0.46), (-0.02, 0.0, -0.06, 0.5, -0.12, 1.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(60, 0, 8, int(120 * pal.shade)), 0.07, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawPath(groove)
    rim = QRadialGradient(QPointF(0.55, 0.55), 1.1)
    rim.setColorAt(0.0, QColor(30, 0, 6, 0))
    rim.setColorAt(1.0, QColor(30, 0, 6, int(110 * pal.shade)))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(rim))
    p.drawPath(body)

    # Coronary arteries on the surface.
    for path, width in CORONARIES:
        pen = QPen(QColor(70, 0, 8, 170), width + 0.022)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        pen = QPen(pal.coronary, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawPath(path)

    # Glossy highlight.
    gloss = QPainterPath()
    gloss.moveTo(-0.78, -0.35)
    gloss.cubicTo(-0.80, -0.62, -0.50, -0.72, -0.28, -0.60)
    gloss.cubicTo(-0.46, -0.52, -0.62, -0.34, -0.66, -0.05)
    gloss.cubicTo(-0.72, -0.12, -0.78, -0.22, -0.78, -0.35)
    gl = QLinearGradient(QPointF(-0.7, -0.7), QPointF(-0.4, -0.1))
    gl.setColorAt(0.0, QColor(255, 255, 255, 150))
    gl.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(gl))
    p.drawPath(gloss)
    p.setClipping(False)

    # Atrial appendages, over the top edge of the body.
    for cx, cy, rot in ((-0.62, -0.50, -25.0), (0.60, -0.46, 22.0)):
        p.save()
        p.translate(cx, cy)
        p.rotate(rot)
        lobe = QPainterPath()
        lobe.addEllipse(QRectF(-0.26, -0.13, 0.52, 0.26))
        lg = QRadialGradient(QPointF(-0.08, -0.05), 0.35)
        lg.setColorAt(0.0, _mix(QColor(0, 0, 0), pal.body_mid, tone))
        lg.setColorAt(1.0, _mix(QColor(0, 0, 0), pal.body_dark, 0.9))
        p.setBrush(QBrush(lg))
        p.setPen(QPen(_mix(QColor(0, 0, 0), pal.body_dark, 0.9), 0.02))
        p.drawPath(lobe)
        p.restore()
    p.restore()
    p.restore()


class HeartWidget(QWidget):
    """Contracts on each detected beat and relaxes until the next one.

    The caller calls pulse() at the moment the peak is shown on the plot. The
    contraction has a fast attack and an exponential release, followed by a
    smaller second contraction (the "dub" of lub-dub). The arteries swell with
    a short delay. Nothing jumps: every value is a continuous function of the
    time since the beat.
    """

    ATTACK_S = 0.07
    RELEASE_TAU_S = 0.20
    DUB_AT_S = 0.34
    DUB_GAIN = 0.28
    ARTERY_DELAY_S = 0.07

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(210, 230)
        self._last_pulse = -10.0
        self._active = False
        self._life = 0.0  # 0 idle (grey) to 1 alive, eased
        self._last_paint = time.perf_counter()
        self.palette_ = HeartPalette()

    def set_theme(self, name: str) -> None:
        self.palette_ = HeartPalette.studio() if name == "light" else HeartPalette()
        self.update()

    def set_active(self, active: bool) -> None:
        self._active = active

    def pulse(self) -> None:
        self._last_pulse = time.perf_counter()
        self._active = True

    def _envelope(self, dt: float) -> float:
        if dt < 0:
            return 0.0
        if dt < self.ATTACK_S:
            x = dt / self.ATTACK_S
            return 1.0 - (1.0 - x) ** 3  # ease out
        return math.exp(-(dt - self.ATTACK_S) / self.RELEASE_TAU_S)

    def _beat(self, dt: float) -> float:
        main = self._envelope(dt)
        dub = self.DUB_GAIN * self._envelope(dt - self.DUB_AT_S)
        return min(1.0, main + dub)

    def paintEvent(self, _event) -> None:
        now = time.perf_counter()
        step = min(0.1, now - self._last_paint)
        self._last_paint = now
        target = 1.0 if self._active else 0.0
        self._life += (target - self._life) * min(1.0, step * 5.0)

        dt = now - self._last_pulse
        squeeze = self._beat(dt) if self._active else 0.0
        pulse = self._beat(dt - self.ARTERY_DELAY_S) if self._active else 0.0

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self.width() / 2, self.height() / 2 + 6)
        size = min(self.width() * 1.05, self.height() * 0.98)

        if self._life > 0.05 and dt < 0.8:
            ring = dt / 0.8
            color = QColor(self.palette_.glow)
            color.setAlphaF(0.34 * (1.0 - ring) ** 2 * self._life)
            r = size * (0.42 + 0.38 * ring)
            glow = QRadialGradient(QPointF(0, 0), r)
            glow.setColorAt(0.0, color)
            transparent = QColor(color)
            transparent.setAlpha(0)
            glow.setColorAt(1.0, transparent)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(glow))
            p.drawEllipse(QRectF(-r, -r, 2 * r, 2 * r))

        paint_anatomical_heart(p, size, squeeze, pulse, self.palette_, life=self._life)
        p.end()
