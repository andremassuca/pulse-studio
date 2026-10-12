"""The main window."""

import time
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..acquisition import (
    ReplaySource,
    SerialSource,
    SimulatedSource,
    list_serial_ports,
    pick_default,
)
from ..resources import sample_recording
from ..dsp import SignalState
from ..recording import default_folder
from ..session import Session
from .heart import HeartWidget
from .plots import TachoPlot, WavePlot
from .theme import THEMES, stylesheet
from .widgets import Card, Chip, StatCard

DEMO_KEY = "demo"
SAMPLE_KEY = "sample"
DISPLAY_DELAY_S = 0.28  # must be larger than the peak detection latency
SCENARIOS = [
    ("Good signal", "finger"),
    ("No finger", "no_finger"),
    ("Movement", "motion"),
    ("Too much pressure", "saturated"),
]
STATE_TEXT = {
    SignalState.WARMING_UP: ("Warming up", "idle"),
    SignalState.NO_FINGER: ("No finger detected", "bad"),
    SignalState.MOTION: ("Movement detected", "warn"),
    SignalState.SATURATED: ("Sensor saturated, ease the pressure", "bad"),
    SignalState.POOR: ("Weak signal", "warn"),
    SignalState.GOOD: ("Good signal", "good"),
}
DISCLAIMER = (
    "PPG measures blood volume changes optically, not the electrical activity of the heart. "
    "The heart animation is illustrative. Pulse Studio is not a medical device."
)


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


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings):
        super().__init__()
        self.settings = settings
        self.session = Session()
        self.clock = PlayClock()
        self._pending = []  # beats waiting for the play head
        self._theme = "dark" if settings.value("theme", "light") == "dark" else "light"
        self.setWindowTitle("Pulse Studio")
        self.resize(1240, 900)
        self.setMinimumSize(1020, 780)

        self._build()
        self._refresh_ports(initial=True)
        self._apply_theme()
        self._set_span(int(settings.value("span", 10)))

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._slow = QTimer(self)
        self._slow.setInterval(100)
        self._slow.timeout.connect(self._update_cards)
        self._slow.start()
        self._rec_timer = QTimer(self)
        self._rec_timer.setInterval(500)
        self._rec_timer.timeout.connect(self._update_record_button)

    # ---- layout ---------------------------------------------------------

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(24, 18, 24, 14)
        main.setSpacing(14)

        # Top bar
        top = QHBoxLayout()
        top.setSpacing(10)
        title = QLabel("Pulse Studio")
        title.setObjectName("title")
        top.addWidget(title)
        top.addStretch(1)
        self.scenario = QComboBox()
        self.scenario.setMinimumWidth(160)
        self.scenario.setToolTip("Simulated signal to try the detection of bad cases")
        for label, key in SCENARIOS:
            self.scenario.addItem(label, key)
        self.scenario.currentIndexChanged.connect(self._scenario_changed)
        self.scenario.hide()
        top.addWidget(self.scenario)
        self.port_box = QComboBox()
        self.port_box.currentIndexChanged.connect(self._port_changed)
        top.addWidget(self.port_box)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("icon")
        self.refresh_btn.clicked.connect(lambda: self._refresh_ports())
        top.addWidget(self.refresh_btn)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("primary")
        self.connect_btn.setMinimumWidth(110)
        self.connect_btn.clicked.connect(self._toggle_connection)
        top.addWidget(self.connect_btn)
        self.record_btn = QPushButton("Record")
        self.record_btn.setMinimumWidth(130)
        self.record_btn.setEnabled(False)
        self.record_btn.clicked.connect(self._toggle_recording)
        top.addWidget(self.record_btn)
        self.theme_btn = QPushButton()
        self.theme_btn.setObjectName("icon")
        self.theme_btn.clicked.connect(self._toggle_theme)
        top.addWidget(self.theme_btn)
        main.addLayout(top)

        # Hero row
        hero = QHBoxLayout()
        hero.setSpacing(14)
        self.hero_card = Card()
        hl = QHBoxLayout()
        hl.setSpacing(8)
        self.heart = HeartWidget()
        hl.addWidget(self.heart, 5)
        bpm_col = QVBoxLayout()
        bpm_col.addStretch(1)
        self.bpm_label = QLabel("--")
        self.bpm_label.setObjectName("bpm")
        bpm_col.addWidget(self.bpm_label)
        unit = QLabel("BPM")
        unit.setObjectName("bpmUnit")
        bpm_col.addWidget(unit)
        self.status_chip = Chip()
        bpm_col.addSpacing(6)
        bpm_col.addWidget(self.status_chip, 0, Qt.AlignmentFlag.AlignLeft)
        bpm_col.addStretch(1)
        hl.addLayout(bpm_col, 6)
        self.hero_card.layout_.addLayout(hl)
        self.hero_card.setFixedHeight(236)
        hero.addWidget(self.hero_card, 5)

        cards = QVBoxLayout()
        cards.setSpacing(14)
        self.ibi_card = StatCard("Interval", "ms")
        self.amp_card = StatCard("Amplitude", "counts")
        self.quality_card = StatCard("Signal quality", "%")
        small = QHBoxLayout()
        small.setSpacing(14)
        small.addWidget(self.ibi_card)
        small.addWidget(self.amp_card)
        for card in (self.ibi_card, self.amp_card, self.quality_card):
            card.setFixedHeight(111)
        cards.addLayout(small, 1)
        cards.addWidget(self.quality_card, 1)
        hero.addLayout(cards, 4)
        main.addLayout(hero, 0)

        # Waveform
        wave_card = Card("Live PPG")
        head = QHBoxLayout()
        head.addStretch(1)
        self.seg_group = QButtonGroup(self)
        self.seg_buttons = {}
        for secs in (5, 10, 30):
            b = QPushButton(f"{secs} s")
            b.setObjectName("seg")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, s=secs: self._set_span(s))
            self.seg_group.addButton(b)
            self.seg_buttons[secs] = b
            head.addWidget(b)
        wave_card.layout_.itemAt(0).widget().setParent(None)
        header = QHBoxLayout()
        header.addWidget(self.hero_title("Live PPG"))
        header.addLayout(head)
        wave_card.layout_.addLayout(header)
        self.wave = WavePlot()
        wave_card.layout_.addWidget(self.wave, 1)
        wave_card.setMinimumHeight(250)
        main.addWidget(wave_card, 1)

        # Variability
        lower = QHBoxLayout()
        lower.setSpacing(14)
        tacho_card = Card("Tachogram (beat to beat interval, ms)")
        self.tacho = TachoPlot()
        tacho_card.layout_.addWidget(self.tacho, 1)
        tacho_card.setFixedHeight(206)
        lower.addWidget(tacho_card, 3)
        hrv_card = Card("Variability")
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(2)
        self.sdnn = self._hrv_value(grid, 0, "SDNN", "ms")
        self.rmssd = self._hrv_value(grid, 1, "RMSSD", "ms")
        self.beats_label = self._hrv_value(grid, 2, "Beats", "")
        hrv_card.layout_.addLayout(grid)
        self.hrv_hint = QLabel("")
        self.hrv_hint.setObjectName("hint")
        self.hrv_hint.setWordWrap(True)
        hrv_card.layout_.addWidget(self.hrv_hint)
        hrv_card.layout_.addStretch(1)
        hrv_card.setFixedHeight(206)
        lower.addWidget(hrv_card, 2)
        main.addLayout(lower, 0)

        # Footer
        foot = QHBoxLayout()
        note = QLabel(DISCLAIMER)
        note.setObjectName("note")
        note.setWordWrap(True)
        foot.addWidget(note, 1)
        self.record_info = QPushButton("")
        self.record_info.setObjectName("seg")
        self.record_info.clicked.connect(self._open_recordings)
        self.record_info.hide()
        foot.addWidget(self.record_info)
        main.addLayout(foot)

    def hero_title(self, text: str) -> QLabel:
        lab = QLabel(text.upper())
        lab.setObjectName("cardTitle")
        return lab

    def _hrv_value(self, grid: QGridLayout, r: int, name: str, unit: str) -> QLabel:
        lab = QLabel(name)
        lab.setObjectName("cardTitle")
        val = QLabel("--")
        val.setObjectName("cardValue")
        val.setFont(self._small_value_font())
        grid.addWidget(lab, r, 0)
        grid.addWidget(val, r, 1, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(QLabel(unit), r, 2)
        return val

    def _small_value_font(self) -> QFont:
        f = QFont("Segoe UI Variable Display", 18)
        f.setWeight(QFont.Weight.DemiBold)
        return f

    # ---- theme and settings ---------------------------------------------

    def _apply_theme(self) -> None:
        c = THEMES[self._theme]
        self.setStyleSheet(stylesheet(c))
        self.wave.apply_theme(c)
        self.tacho.apply_theme(c)
        self.heart.set_colors("#FF7A8E" if self._theme == "dark" else "#FF6B81",
                              c["accent_dark"], c["idle"], c["accent"])
        self.theme_btn.setText("Light" if self._theme == "dark" else "Dark")
        self._update_cards()

    def _toggle_theme(self) -> None:
        self._theme = "light" if self._theme == "dark" else "dark"
        self.settings.setValue("theme", self._theme)
        self._apply_theme()

    def _set_span(self, seconds: int) -> None:
        if seconds not in self.seg_buttons:
            seconds = 10
        self.seg_buttons[seconds].setChecked(True)
        self.wave.set_span(float(seconds))
        self.settings.setValue("span", seconds)

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

    def _port_changed(self) -> None:
        self.scenario.setVisible(self.port_box.currentData() == DEMO_KEY)

    def _toggle_connection(self) -> None:
        if self.session.active:
            self._disconnect()
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
            self.session.start(source)
        except RuntimeError as exc:
            self.record_info.setText(str(exc))
            self.record_info.show()
            self.record_info.setToolTip(str(exc))
            return
        self.settings.setValue("port", key)
        self.record_info.hide()
        self.clock.reset()
        self._pending.clear()
        self.connect_btn.setText("Disconnect")
        self.connect_btn.setObjectName("")
        self.connect_btn.setStyleSheet(self.connect_btn.styleSheet())
        self.connect_btn.style().unpolish(self.connect_btn)
        self.connect_btn.style().polish(self.connect_btn)
        self.record_btn.setEnabled(True)
        self.port_box.setEnabled(False)
        self.refresh_btn.setEnabled(False)

    def _disconnect(self) -> None:
        if self.session.recorder is not None:
            self._toggle_recording()
        self.session.stop()
        self.connect_btn.setText("Connect")
        self.connect_btn.setObjectName("primary")
        self.connect_btn.style().unpolish(self.connect_btn)
        self.connect_btn.style().polish(self.connect_btn)
        self.record_btn.setEnabled(False)
        self.port_box.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.heart.set_active(False)

    def _scenario_changed(self) -> None:
        src = self.session.source
        if isinstance(src, SimulatedSource):
            src.mode = self.scenario.currentData()

    # ---- recording -------------------------------------------------------

    def _recordings_folder(self) -> Path:
        saved = self.settings.value("record_folder")
        return Path(saved) if saved else default_folder()

    def _toggle_recording(self) -> None:
        if self.session.recorder is None:
            path = self.session.start_recording(self._recordings_folder())
            self.record_btn.setText("Stop recording")
            self.record_btn.setObjectName("recording")
            self._rec_timer.start()
            self.record_info.hide()
        else:
            paths = self.session.stop_recording()
            self._rec_timer.stop()
            self.record_btn.setText("Record")
            self.record_btn.setObjectName("")
            if paths:
                self.record_info.setText(f"Saved {paths[0].name}. Open folder")
                self.record_info.setToolTip(str(paths[0].parent))
                self.record_info.show()
        self.record_btn.style().unpolish(self.record_btn)
        self.record_btn.style().polish(self.record_btn)

    def _update_record_button(self) -> None:
        rec = self.session.recorder
        if rec is not None:
            s = int(rec.duration)
            self.record_btn.setText(f"Stop  {s // 60:02d}:{s % 60:02d}")

    def _open_recordings(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._recordings_folder())))

    # ---- frame and card updates -----------------------------------------

    def _tick(self) -> None:
        s = self.session
        if not s.active:
            return
        if s.error:
            self._disconnect()
            self.record_info.setText(s.error)
            self.record_info.show()
            return
        self._pending.extend(s.poll())
        if s.t.size == 0:
            return
        head = self.clock.update(s.latest_t, time.perf_counter())

        usable = s.metrics.bpm is not None
        while self._pending and self._pending[0].t <= head:
            beat = self._pending.pop(0)
            if usable:
                self.heart.pulse()
        self.heart.set_active(usable)
        self.heart.update()
        self.wave.update_view(s.t, s.filtered, s.beats, head)

    def _update_cards(self) -> None:
        c = THEMES[self._theme]
        s = self.session
        m = s.metrics if s.active else None
        dark = self._theme == "dark"
        if m is None:
            self.bpm_label.setText("--")
            self.status_chip.set_state("Not connected", c["idle"], dark)
            for card in (self.ibi_card, self.amp_card, self.quality_card):
                card.set_value("--")
            self.sdnn.setText("--")
            self.rmssd.setText("--")
            self.beats_label.setText("--")
            self.hrv_hint.setText("Connect the sensor or try the demo.")
            self.tacho.update_beats([])
            return

        q = m.quality
        text, tone = STATE_TEXT[q.state]
        self.status_chip.set_state(text, c[tone], dark)
        self.bpm_label.setText("--" if m.bpm is None else f"{m.bpm:.0f}")
        self.ibi_card.set_value("--" if m.ibi_ms is None else f"{m.ibi_ms:.0f}",
                                "since the last beat" if m.ibi_ms else "")
        self.amp_card.set_value("--" if m.amplitude <= 0 else f"{m.amplitude:.1f}",
                                "filtered, peak to peak" if m.amplitude else "")
        self.quality_card.set_value(f"{q.score * 100:.0f}", text)
        h = m.hrv
        self.sdnn.setText("--" if h is None else f"{h.sdnn_ms:.0f}")
        self.rmssd.setText("--" if h is None else f"{h.rmssd_ms:.0f}")
        self.beats_label.setText(str(m.beat_count))
        self.hrv_hint.setText(
            "Computed over the last 90 s of valid beats." if h
            else "Needs about 20 steady beats. Keep the finger still."
        )
        self.tacho.update_beats(s.beats)

    def closeEvent(self, event) -> None:
        self.settings.setValue("geometry", self.saveGeometry())
        self.session.stop()
        super().closeEvent(event)
