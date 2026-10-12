"""Small reusable widgets: cards and the status chip."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class Card(QFrame):
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(20, 16, 20, 16)
        self.layout_.setSpacing(6)
        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("cardTitle")
        if title:
            self.layout_.addWidget(self.title_label)


class StatCard(Card):
    """A title, one big value and a unit."""

    def __init__(self, title: str, unit: str, parent=None):
        super().__init__(title, parent)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.value = QLabel("--")
        self.value.setObjectName("cardValue")
        self.unit = QLabel(unit)
        self.unit.setObjectName("cardUnit")
        self.unit.setAlignment(Qt.AlignmentFlag.AlignBottom)
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


def row(*widgets: QWidget, spacing: int = 12) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    for w in widgets:
        lay.addWidget(w)
    return lay
