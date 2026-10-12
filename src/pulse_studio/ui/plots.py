"""The live waveform, tachogram, Poincare plot and BPM trend."""

import math

import numpy as np
import pyqtgraph as pg
from PySide6.QtGui import QColor, QFont

from ..dsp import Beat


def _nice_step(span: float, divisions: int = 4) -> float:
    raw = span / divisions
    mag = 10 ** math.floor(math.log10(max(raw, 1e-9)))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return float(m * mag)
    return float(10 * mag)


def _rgba(color: str, alpha: int, width: float) -> pg.mkPen:
    c = QColor(color)
    c.setAlpha(alpha)
    return pg.mkPen(c, width=width)


def _style_axis(axis, c: dict) -> None:
    axis.setPen(pg.mkPen(c["grid_major"]))
    axis.setTextPen(pg.mkPen(c["muted"]))
    axis.setStyle(tickFont=QFont("Segoe UI", 9))


class WavePlot(pg.PlotWidget):
    """The PPG trace, in the style of a patient monitor.

    Sweep mode: the trace is written from left to right, a short gap erases
    the old trace ahead of the head, and the previous pass fades behind it.
    Scroll mode: the trace moves left under a fixed grid. Peaks appear once the
    play head reaches them, which is also when the heart contracts.
    """

    GLOW = ((9.0, 26), (5.0, 60), (2.4, 255))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMenuEnabled(False)
        self.setMouseEnabled(False, False)
        self.hideButtons()
        self.setAntialiasing(True)
        self.span = 10.0
        self.mode = "sweep"
        self._half = 3.0
        self._snap = True  # fit the vertical scale at once on the first data
        self._c = None
        item = self.getPlotItem()
        item.layout.setContentsMargins(6, 8, 10, 4)
        self._prev = self.plot([], [])
        self._cur = [self.plot([], []) for _ in self.GLOW]
        self._halo = pg.ScatterPlotItem(size=26, pen=pg.mkPen(None))
        self._head = pg.ScatterPlotItem(size=9, pen=pg.mkPen(None))
        self._peak_halo = pg.ScatterPlotItem(size=24, pen=pg.mkPen(None))
        self._peaks = pg.ScatterPlotItem(size=11)
        self._rejected = pg.ScatterPlotItem(size=9, brush=pg.mkBrush(None))
        for it in (self._peak_halo, self._peaks, self._rejected, self._halo, self._head):
            self.addItem(it)
        self.set_span(10.0)

    # ---- appearance ------------------------------------------------------

    def apply_theme(self, c: dict) -> None:
        self._c = c
        self.setBackground(c["plot_bg"])
        _style_axis(self.getAxis("bottom"), c)
        studio = c["name"] == "light"
        self.getPlotItem().showAxis("left", studio)
        if studio:
            _style_axis(self.getAxis("left"), c)
            self.getAxis("left").setWidth(54)
            self.setLabel("left", "Amplitude (counts)", **{"color": c["muted"], "font-size": "10pt"})
            self.setLabel("bottom", "Time (s)", **{"color": c["muted"], "font-size": "10pt"})
        else:
            self.setLabel("bottom", "")
        glow = bool(c["glow"])
        for curve, (width, alpha) in zip(self._cur, self.GLOW):
            if width > 3 and not glow:
                curve.setPen(pg.mkPen(None))
            else:
                curve.setPen(_rgba(c["wave"], alpha, width))
        self._prev.setPen(_rgba(c["wave"], 90 if glow else 70, 2.0))
        self._head.setBrush(pg.mkBrush("#FFFFFF" if glow else c["wave"]))
        self._halo.setBrush(pg.mkBrush(_rgba(c["wave"], 70 if glow else 0, 1).color()))
        self._peaks.setBrush(pg.mkBrush(c["peak"]))
        self._peaks.setPen(pg.mkPen(c["plot_bg"], width=2))
        self._peak_halo.setBrush(pg.mkBrush(_rgba(c["peak"], 60 if glow else 0, 1).color()))
        self._rejected.setPen(pg.mkPen(c["idle"], width=2))
        self.showGrid(x=True, y=True, alpha=0.9 if glow else 0.55)

    def set_span(self, seconds: float) -> None:
        self.span = seconds
        self._apply_axes()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self._apply_axes()

    def _apply_axes(self) -> None:
        major = 1.0 if self.span <= 10 else 5.0
        axis = self.getAxis("bottom")
        axis.setTickSpacing(major, major / 5)
        axis.setStyle(showValues=True)
        self.setXRange(0, self.span, padding=0)

    # ---- drawing ---------------------------------------------------------

    @staticmethod
    def _thin(x: np.ndarray, y: np.ndarray, limit: int = 1500):
        step = max(1, len(x) // limit)
        return x[::step], y[::step]

    def clear_view(self) -> None:
        self._snap = True
        for curve in (*self._cur, self._prev):
            curve.setData([], [])
        for it in (self._peaks, self._rejected, self._halo, self._head, self._peak_halo):
            it.setData([], [])

    def update_view(self, t: np.ndarray, y: np.ndarray, beats: list[Beat], playhead: float) -> None:
        if t.size == 0:
            self.clear_view()
            return
        S = self.span
        if self.mode == "sweep":
            self._draw_sweep(t, y, beats, playhead, S)
        else:
            self._draw_scroll(t, y, beats, playhead, S)

    def _set_current(self, x: np.ndarray, y: np.ndarray) -> None:
        x, y = self._thin(x, y)
        for curve in self._cur:
            curve.setData(x, y)

    def _scale_y(self, *arrays: np.ndarray) -> None:
        parts = [a for a in arrays if a.size]
        values = np.concatenate(parts) if parts else np.empty(0)
        if values.size > 50:
            level = float(np.percentile(np.abs(values), 99))
            target = max(1.2, level * 1.35)
            if self._snap and values.size > 250:
                self._half, self._snap = target, False
            else:
                # Grow fast when the trace would be clipped, shrink gently.
                self._half += (0.35 if target > self._half else 0.06) * (target - self._half)
        step = _nice_step(2 * self._half)
        self.getAxis("left").setTickSpacing(step, step / 5)
        self.setYRange(-self._half, self._half, padding=0)

    def _mark(self, good, bad, head_xy) -> None:
        self._peaks.setData([p[0] for p in good], [p[1] for p in good])
        self._peak_halo.setData([p[0] for p in good], [p[1] for p in good])
        self._rejected.setData([p[0] for p in bad], [p[1] for p in bad])
        if head_xy is None:
            self._head.setData([], [])
            self._halo.setData([], [])
        else:
            self._head.setData([head_xy[0]], [head_xy[1]])
            self._halo.setData([head_xy[0]], [head_xy[1]])

    def _draw_sweep(self, t, y, beats, head, S) -> None:
        start = math.floor(head / S) * S
        phase = head - start
        gap = max(0.3, 0.04 * S)
        a = int(np.searchsorted(t, start))
        b = int(np.searchsorted(t, head, side="right"))
        cur_x, cur_y = t[a:b] - start, y[a:b]
        self._set_current(cur_x, cur_y)

        p0 = int(np.searchsorted(t, start - S + phase + gap))
        prev_x, prev_y = t[p0:a] - (start - S), y[p0:a]
        px, py = self._thin(prev_x, prev_y)
        self._prev.setData(px, py)
        self._scale_y(cur_y, prev_y)

        good, bad = [], []
        for beat in beats:
            if start <= beat.t <= head:
                x = beat.t - start
            elif start - S + phase + gap <= beat.t < start:
                x = beat.t - (start - S)
            else:
                continue
            (good if beat.valid or beat.ibi_ms is None else bad).append((x, beat.height))
        head_xy = (float(cur_x[-1]), float(cur_y[-1])) if cur_x.size else None
        self._mark(good, bad, head_xy)

    def _draw_scroll(self, t, y, beats, head, S) -> None:
        a = int(np.searchsorted(t, head - S - 0.2))
        b = int(np.searchsorted(t, head, side="right"))
        x, v = t[a:b] - (head - S), y[a:b]
        self._set_current(x, v)
        self._prev.setData([], [])
        self._scale_y(v)
        good, bad = [], []
        for beat in beats:
            if head - S - 0.5 <= beat.t <= head:
                (good if beat.valid or beat.ibi_ms is None else bad).append((beat.t - (head - S), beat.height))
        head_xy = (float(x[-1]), float(v[-1])) if x.size else None
        self._mark(good, bad, head_xy)


class _SmallPlot(pg.PlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMenuEnabled(False)
        self.setMouseEnabled(False, False)
        self.hideButtons()
        self.setAntialiasing(True)
        self.getPlotItem().layout.setContentsMargins(2, 6, 8, 2)
        self.getAxis("left").setWidth(40)

    def _theme(self, c: dict) -> None:
        self.setBackground(c["card"])
        for name in ("left", "bottom"):
            _style_axis(self.getAxis(name), c)


class TachoPlot(_SmallPlot):
    """Beat to beat interval over the last beats."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._line = self.plot([], [])
        self._dots = pg.ScatterPlotItem(size=7)
        self._invalid = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(None))
        self.addItem(self._dots)
        self.addItem(self._invalid)

    def apply_theme(self, c: dict) -> None:
        self._theme(c)
        self._line.setPen(pg.mkPen(c["accent"], width=2))
        self._dots.setBrush(pg.mkBrush(c["accent"]))
        self._dots.setPen(pg.mkPen(c["card"], width=1.5))
        self._invalid.setPen(pg.mkPen(c["idle"], width=1.8))
        self.showGrid(x=False, y=True, alpha=0.35)

    def update_beats(self, beats: list[Beat], count: int = 40) -> None:
        shown = [b for b in beats if b.ibi_ms is not None][-count:]
        if len(shown) < 2:
            for it in (self._line, self._dots, self._invalid):
                it.setData([], [])
            return
        x = np.arange(len(shown), dtype=float)
        y = np.array([b.ibi_ms for b in shown])
        ok = np.array([b.valid for b in shown])
        self._line.setData(x[ok], y[ok])
        self._dots.setData(x[ok], y[ok])
        self._invalid.setData(x[~ok], y[~ok])
        good = y[ok] if ok.any() else y
        lo, hi = float(good.min()), float(good.max())
        pad = max(60.0, (hi - lo) * 0.3)
        self.setYRange(lo - pad, hi + pad, padding=0)
        self.setXRange(-0.5, max(count // 2, len(shown)) - 0.5, padding=0)


class PoincarePlot(_SmallPlot):
    """Each interval against the next one. A tight cloud means steady rhythm."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._diag = self.plot([], [])
        self._cloud = pg.ScatterPlotItem(size=7, pen=pg.mkPen(None))
        self.addItem(self._cloud)
        self._last = pg.ScatterPlotItem(size=11)
        self.addItem(self._last)

    def apply_theme(self, c: dict) -> None:
        self._theme(c)
        self._diag.setPen(pg.mkPen(c["grid_major"], width=1.5, style=pg.QtCore.Qt.PenStyle.DashLine))
        self._cloud.setBrush(pg.mkBrush(_rgba(c["accent"], 150, 1).color()))
        self._last.setBrush(pg.mkBrush(c["wave"]))
        self._last.setPen(pg.mkPen(c["card"], width=2))
        self.showGrid(x=True, y=True, alpha=0.25)

    def update_beats(self, beats: list[Beat], count: int = 80) -> None:
        pairs = []
        seq = [b for b in beats if b.valid and b.ibi_ms is not None]
        for a, b in zip(seq, seq[1:]):
            if abs(b.t - b.ibi_ms / 1000.0 - a.t) < 1e-3:
                pairs.append((a.ibi_ms, b.ibi_ms))
        pairs = pairs[-count:]
        if len(pairs) < 3:
            self._cloud.setData([], [])
            self._last.setData([], [])
            self._diag.setData([], [])
            return
        xs = np.array([p[0] for p in pairs])
        ys = np.array([p[1] for p in pairs])
        self._cloud.setData(xs, ys)
        self._last.setData([xs[-1]], [ys[-1]])
        lo = float(min(xs.min(), ys.min()))
        hi = float(max(xs.max(), ys.max()))
        pad = max(40.0, (hi - lo) * 0.25)
        self._diag.setData([lo - pad, hi + pad], [lo - pad, hi + pad])
        self.setXRange(lo - pad, hi + pad, padding=0)
        self.setYRange(lo - pad, hi + pad, padding=0)


class TrendPlot(_SmallPlot):
    """BPM over the session, with the range it has covered."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._line = self.plot([], [])
        self._c = None

    def apply_theme(self, c: dict) -> None:
        self._theme(c)
        self._c = c
        self._line.setPen(pg.mkPen(c["wave"], width=2.2))
        fill = QColor(c["wave"])
        fill.setAlpha(40)
        self._line.setFillLevel(0)
        self._line.setBrush(pg.mkBrush(fill))
        self.showGrid(x=False, y=True, alpha=0.35)

    def update_history(self, history: list[tuple[float, float]], now: float, window: float = 300.0) -> None:
        pts = [(t - now, v) for t, v in history if now - t <= window]
        if len(pts) < 2:
            self._line.setData([], [])
            return
        x = np.array([p[0] for p in pts])
        y = np.array([p[1] for p in pts])
        lo, hi = float(y.min()), float(y.max())
        pad = max(6.0, (hi - lo) * 0.3)
        self._line.setFillLevel(lo - pad)
        self._line.setData(x, y)
        self.setYRange(lo - pad, hi + pad, padding=0)
        self.setXRange(-min(window, max(30.0, -x[0])), 0, padding=0)
