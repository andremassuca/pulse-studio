"""The main window: sidebar, header, device controls and the pages."""

import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..acquisition import (
    ReplaySource,
    SerialSource,
    SimulatedSource,
    list_serial_ports,
    pick_default,
)
from ..recording import default_folder, list_sessions
from ..resources import sample_recording
from ..session import Session
from . import icons
from .branding import icon_pixmap
from .pages import DashboardPage, LivePage, SessionsPage, SettingsPage
from .theme import THEMES, stylesheet
from .widgets import StatusLine

DEMO_KEY = "demo"
SAMPLE_KEY = "sample"
DISPLAY_DELAY_S = 0.30  # must be larger than the peak detection latency
SCENARIOS = [
    ("Good signal", "finger"),
    ("No finger", "no_finger"),
    ("Movement", "motion"),
    ("Too much pressure", "saturated"),
]
PAGES = [
    ("Dashboard", icons.home, "Pulse Studio", "Monitor your heart rate in real time with an optical pulse sensor."),
    ("Live Signal", icons.pulse, "Live Signal", "The filtered pulse wave beat by beat, with its variability."),
    ("Sessions", icons.stack, "Sessions", "Recordings you made, ready to replay."),
    ("Settings", icons.gear, "Settings", "Appearance, recordings and startup."),
]


class PlayClock:
    """Maps wall time to signal time, a fixed delay behind the newest sample.

    Samples arrive in small bursts. Following the newest one directly would
    make the display stutter, so the offset is smoothed and the play head
    only moves forward.
    """

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._offset: float | None = None
        self.head = 0.0

    def update(self, latest: float, wall: float) -> float:
        target = wall - (latest - DISPLAY_DELAY_S)
        if self._offset is None:
            self._offset = target
            self.head = latest - DISPLAY_DELAY_S
        else:
            self._offset += 0.04 * (target - self._offset)
        head = min(wall - self._offset, latest - 0.02)
        self.head = max(self.head, head)
        return self.head


