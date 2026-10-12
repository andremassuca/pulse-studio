"""Colour palettes and the application style sheet."""

LIGHT = {
    "name": "light",
    "bg": "#F3F4F8",
    "card": "#FFFFFF",
    "border": "#E2E5EE",
    "text": "#171B2A",
    "muted": "#6A7287",
    "accent": "#E0314B",
    "accent_dark": "#B3213A",
    "plot_bg": "#FFFFFF",
    "grid": "#E6E9F0",
    "grid_major": "#CBD1DE",
    "wave": "#0B8F63",
    "peak": "#E0314B",
    "good": "#17A673",
    "warn": "#E39A12",
    "bad": "#D8384B",
    "idle": "#B9BFCD",
    "button": "#EEF0F6",
    "button_hover": "#E3E6F0",
}

DARK = {
    "name": "dark",
    "bg": "#0C101A",
    "card": "#151A28",
    "border": "#232A3E",
    "text": "#EEF1F8",
    "muted": "#8D96AC",
    "accent": "#FF5A74",
    "accent_dark": "#D63A55",
    "plot_bg": "#0E1320",
    "grid": "#1B2236",
    "grid_major": "#2B3550",
    "wave": "#4EE0A0",
    "peak": "#FF5A74",
    "good": "#3DD598",
    "warn": "#F5B84A",
    "bad": "#FF6B7D",
    "idle": "#4A546C",
    "button": "#1D2335",
    "button_hover": "#262E45",
}

THEMES = {"light": LIGHT, "dark": DARK}

FONT_FAMILY = '"Segoe UI Variable Text", "Segoe UI", sans-serif'
DISPLAY_FAMILY = '"Segoe UI Variable Display", "Segoe UI", sans-serif'


def stylesheet(c: dict) -> str:
    return f"""
* {{ font-family: {FONT_FAMILY}; font-size: 13px; color: {c['text']}; }}
QMainWindow, QWidget#root {{ background: {c['bg']}; }}
QFrame#card {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 16px; }}
QLabel {{ background: transparent; }}
QLabel#title {{ font-family: {DISPLAY_FAMILY}; font-size: 20px; font-weight: 600; }}
QLabel#cardTitle {{ color: {c['muted']}; font-size: 12px; font-weight: 600; letter-spacing: 1px; }}
QLabel#cardValue {{ font-family: {DISPLAY_FAMILY}; font-size: 34px; font-weight: 600; }}
QLabel#cardUnit {{ color: {c['muted']}; font-size: 13px; }}
QLabel#hint {{ color: {c['muted']}; font-size: 12px; }}
QLabel#note {{ color: {c['muted']}; font-size: 11px; }}
QLabel#bpm {{ font-family: {DISPLAY_FAMILY}; font-size: 92px; font-weight: 600; }}
QLabel#bpmUnit {{ color: {c['muted']}; font-size: 14px; font-weight: 600; letter-spacing: 3px; }}
QLabel#chip {{ border-radius: 11px; padding: 3px 12px; font-size: 12px; font-weight: 600; }}
QPushButton {{ background: {c['button']}; border: none; border-radius: 10px;
               padding: 8px 16px; font-weight: 600; }}
QPushButton:hover {{ background: {c['button_hover']}; }}
QPushButton:disabled {{ color: {c['idle']}; }}
QPushButton#primary {{ background: {c['accent']}; color: white; }}
QPushButton#primary:hover {{ background: {c['accent_dark']}; }}
QPushButton#recording {{ background: {c['bad']}; color: white; }}
QPushButton#seg {{ background: transparent; border-radius: 8px; padding: 5px 12px; color: {c['muted']}; }}
QPushButton#seg:checked {{ background: {c['button']}; color: {c['text']}; }}
QPushButton#seg:hover {{ background: {c['button_hover']}; }}
QPushButton#icon {{ padding: 8px 10px; }}
QComboBox {{ background: {c['button']}; border: none; border-radius: 10px; padding: 7px 12px;
             min-width: 230px; font-weight: 600; }}
QComboBox:hover {{ background: {c['button_hover']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {c['card']}; border: 1px solid {c['border']};
             selection-background-color: {c['button_hover']}; selection-color: {c['text']};
             padding: 4px; outline: none; }}
QToolTip {{ background: {c['card']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 4px; }}
"""
