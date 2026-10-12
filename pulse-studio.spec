# PyInstaller spec. Build with: pyinstaller pulse-studio.spec --noconfirm
from pathlib import Path

root = Path(SPECPATH)

a = Analysis(
    [str(root / "launcher.py")],
    pathex=[str(root / "src")],
    datas=[
        (str(root / "assets" / "icon.ico"), "assets"),
        (str(root / "assets" / "icon.png"), "assets"),
    ],
    hiddenimports=["serial.tools.list_ports_windows"],
    excludes=[
        "matplotlib", "PIL", "tkinter", "pytest", "IPython",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
        "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.QtPdf", "PySide6.QtSql", "PySide6.QtTest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Pulse Studio",
    icon=str(root / "assets" / "icon.ico"),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Pulse Studio", upx=False)
