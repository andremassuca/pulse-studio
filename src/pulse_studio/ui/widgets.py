"""Small reusable widgets: cards, stats, the status chip and the quality bar."""

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class Card(QFrame):
    """A rounded panel with an optional title and a header row for controls."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(18, 14, 18, 14)
        self.layout_.setSpacing(6)
        self.header = QHBoxLayout()
        self.header.setSpacing(4)
        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("cardTitle")
        if title:
            self.header.addWidget(self.title_label)
            self.header.addStretch(1)
            self.layout_.addLayout(self.header)


class StatCard(Card):
    """A title, one big value, a unit and a line of explanation."""

    def __init__(self, title: str, unit: str, parent=None):
        super().__init__(title, parent)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.value = QLabel("--")
        self.value.setObjectName("cardValue")
        self.unit = QLabel(unit)
        self.unit.setObjectName("cardUnit")
        row.addWidget(self.value)
        row.addWidget(self.unit, 0, Qt.AlignmentFlag.AlignBottom)
        row.addStretch(1)
        self.layout_.addLayout(row)
        self.hint = QLabel("")
        self.hint.setObjectName("hint")
        self.layout_.addWidget(self.hint)
        self.layout_.addStretch(1)

    def set_value(self, text: str, hint: str = "") -> None:
        self.value.setText(text)
        self.hint.setText(hint)


class MiniStat(QWidget):
    def __init__(self, title: str, unit: str = "", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        t = QLabel(title.upper())
        t.setObjectName("miniTitle")
        lay.addWidget(t)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.value = QLabel("--")
        self.value.setObjectName("valueSmall")
        self.unit = QLabel(unit)
        self.unit.setObjectName("unit")
        row.addWidget(self.value)
        row.addWidget(self.unit, 0, Qt.AlignmentFlag.AlignBottom)
        row.addStretch(1)
        lay.addLayout(row)

    def set_value(self, text: str) -> None:
        self.value.setText(text)


class Chip(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chip")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_state(self, text: str, color: str, dark: bool) -> None:
        self.setText(text)
        r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
        bg = f"rgba({r}, {g}, {b}, {0.20 if dark else 0.14})"
        self.setStyleSheet(f"QLabel#chip {{ color: {color}; background: {bg}; }}")


class QualityBar(QWidget):
    """Five segments that fill with the signal quality, like a signal meter."""

    SEGMENTS = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(12)
        self._level = 0.0
        self._color = QColor("#3DE59A")
        self._off = QColor("#222B36")

    def set_level(self, level: float, color: str, off: str) -> None:
        self._level = max(0.0, min(1.0, level))
        self._color, self._off = QColor(color), QColor(off)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        gap = 4.0
        w = (self.width() - gap * (self.SEGMENTS - 1)) / self.SEGMENTS
        lit = self._level * self.SEGMENTS
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(self.SEGMENTS):
            fill = max(0.0, min(1.0, lit - i))
            x = i * (w + gap)
            p.setBrush(self._off)
            p.drawRoundedRect(QRectF(x, 0, w, self.height()), 4, 4)
            if fill > 0:
                c = QColor(self._color)
                c.setAlphaF(0.35 + 0.65 * fill)
                p.setBrush(c)
                p.drawRoundedRect(QRectF(x, 0, w * max(fill, 0.25), self.height()), 4, 4)
        p.end()


class MetricCard(QFrame):
    """Icon and title, one big value with its unit, a divider and a description."""

    def __init__(self, title: str, unit: str = "", tint: bool = False, word: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("cardTint" if tint else "card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 14)
        lay.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.icon = QLabel()
        self.icon.setFixedSize(22, 22)
        self.icon.setScaledContents(True)
        head.addWidget(self.icon)
        self.title = QLabel(title)
        self.title.setObjectName("cardTitle")
        head.addWidget(self.title)
        head.addStretch(1)
        lay.addLayout(head)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.value = QLabel("--")
        self.value.setObjectName("word" if word else "value")
        self.unit = QLabel(unit)
        self.unit.setObjectName("unit")
        row.addWidget(self.value)
        row.addWidget(self.unit, 0, Qt.AlignmentFlag.AlignBottom)
        row.addStretch(1)
        lay.addLayout(row)
        self.extra = QVBoxLayout()
        self.extra.setSpacing(0)
        lay.addLayout(self.extra)
        lay.addStretch(1)
        line = QFrame()
        line.setObjectName("divider")
        lay.addWidget(line)
        self.desc = QLabel("")
        self.desc.setObjectName("hint")
        self.desc.setWordWrap(True)
        lay.addWidget(self.desc)

    def set_icon(self, icon: QIcon) -> None:
        self.icon.setPixmap(icon.pixmap(QSize(44, 44)))

    def set(self, value: str, desc: str = "") -> None:
        self.value.setText(value)
        self.desc.setText(desc)


class Legend(QWidget):
    """A line sample and a dot sample with their names."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self._line = QColor("#E5484D")
        self._dot = QColor("#E5484D")
        self._text = QColor("#1F1A19")

    def set_colors(self, line: str, dot: str, text: str) -> None:
        self._line, self._dot, self._text = QColor(line), QColor(dot), QColor(text)
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(300, 22)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        y = self.height() / 2
        pen = QPen(self._line, 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(2, y), QPointF(26, y))
        p.setPen(self._text)
        p.drawText(QPointF(34, y + 4.5), "Filtered PPG")
        x = 34 + p.fontMetrics().horizontalAdvance("Filtered PPG") + 28
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._dot)
        p.drawEllipse(QPointF(x, y), 5.5, 5.5)
        p.setPen(self._text)
        p.drawText(QPointF(x + 14, y + 4.5), "Detected peaks")
        p.end()


class StatusLine(QWidget):
    """A coloured dot and a short text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.dot = QLabel()
        self.dot.setFixedSize(10, 10)
        self.text = QLabel("")
        self.text.setObjectName("status")
        lay.addWidget(self.dot)
        lay.addWidget(self.text)

    def set(self, text: str, color: str) -> None:
        self.text.setText(text)
        self.text.setStyleSheet(f"color: {color};")
        self.dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
