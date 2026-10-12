"""The four pages of the main window."""

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..dsp import SignalState
from ..recording import list_sessions
from . import icons
from .heart import HeartWidget
from .plots import PoincarePlot, TachoPlot, TrendPlot, WavePlot
from .widgets import Card, Legend, MetricCard, MiniStat, QualityBar

STATE_WORD = {
    SignalState.WARMING_UP: ("Warming up", "idle", "Settling, one moment"),
    SignalState.NO_FINGER: ("No finger", "bad", "Place a fingertip on the sensor"),
    SignalState.MOTION: ("Movement", "warn", "Hold still"),
    SignalState.SATURATED: ("Saturated", "bad", "Ease the pressure on the sensor"),
    SignalState.POOR: ("Weak", "warn", "Keep still and press lightly"),
    SignalState.GOOD: ("Good", "good", "Stable signal detected"),
}


def _page_layout(page: QWidget) -> QVBoxLayout:
    page.setObjectName("page")
    lay = QVBoxLayout(page)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(14)
    return lay


def _seg(text: str, group: QButtonGroup, slot) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("seg")
    b.setCheckable(True)
    b.clicked.connect(slot)
    group.addButton(b)
    return b


class _WaveControls:
    """Window length buttons shared by the two pages that show the trace."""

    def __init__(self, window, header: QHBoxLayout, with_mode: bool):
        self.group = QButtonGroup(window)
        self.span_buttons = {}
        for secs in (5, 10, 30):
            b = _seg(f"{secs} s", self.group, lambda _=False, s=secs: window.set_span(s))
            self.span_buttons[secs] = b
            header.addWidget(b)
        self.mode_buttons = {}
        if with_mode:
            header.addSpacing(8)
            self.mode_group = QButtonGroup(window)
            for key, label in (("scroll", "Scroll"), ("sweep", "Sweep")):
                b = _seg(label, self.mode_group, lambda _=False, k=key: window.set_mode(k))
                self.mode_buttons[key] = b
                header.addWidget(b)


class DashboardPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window_ = window
        lay = _page_layout(self)

        # Row of summary cards and the heart.
        top = QHBoxLayout()
        top.setSpacing(14)
        self.bpm_card = MetricCard("Heart rate", "BPM", tint=True)
        self.ibi_card = MetricCard("Pulse interval", "ms")
        self.quality_card = MetricCard("Signal quality", "", word=True)
        self.quality_bar = QualityBar()
        self.quality_bar.SEGMENTS = 4
        self.quality_card.extra.addWidget(self.quality_bar)
        self.quality_card.extra.addSpacing(8)
        for card in (self.bpm_card, self.ibi_card, self.quality_card):
            card.setFixedHeight(186)
            top.addWidget(card, 3)
        heart_box = QHBoxLayout()
        heart_box.setSpacing(10)
        self.heart = HeartWidget()
        self.heart.setFixedSize(190, 186)
        heart_box.addWidget(self.heart)
        cap = QVBoxLayout()
        cap.addStretch(1)
        bar = QFrame()
        bar.setObjectName("accentBar")
        bar.setFixedSize(34, 2)
        cap.addWidget(bar)
        self.caption = QLabel("The heart beats with every pulse found in the signal.\nIt is an illustration, not a measurement.")
        self.caption.setObjectName("hint")
        self.caption.setWordWrap(True)
        self.caption.setFixedWidth(150)
        cap.addWidget(self.caption)
        cap.addStretch(1)
        heart_box.addLayout(cap)
        top.addLayout(heart_box, 4)
        lay.addLayout(top)

        # The live signal.
        live = Card()
        live.layout_.setContentsMargins(24, 18, 24, 14)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(0)
        t = QLabel("The live signal")
        t.setObjectName("sectionTitle")
        titles.addWidget(t)
        s = QLabel("Real-time photoplethysmography (PPG) signal from the XD-58C sensor.")
        s.setObjectName("hint")
        titles.addWidget(s)
        head.addLayout(titles)
        head.addStretch(1)
        self.controls = _WaveControls(window, head, with_mode=False)
        head.addSpacing(14)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setObjectName("outline")
        self.pause_btn.setMinimumWidth(96)
        self.pause_btn.clicked.connect(window.toggle_pause)
        head.addWidget(self.pause_btn)
        self.record_btn = QPushButton("Record")
        self.record_btn.setObjectName("primary")
        self.record_btn.setMinimumWidth(110)
        self.record_btn.clicked.connect(window.toggle_recording)
        head.addWidget(self.record_btn)
        live.layout_.addLayout(head)
        self.wave = WavePlot()
        live.layout_.addWidget(self.wave, 1)
        self.legend = Legend()
        live.layout_.addWidget(self.legend)
        line = QFrame()
        line.setObjectName("divider")
        live.layout_.addWidget(line)
        stats = QHBoxLayout()
        stats.setSpacing(26)
        self.amp = MiniStat("Amplitude", "counts")
        self.last_beat = MiniStat("Last beat", "s")
        self.peaks = MiniStat("Peaks detected", "")
        self.window_note = QLabel("")
        self.window_note.setObjectName("hint")
        for w in (self.amp, self.last_beat, self.peaks):
            stats.addWidget(w, 1)
        stats.addWidget(self.window_note, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        live.layout_.addLayout(stats)
        live.setMinimumHeight(340)
        lay.addWidget(live, 1)

        # Session bar.
        bar = Card()
        row = QHBoxLayout()
        row.setSpacing(14)
        self.session_icon = QLabel()
        self.session_icon.setFixedSize(30, 30)
        self.session_icon.setScaledContents(True)
        row.addWidget(self.session_icon)
        col = QVBoxLayout()
        col.setSpacing(0)
        name = QLabel("Current session")
        name.setObjectName("cardTitle")
        col.addWidget(name)
        self.session_state = QLabel("Not recording")
        self.session_state.setObjectName("hint")
        col.addWidget(self.session_state)
        row.addLayout(col)
        row.addStretch(1)
        self.start_btn = QPushButton("Start recording")
        self.start_btn.setObjectName("primary")
        self.start_btn.setMinimumWidth(160)
        self.start_btn.clicked.connect(window.toggle_recording)
        row.addWidget(self.start_btn)
        self.export_btn = QPushButton("Export CSV")
        self.export_btn.setObjectName("outline")
        self.export_btn.setMinimumWidth(130)
        self.export_btn.clicked.connect(window.export_buffer)
        row.addWidget(self.export_btn)
        self.last_session = QLabel("")
        self.last_session.setObjectName("hint")
        self.last_session.setMinimumWidth(170)
        row.addWidget(self.last_session)
        bar.layout_.addLayout(row)
        lay.addWidget(bar)

    def apply_theme(self, c: dict) -> None:
        self.wave.apply_theme(c)
        self.heart.set_theme(c["name"])
        self.legend.set_colors(c["wave"], c["peak"], c["text"])
        self.bpm_card.set_icon(icons.heart_outline(c["accent"]))
        self.ibi_card.set_icon(icons.pulse(c["accent"]))
        self.quality_card.set_icon(icons.bars(c["accent"]))
        self.session_icon.setPixmap(icons.stack(c["muted"], 60).pixmap(60, 60))
        self.setStyleSheet(f"QFrame#accentBar {{ background: {c['accent']}; border: none; }}")

    def refresh(self, ctx) -> None:
        c, s = ctx.c, ctx.session
        win = self.window_
        rec = s.recorder
        self.pause_btn.setText("Resume" if win.paused else "Pause")
        self.record_btn.setText("Stop" if rec else "Record")
        self.start_btn.setText("Stop recording" if rec else "Start recording")
        self.record_btn.setEnabled(ctx.connected)
        self.start_btn.setEnabled(ctx.connected)
        self.session_state.setText(
            f"Recording, {int(rec.duration)} s" if rec else "Not recording")
        self.last_session.setText(win.last_session_text())

        if not ctx.connected:
            self.bpm_card.set("--", "Connect the sensor, or try a demo")
            self.ibi_card.set("--", "Time between consecutive heart beats")
            self.quality_card.set("--", "No signal yet")
            self.quality_bar.set_level(0, c["idle"], c["button"])
            self.amp.set_value("--")
            self.last_beat.set_value("--")
            self.peaks.set_value("--")
            return
        m = s.metrics
        q = m.quality
        word, tone, hint = STATE_WORD[q.state]
        if m.bpm is None:
            self.bpm_card.set("--", "Waiting for a steady signal")
        else:
            self.bpm_card.set(("~" if m.bpm_approx else "") + f"{m.bpm:.0f}",
                              "Estimated from the rhythm" if m.bpm_approx else "From detected pulse intervals")
        self.ibi_card.set("--" if m.ibi_ms is None else f"{m.ibi_ms:.0f}", "Time between consecutive heart beats")
        self.quality_card.set(word, hint)
        self.quality_card.value.setStyleSheet(f"color: {c[tone]};" if q.state != SignalState.WARMING_UP else "")
        self.quality_bar.set_level(q.score, c[tone], c["button"])
        self.amp.set_value("--" if m.amplitude <= 0 else f"{m.amplitude:.1f}")
        self.last_beat.set_value("--" if m.ibi_ms is None else f"{m.ibi_ms / 1000:.2f}")
        head, span = ctx.head, self.wave.span
        self.peaks.set_value(str(sum(1 for b in s.beats if head - span <= b.t <= head)))
        self.window_note.setText(f"In the selected time window\n({span:.0f} seconds)")

    def draw(self, ctx) -> None:
        s = ctx.session
        self.heart.update()
        self.wave.update_view(s.t, s.filtered, s.beats, ctx.head)


class LivePage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window_ = window
        lay = _page_layout(self)

        row = QHBoxLayout()
        row.setSpacing(14)
        self.bpm = MetricCard("Heart rate", "BPM", tint=True)
        self.ibi = MetricCard("Interval", "ms")
        self.amp = MetricCard("Amplitude", "counts")
        self.resp = MetricCard("Respiration", "/min")
        self.quality = MetricCard("Signal quality", "%")
        for card in (self.bpm, self.ibi, self.amp, self.resp, self.quality):
            card.setFixedHeight(142)
            card.desc.setMaximumHeight(18)
            row.addWidget(card, 1)
        lay.addLayout(row)

        wave_card = Card("Live PPG  ·  0.6-3.5 Hz")
        self.controls = _WaveControls(window, wave_card.header, with_mode=True)
        wave_card.header.addSpacing(10)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setObjectName("outline")
        self.pause_btn.clicked.connect(window.toggle_pause)
        wave_card.header.addWidget(self.pause_btn)
        self.wave = WavePlot()
        wave_card.layout_.addWidget(self.wave, 1)
        wave_card.setMinimumHeight(260)
        lay.addWidget(wave_card, 1)

        lower = QHBoxLayout()
        lower.setSpacing(14)
        self.tacho, self.poincare, self.trend = TachoPlot(), PoincarePlot(), TrendPlot()
        for title, plot in (("Tachogram, ms", self.tacho), ("Poincare plot, ms", self.poincare),
                            ("BPM, last minutes", self.trend)):
            card = Card(title)
            card.layout_.addWidget(plot, 1)
            card.setFixedHeight(214)
            lower.addWidget(card, 3)
        hrv = Card("Variability")
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        self.sdnn = MiniStat("SDNN", "ms")
        self.rmssd = MiniStat("RMSSD", "ms")
        self.pnn50 = MiniStat("pNN50", "%")
        self.beats = MiniStat("Beats", "")
        for i, w in enumerate((self.sdnn, self.rmssd, self.pnn50, self.beats)):
            grid.addWidget(w, i // 2, i % 2)
        hrv.layout_.addLayout(grid)
        self.hrv_hint = QLabel("")
        self.hrv_hint.setObjectName("hint")
        self.hrv_hint.setWordWrap(True)
        hrv.layout_.addWidget(self.hrv_hint)
        hrv.layout_.addStretch(1)
        hrv.setFixedHeight(214)
        lower.addWidget(hrv, 3)
        lay.addLayout(lower)

    def apply_theme(self, c: dict) -> None:
        for plot in (self.wave, self.tacho, self.poincare, self.trend):
            plot.apply_theme(c)
        self.bpm.set_icon(icons.heart_outline(c["accent"]))
        self.ibi.set_icon(icons.pulse(c["accent"]))
        self.amp.set_icon(icons.bars(c["accent"]))
        self.resp.set_icon(icons.clock(c["accent"]))
        self.quality.set_icon(icons.bars(c["accent"]))

    def refresh(self, ctx) -> None:
        s = ctx.session
        self.pause_btn.setText("Resume" if self.window_.paused else "Pause")
        if not ctx.connected:
            for card in (self.bpm, self.ibi, self.amp, self.resp, self.quality):
                card.set("--", "")
            for w in (self.sdnn, self.rmssd, self.pnn50, self.beats):
                w.set_value("--")
            self.hrv_hint.setText("")
            for plot in (self.tacho, self.poincare):
                plot.update_beats([])
            self.trend.update_history([], 0.0)
            return
        m, q = s.metrics, s.metrics.quality
        word, tone, hint = STATE_WORD[q.state]
        self.bpm.set("--" if m.bpm is None else ("~" if m.bpm_approx else "") + f"{m.bpm:.0f}",
                     "Estimated from the rhythm" if m.bpm_approx else "Moving average of 6 beats")
        self.ibi.set("--" if m.ibi_ms is None else f"{m.ibi_ms:.0f}", "Last valid interval")
        self.amp.set("--" if m.amplitude <= 0 else f"{m.amplitude:.1f}", "Filtered, peak to peak")
        self.resp.set("--" if m.resp_rate is None else f"{m.resp_rate:.0f}",
                      "Estimate" if m.resp_rate else "Needs about 30 s")
        self.quality.set(f"{q.score * 100:.0f}", f"{word}. {hint}")
        h = m.hrv
        self.sdnn.set_value("--" if h is None else f"{h.sdnn_ms:.0f}")
        self.rmssd.set_value("--" if h is None else f"{h.rmssd_ms:.0f}")
        self.pnn50.set_value("--" if h is None else f"{h.pnn50:.0f}")
        self.beats.set_value(str(m.beat_count))
        self.hrv_hint.setText(
            f"SD1 {h.sd1_ms:.0f} ms, SD2 {h.sd2_ms:.0f} ms. Last 90 s of valid beats." if h
            else "Needs about 20 steady beats. Keep the finger still."
        )
        self.tacho.update_beats(s.beats)
        self.poincare.update_beats(s.beats)
        self.trend.update_history(s.bpm_history, s.latest_t)

    def draw(self, ctx) -> None:
        s = ctx.session
        self.wave.update_view(s.t, s.filtered, s.beats, ctx.head)


class SessionsPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window_ = window
        lay = _page_layout(self)
        card = Card()
        card.layout_.setContentsMargins(20, 18, 20, 18)
        head = QHBoxLayout()
        title = QLabel("Recordings")
        title.setObjectName("sectionTitle")
        head.addWidget(title)
        head.addStretch(1)
        self.folder_label = QLabel("")
        self.folder_label.setObjectName("hint")
        head.addWidget(self.folder_label)
        card.layout_.addLayout(head)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Started", "Duration", "Beats", "Size"])
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        card.layout_.addWidget(self.table, 1)
        self.empty = QLabel("No recordings yet. Press Record on the Dashboard to make one.")
        self.empty.setObjectName("hint")
        card.layout_.addWidget(self.empty)

        row = QHBoxLayout()
        self.replay_btn = QPushButton("Replay in the app")
        self.replay_btn.setObjectName("primary")
        self.replay_btn.setEnabled(False)
        self.replay_btn.clicked.connect(self._replay)
        row.addWidget(self.replay_btn)
        open_btn = QPushButton("Open folder")
        open_btn.setObjectName("outline")
        open_btn.clicked.connect(window.open_recordings)
        row.addWidget(open_btn)
        refresh = QPushButton("Refresh")
        refresh.setObjectName("outline")
        refresh.clicked.connect(self.reload)
        row.addWidget(refresh)
        row.addStretch(1)
        card.layout_.addLayout(row)
        lay.addWidget(card, 1)
        self._sessions = []

    def apply_theme(self, c: dict) -> None:
        pass

    def reload(self) -> None:
        folder = self.window_.recordings_folder()
        self.folder_label.setText(str(folder))
        self._sessions = list_sessions(folder)
        self.table.setRowCount(len(self._sessions))
        for i, info in enumerate(self._sessions):
            when = info.started.strftime("%d %b %Y, %H:%M") if info.started else info.samples_path.name
            mins, secs = divmod(int(info.duration_s), 60)
            for col, text in enumerate((when, f"{mins}:{secs:02d}", str(info.beats),
                                        f"{info.size_bytes / 1024:.0f} KB")):
                self.table.setItem(i, col, QTableWidgetItem(text))
        self.empty.setVisible(not self._sessions)
        self.table.setVisible(bool(self._sessions))
        self._selection_changed()

    def _selection_changed(self) -> None:
        self.replay_btn.setEnabled(bool(self.table.selectedItems()))

    def _replay(self) -> None:
        rows = {i.row() for i in self.table.selectedItems()}
        if rows:
            self.window_.replay_file(self._sessions[min(rows)].samples_path)

    def refresh(self, ctx) -> None:
        pass

    def draw(self, ctx) -> None:
        pass


class SettingsPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window_ = window
        lay = _page_layout(self)
        card = Card()
        card.layout_.setContentsMargins(26, 22, 26, 22)
        card.layout_.setSpacing(14)
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(16)
        grid.setColumnStretch(1, 1)

        def label(text: str, hint: str = "") -> QWidget:
            box = QWidget()
            v = QVBoxLayout(box)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(0)
            t = QLabel(text)
            t.setObjectName("cardTitle")
            v.addWidget(t)
            if hint:
                h = QLabel(hint)
                h.setObjectName("hint")
                v.addWidget(h)
            return box

        self.theme_box = QComboBox()
        for key, name in (("light", "Studio (light)"), ("dark", "Monitor (dark)")):
            self.theme_box.addItem(name, key)
        self.theme_box.currentIndexChanged.connect(lambda: window.set_theme(self.theme_box.currentData()))
        grid.addWidget(label("Appearance", "Studio is light and warm. Monitor is dark, like a patient monitor."), 0, 0)
        grid.addWidget(self.theme_box, 0, 1, Qt.AlignmentFlag.AlignLeft)

        self.mode_box = QComboBox()
        self.mode_box.addItem("Scroll: the trace moves left", "scroll")
        self.mode_box.addItem("Sweep: the trace is written across the screen", "sweep")
        self.mode_box.currentIndexChanged.connect(lambda: window.set_mode(self.mode_box.currentData()))
        grid.addWidget(label("Trace style"), 1, 0)
        grid.addWidget(self.mode_box, 1, 1, Qt.AlignmentFlag.AlignLeft)

        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        browse = QPushButton("Browse")
        browse.setObjectName("outline")
        browse.clicked.connect(self._browse)
        frow = QHBoxLayout()
        frow.addWidget(self.folder_edit, 1)
        frow.addWidget(browse)
        grid.addWidget(label("Recordings folder", "Where CSV recordings are saved."), 2, 0)
        grid.addLayout(frow, 2, 1)

        self.auto_box = QCheckBox("Connect to the Arduino when the app starts")
        self.auto_box.toggled.connect(lambda on: window.settings.setValue("autoconnect", on))
        grid.addWidget(label("Startup"), 3, 0)
        grid.addWidget(self.auto_box, 3, 1)
        card.layout_.addLayout(grid)

        line = QFrame()
        line.setObjectName("divider")
        card.layout_.addWidget(line)
        about = QLabel(
            "Pulse Studio reads an XD-58C pulse sensor through an Arduino Uno and shows the pulse in real time.\n"
            "The PPG measures blood volume changes optically, not the electrical activity of the heart. "
            "The heart animation is illustrative, respiration is an estimate, and this is not a medical device.\n"
            "MIT license. Source: github.com/andremassuca/pulse-studio"
        )
        about.setObjectName("hint")
        about.setWordWrap(True)
        card.layout_.addWidget(about)
        card.layout_.addStretch(1)
        lay.addWidget(card, 1)

    def load(self, theme: str, mode: str, folder: Path, auto: bool) -> None:
        for box, value in ((self.theme_box, theme), (self.mode_box, mode)):
            box.blockSignals(True)
            box.setCurrentIndex(max(0, box.findData(value)))
            box.blockSignals(False)
        self.folder_edit.setText(str(folder))
        self.auto_box.blockSignals(True)
        self.auto_box.setChecked(auto)
        self.auto_box.blockSignals(False)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Recordings folder", self.folder_edit.text())
        if chosen:
            self.folder_edit.setText(chosen)
            self.window_.settings.setValue("record_folder", chosen)

    def apply_theme(self, c: dict) -> None:
        pass

    def refresh(self, ctx) -> None:
        pass

    def draw(self, ctx) -> None:
        pass