@dataclass
class Ctx:
    session: Session
    c: dict
    connected: bool
    head: float


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings):
        super().__init__()
        self.settings = settings
        self.session = Session()
        self.clock = PlayClock()
        self.paused = False
        self._pending = []  # beats waiting for the play head
        self._head = 0.0
        self._theme = "light" if settings.value("theme", "light") == "light" else "dark"
        self.setWindowTitle("Pulse Studio")
        self.resize(1440, 900)
        self.setMinimumSize(1240, 800)

        self._build()
        self._refresh_ports(initial=True)
        self._apply_theme()
        self.set_span(int(settings.value("span", 10)), save=False)
        self.set_mode(self._saved_mode(), save=False)
        self.settings_page.load(self._theme, self._mode, self.recordings_folder(),
                                str(settings.value("autoconnect", "false")).lower() == "true")
        self._go(0)

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._slow = QTimer(self)
        self._slow.setInterval(100)
        self._slow.timeout.connect(self._refresh)
        self._slow.start()

    # ---- construction ----------------------------------------------------

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_sidebar())

        content = QVBoxLayout()
        content.setContentsMargins(30, 22, 30, 12)
        content.setSpacing(14)
        content.addLayout(self._build_header())
        self.stack = QStackedWidget()
        self.dashboard = DashboardPage(self)
        self.live = LivePage(self)
        self.sessions_page = SessionsPage(self)
        self.settings_page = SettingsPage(self)
        self.pages = [self.dashboard, self.live, self.sessions_page, self.settings_page]
        for page in self.pages:
            self.stack.addWidget(page)
        content.addWidget(self.stack, 1)
        self.notice = QPushButton("")
        self.notice.setObjectName("link")
        self.notice.hide()
        self.notice.clicked.connect(self.open_recordings)
        content.addWidget(self.notice, 0, Qt.AlignmentFlag.AlignLeft)
        outer.addLayout(content, 1)

        self.heart = self.dashboard.heart

    def _build_sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(236)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(18, 22, 18, 18)
        lay.setSpacing(6)
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(icon_pixmap(64).scaled(34, 34, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))
        brand.addWidget(logo)
        name = QLabel("Pulse Studio")
        name.setObjectName("appName")
        brand.addWidget(name)
        brand.addStretch(1)
        lay.addLayout(brand)
        lay.addSpacing(26)
        self.nav_group = QButtonGroup(self)
        self.nav_buttons = []
        for i, (label, _icon, _t, _s) in enumerate(PAGES):
            b = QPushButton("  " + label)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setIconSize(b.iconSize() * 1.0)
            b.clicked.connect(lambda _=False, k=i: self._go(k))
            self.nav_group.addButton(b)
            self.nav_buttons.append(b)
            lay.addWidget(b)
        lay.addStretch(1)
        self.side_note = QLabel(f"Pulse Studio v{__version__}\nPPG · Arduino Uno\nXD-58C sensor")
        self.side_note.setObjectName("note")
        lay.addWidget(self.side_note)
        return side

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(20)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.page_title = QLabel("Pulse Studio")
        self.page_title.setObjectName("pageTitle")
        titles.addWidget(self.page_title)
        self.page_sub = QLabel("")
        self.page_sub.setObjectName("sub")
        titles.addWidget(self.page_sub)
        header.addLayout(titles, 1)

        right = QVBoxLayout()
        right.setSpacing(8)
        status = QHBoxLayout()
        status.setSpacing(16)
        status.addStretch(1)
        self.status_line = StatusLine()
        status.addWidget(self.status_line)
        self.device_label = QLabel("")
        self.device_label.setObjectName("sub")
        status.addWidget(self.device_label)
        self.rate_label = QLabel("Sampling 500 Hz")
        self.rate_label.setObjectName("sub")
        status.addWidget(self.rate_label)
        right.addLayout(status)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addStretch(1)
        self.scenario = QComboBox()
        self.scenario.setMinimumWidth(150)
        self.scenario.setToolTip("Simulated signal, to see how bad signals are detected")
        for label, key in SCENARIOS:
            self.scenario.addItem(label, key)
        self.scenario.currentIndexChanged.connect(self._scenario_changed)
        self.scenario.hide()
        controls.addWidget(self.scenario)
        self.port_box = QComboBox()
        self.port_box.currentIndexChanged.connect(self._port_changed)
        controls.addWidget(self.port_box)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("outline")
        self.refresh_btn.clicked.connect(lambda: self._refresh_ports())
        controls.addWidget(self.refresh_btn)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("primary")
        self.connect_btn.setMinimumWidth(110)
        self.connect_btn.clicked.connect(self.toggle_connection)
        controls.addWidget(self.connect_btn)
        right.addLayout(controls)
        header.addLayout(right)
        return header

    # ---- navigation and theme -------------------------------------------

    def _go(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.nav_buttons[index].setChecked(True)
        _label, _icon, title, sub = PAGES[index]
        self.page_title.setText(title)
        self.page_sub.setText(sub)
        if self.pages[index] is self.sessions_page:
            self.sessions_page.reload()

    def _apply_theme(self) -> None:
        c = THEMES[self._theme]
        self.setStyleSheet(stylesheet(c))
        for page in self.pages:
            page.apply_theme(c)
        for b, (_l, icon, _t, _s) in zip(self.nav_buttons, PAGES):
            b.setIcon(icon(c["text"]))
        self._refresh()

    def set_theme(self, name: str) -> None:
        self._theme = name if name in THEMES else "light"
        self.settings.setValue("theme", self._theme)
        box = self.settings_page.theme_box
        box.blockSignals(True)
        box.setCurrentIndex(max(0, box.findData(self._theme)))
        box.blockSignals(False)
        if not self.settings.contains("mode"):
            self.set_mode(self._saved_mode(), save=False)
        self._apply_theme()

    def _saved_mode(self) -> str:
        saved = self.settings.value("mode")
        if saved in ("scroll", "sweep"):
            return str(saved)
        return "scroll" if self._theme == "light" else "sweep"

    def set_span(self, seconds: int, save: bool = True) -> None:
        if seconds not in (5, 10, 30):
            seconds = 10
        for page in (self.dashboard, self.live):
            page.controls.span_buttons[seconds].setChecked(True)
            page.wave.set_span(float(seconds))
        if save:
            self.settings.setValue("span", seconds)

    def set_mode(self, mode: str, save: bool = True) -> None:
        self._mode = mode if mode in ("scroll", "sweep") else "scroll"
        for page in (self.dashboard, self.live):
            page.wave.set_mode(self._mode)
        for key, b in self.live.controls.mode_buttons.items():
            b.setChecked(key == self._mode)
        if hasattr(self, "settings_page"):
            box = self.settings_page.mode_box
            box.blockSignals(True)
            box.setCurrentIndex(max(0, box.findData(self._mode)))
            box.blockSignals(False)
        if save:
            self.settings.setValue("mode", self._mode)

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        if not self.paused:
            self.clock.reset()
            self._pending.clear()
        self._refresh()

    # ---- connection ------------------------------------------------------

    def _refresh_ports(self, initial: bool = False) -> None:
        current = self.port_box.currentData()
        remembered = self.settings.value("port") if initial else current
        self.port_box.blockSignals(True)
        self.port_box.clear()
        ports = list_serial_ports()
        for p in ports:
            self.port_box.addItem(p.label + ("  (Arduino)" if p.is_arduino else ""), p.device)
        self.port_box.addItem("Demo (simulated signal)", DEMO_KEY)
        if sample_recording() is not None:
            self.port_box.addItem("Demo (recorded sample)", SAMPLE_KEY)
        choice = pick_default(ports, remembered if remembered not in (DEMO_KEY, SAMPLE_KEY) else None)
        saved_demo = self.port_box.findData(remembered) if remembered in (DEMO_KEY, SAMPLE_KEY) else -1
        if saved_demo >= 0:
            self.port_box.setCurrentIndex(saved_demo)
        elif choice is None:
            self.port_box.setCurrentIndex(self.port_box.findData(DEMO_KEY))
        else:
            self.port_box.setCurrentIndex(self.port_box.findData(choice.device))
        self.port_box.blockSignals(False)
        self._port_changed()
        self._has_arduino = any(p.is_arduino or p.is_clone for p in ports)

    def _port_changed(self) -> None:
        self.scenario.setVisible(self.port_box.currentData() == DEMO_KEY)

    def _repolish(self, widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _notify(self, text: str) -> None:
        self.notice.setText(text)
        self.notice.setVisible(bool(text))

    def toggle_connection(self) -> None:
        if self.session.active:
            self.disconnect_source()
            return
        key = self.port_box.currentData()
        try:
            if key == DEMO_KEY:
                source = SimulatedSource()
                source.mode = self.scenario.currentData()
            elif key == SAMPLE_KEY:
                source = ReplaySource(sample_recording())
            else:
                source = SerialSource(key, self.port_box.currentText())
            self._start(source)
        except RuntimeError as exc:
            self._notify(str(exc))
            return
        self.settings.setValue("port", key)

    def autoconnect(self, force: bool = False) -> None:
        """Connects at start-up: when forced, or when the setting is on and an Arduino is plugged in."""
        wanted = force or str(self.settings.value("autoconnect", "false")).lower() == "true"
        if not wanted or self.session.active:
            return
        if force or (self._has_arduino and self.port_box.currentData() not in (DEMO_KEY, SAMPLE_KEY)):
            self.toggle_connection()

    def _start(self, source) -> None:
        self.session.start(source)
        self._notify("")
        self.clock.reset()
        self._pending.clear()
        self.paused = False
        for page in (self.dashboard, self.live):
            page.wave.clear_view()
        self.connect_btn.setText("Disconnect")
        self.connect_btn.setObjectName("outline")
        self._repolish(self.connect_btn)
        self.port_box.setEnabled(False)
        self.refresh_btn.setEnabled(False)

    def disconnect_source(self) -> None:
        if self.session.recorder is not None:
            self.toggle_recording()
        self.session.stop()
        self.paused = False
        self.connect_btn.setText("Connect")
        self.connect_btn.setObjectName("primary")
        self._repolish(self.connect_btn)
        self.port_box.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.heart.set_active(False)
        self.heart.update()

    def replay_file(self, path: Path) -> None:
        if self.session.active:
            self.disconnect_source()
        try:
            self._start(ReplaySource(path))
        except (OSError, ValueError, KeyError) as exc:
            self._notify(f"Could not open {path.name}: {exc}")
            return
        self._go(1)

    def _scenario_changed(self) -> None:
        src = self.session.source
        if isinstance(src, SimulatedSource):
            src.mode = self.scenario.currentData()

    # ---- recording -------------------------------------------------------

    def recordings_folder(self) -> Path:
        saved = self.settings.value("record_folder")
        return Path(saved) if saved else default_folder()

    def toggle_recording(self) -> None:
        if not self.session.active:
            return
        if self.session.recorder is None:
            self.session.start_recording(self.recordings_folder())
            self._notify("")
        else:
            paths = self.session.stop_recording()
            if paths:
                self._notify(f"Saved {paths[0].name}. Click to open the folder.")
        self._refresh()

    def export_buffer(self) -> None:
        if not self.session.active or self.session.t.size == 0:
            self._notify("Nothing to export yet. Connect the sensor first.")
            return
        folder = self.recordings_folder()
        folder.mkdir(parents=True, exist_ok=True)
        default = folder / f"pulse_export_{datetime.now():%Y%m%d_%H%M%S}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export the last minute", str(default), "CSV (*.csv)")
        if path:
            n = self.session.export_buffer(Path(path))
            self._notify(f"Exported {n} samples to {Path(path).name}. Click to open the folder.")

    def open_recordings(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.recordings_folder())))

    def last_session_text(self) -> str:
        now = time.monotonic()
        if now - getattr(self, "_last_check", 0.0) > 5.0:
            self._last_check = now
            found = list_sessions(self.recordings_folder())
            self._last_text = ""
            if found and found[0].started:
                self._last_text = "Last session\n" + found[0].started.strftime("%d %b %Y, %H:%M")
        return getattr(self, "_last_text", "")

    # ---- frame and card updates -----------------------------------------

    def _ctx(self) -> Ctx:
        return Ctx(self.session, THEMES[self._theme], self.session.active, self._head)

    def _tick(self) -> None:
        s = self.session
        if not s.active:
            return
        if s.error:
            err = s.error
            self.disconnect_source()
            self._notify(err)
            return
        new = s.poll()
        if self.paused or s.t.size == 0:
            return
        self._pending.extend(new)
        self._head = self.clock.update(s.latest_t, time.perf_counter())

        steady = s.metrics.bpm is not None
        while self._pending and self._pending[0].t <= self._head:
            beat = self._pending.pop(0)
            if steady and beat.valid:
                self.heart.pulse()
        self.heart.set_active(steady)
        self.pages[self.stack.currentIndex()].draw(self._ctx())

    def _refresh(self) -> None:
        c = THEMES[self._theme]
        s = self.session
        if s.active:
            kind = {"demo": "Demo running", "sample": "Replaying a recording"}.get(
                self.port_box.currentData(), "Sensor connected")
            if isinstance(s.source, ReplaySource) and self.port_box.currentData() not in (DEMO_KEY, SAMPLE_KEY):
                kind = "Replaying a recording"
            self.status_line.set(kind, c["good"])
            desc = re.sub(r"\s*\((COM\d+)\)", r" · \1", getattr(s.source, "description", ""))
            fw = getattr(s.source, "firmware_version", None)
            self.device_label.setText(desc + (f"  ·  fw {fw}" if fw and fw not in ("demo", "sample") else ""))
        else:
            self.status_line.set("Not connected", c["idle"])
            self.device_label.setText("")
        ctx = self._ctx()
        for page in self.pages:
            page.refresh(ctx)

    def closeEvent(self, event) -> None:
        self.settings.setValue("geometry", self.saveGeometry())
        self.session.stop()
        super().closeEvent(event)
