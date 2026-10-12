"""The live waveform and the tachogram."""

import numpy as np
import pyqtgraph as pg
from PySide6.QtGui import QColor, QFont

from ..dsp import Beat


def _nice_step(span: float, divisions: int = 4) -> float:
    raw = span / divisions
    mag = 10 ** np.floor(np.log10(max(raw, 1e-9)))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return float(m * mag)
    return float(10 * mag)


class WavePlot(pg.PlotWidget):
    """Scrolling PPG trace, drawn relative to the play head.

    The x axis is time before now in seconds. Grid lines sit at fixed
    positions on screen, like a monitor, while the trace scrolls under them.
    Peaks are drawn once the play head has reached them.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMenuEnabled(False)
        self.setMouseEnabled(False, False)
        self.hideButtons()
        self.setAntialiasing(True)
        self.span = 10.0
        self._half = 3.0  # smoothed half height of the y range
        self.getPlotItem().hideAxis("left")
        self.getPlotItem().layout.setContentsMargins(6, 8, 10, 4)
        self._curve = self.plot([], [], pen=pg.mkPen("#0B8F63", width=2.2))
        self._curve.setClipToView(True)
        self._peaks = pg.ScatterPlotItem(size=11, pen=pg.mkPen("#ffffff", width=2),
                                         brush=pg.mkBrush("#E0314B"))
        self._rejected = pg.ScatterPlotItem(size=9, pen=pg.mkPen("#8A93A8", width=2),
                                            brush=pg.mkBrush(None))
        self.addItem(self._peaks)
        self.addItem(self._rejected)
        self.set_span(10.0)

    def apply_theme(self, c: dict) -> None:
        self.setBackground(c["plot_bg"])
        axis = self.getAxis("bottom")
        axis.setPen(pg.mkPen(c["grid_major"]))
        axis.setTextPen(pg.mkPen(c["muted"]))
        axis.setStyle(tickFont=QFont("Segoe UI", 9))
        self._curve.setPen(pg.mkPen(c["wave"], width=2.2))
        self._peaks.setBrush(pg.mkBrush(c["peak"]))
        self._peaks.setPen(pg.mkPen(c["plot_bg"], width=2))
        self._rejected.setPen(pg.mkPen(c["idle"], width=2))
        self._grid = c
        self.showGrid(x=True, y=True, alpha=0.5 if c["name"] == "light" else 0.35)

    def set_span(self, seconds: float) -> None:
        self.span = seconds
        major = 1.0 if seconds <= 10 else 5.0
        axis = self.getAxis("bottom")
        axis.setTickSpacing(major, major / 5)
        self.setXRange(-seconds, 0, padding=0)

    def update_view(self, t, y, beats: list[Beat], playhead: float) -> None:
        if t.size == 0:
            self._curve.setData([], [])
            self._peaks.setData([], [])
            self._rejected.setData([], [])
            return
        lo = int(np.searchsorted(t, playhead - self.span - 0.2))
        hi = int(np.searchsorted(t, playhead, side="right"))
        tv, yv = t[lo:hi] - playhead, y[lo:hi]
        # Thin the trace so the cost does not grow with the window.
        step = max(1, int(len(tv) / 1400))
        self._curve.setData(tv[::step], yv[::step])

        if yv.size > 50:
            level = float(np.percentile(np.abs(yv), 99))
            target = max(2.2, level * 1.35)
            self._half += 0.08 * (target - self._half)
        ticks = _nice_step(2 * self._half)
        self.getAxis("left").setTickSpacing(ticks, ticks / 5)
        self.setYRange(-self._half, self._half, padding=0)

        good_x, good_y, bad_x, bad_y = [], [], [], []
        for b in beats:
            if playhead - self.span - 0.5 <= b.t <= playhead:
                (good_x if b.valid or b.ibi_ms is None else bad_x).append(b.t - playhead)
                (good_y if b.valid or b.ibi_ms is None else bad_y).append(b.height)
        self._peaks.setData(good_x, good_y)
        self._rejected.setData(bad_x, bad_y)


class TachoPlot(pg.PlotWidget):
    """Beat to beat interval over the last beats."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMenuEnabled(False)
        self.setMouseEnabled(False, False)
        self.hideButtons()
        self.setAntialiasing(True)
        self.getPlotItem().layout.setContentsMargins(4, 6, 8, 2)
        self.getAxis("left").setWidth(44)
        self._line = self.plot([], [], pen=pg.mkPen("#E0314B", width=2))
        self._dots = pg.ScatterPlotItem(size=7)
        self.addItem(self._dots)
        self._invalid = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(None))
        self.addItem(self._invalid)

    def apply_theme(self, c: dict) -> None:
        self.setBackground(c["card"])
        for name in ("left", "bottom"):
            ax = self.getAxis(name)
            ax.setPen(pg.mkPen(c["grid_major"]))
            ax.setTextPen(pg.mkPen(c["muted"]))
            ax.setStyle(tickFont=QFont("Segoe UI", 9))
        self._line.setPen(pg.mkPen(c["accent"], width=2))
        self._dots.setBrush(pg.mkBrush(c["accent"]))
        self._dots.setPen(pg.mkPen(c["card"], width=1.5))
        self._invalid.setPen(pg.mkPen(c["idle"], width=1.8))
        self.showGrid(x=False, y=True, alpha=0.4)

    def update_beats(self, beats: list[Beat], count: int = 40) -> None:
        shown = [b for b in beats if b.ibi_ms is not None][-count:]
        if len(shown) < 2:
            self._line.setData([], [])
            self._dots.setData([], [])
            self._invalid.setData([], [])
            return
        x = np.arange(len(shown), dtype=float)
        y = np.array([b.ibi_ms for b in shown])
        ok = np.array([b.valid for b in shown])
        self._line.setData(x[ok], y[ok])
        self._dots.setData(x[ok], y[ok])
        self._invalid.setData(x[~ok], y[~ok])
        lo, hi = float(y.min()), float(y.max())
        pad = max(40.0, (hi - lo) * 0.25)
        self.setYRange(lo - pad, hi + pad, padding=0)
        self.setXRange(-0.5, max(count // 2, len(shown)) - 0.5, padding=0)


def to_qcolor(value: str) -> QColor:
    return QColor(value)
