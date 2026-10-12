import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def pump(app, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def test_window_runs_through_every_page_and_feature(app, tmp_path):
    from PySide6.QtCore import QSettings

    from pulse_studio.ui.main_window import DEMO_KEY, MainWindow

    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    settings.setValue("record_folder", str(tmp_path))
    win = MainWindow(settings)
    win.show()
    win.port_box.setCurrentIndex(win.port_box.findData(DEMO_KEY))
    win.toggle_connection()
    assert win.session.active

    pump(app, 1.5)
    for index in range(4):
        win._go(index)
        pump(app, 0.3)

    win._go(1)
    for mode in ("sweep", "scroll"):
        win.set_mode(mode)
        pump(app, 0.2)
    for span in (5, 30, 10):
        win.set_span(span)
        pump(app, 0.2)

    win.set_theme("dark")
    pump(app, 0.3)
    win.set_theme("light")

    win.toggle_recording()
    pump(app, 1.5)
    win.toggle_pause()
    pump(app, 0.3)
    win.toggle_pause()
    win.toggle_recording()
    win._go(2)
    win.sessions_page.reload()
    assert win.sessions_page.table.rowCount() == 1

    exported = tmp_path / "export.csv"
    assert win.session.export_buffer(exported) > 100
    assert exported.read_text().startswith("t_s,adc,filtered,beat")

    win.disconnect_source()
    assert not win.session.active
    win.close()


def test_settings_are_remembered(app, tmp_path):
    from PySide6.QtCore import QSettings

    from pulse_studio.ui.main_window import MainWindow

    path = str(tmp_path / "s.ini")
    first = MainWindow(QSettings(path, QSettings.Format.IniFormat))
    first.set_theme("dark")
    first.set_span(30)
    first.close()
    second = MainWindow(QSettings(path, QSettings.Format.IniFormat))
    assert second._theme == "dark"
    assert second.dashboard.controls.span_buttons[30].isChecked()
    second.close()
