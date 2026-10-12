"""Entry point: python -m pulse_studio"""

import sys


def main() -> int:
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    if sys.platform == "win32":
        import ctypes

        # Own taskbar identity, so the icon is not grouped under python.exe.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PulseStudio.App")

    app = QApplication(sys.argv)
    app.setApplicationName("Pulse Studio")
    app.setOrganizationName("Pulse Studio")
    app.setFont(QFont("Segoe UI Variable Text", 10))

    from .ui.branding import app_icon, make_splash

    app.setWindowIcon(app_icon())
    splash = make_splash()
    splash.show()
    app.processEvents()

    settings = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                         "Pulse Studio", "settings")
    from .ui.main_window import MainWindow

    window = MainWindow(settings)
    geometry = settings.value("geometry")
    if geometry:
        window.restoreGeometry(geometry)
    window.show()
    splash.finish(window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
