"""Colour palettes and the application style sheet.

"light" is the Studio look: warm paper background, serif headings, coral
accent. "dark" is the Monitor look: near black with a glowing green trace,
like a patient monitor.
"""

LIGHT = {
    "name": "light",
    "label": "Studio (light)",
    "bg": "#FBF8F5",
    "sidebar": "#F6F1EC",
    "card": "#FFFFFF",
    "card_tint": "#FCEEEC",
    "border": "#EDE6DF",
    "text": "#1F1A19",
    "muted": "#8B817B",
    "accent": "#E5484D",
    "accent_dark": "#C93A40",
    "accent_soft": "#FBE3E1",
    "plot_bg": "#FFFFFF",
    "grid": "#F1ECE7",
    "grid_major": "#DED6CE",
    "wave": "#E5484D",
    "glow": 0,
    "peak": "#E5484D",
    "good": "#2E9E6B",
    "warn": "#D98E0B",
    "bad": "#E5484D",
    "idle": "#C9BFB7",
    "button": "#F3EDE7",
    "button_hover": "#EBE3DB",
    "nav_active": "#FBE3E1",
    "title_font": '"Georgia", "Cambria", serif',
    "numeric_font": '"Georgia", "Cambria", serif',
}

DARK = {
    "name": "dark",
    "label": "Monitor (dark)",
    "bg": "#04070B",
    "sidebar": "#070C12",
    "card": "#0A1017",
    "card_tint": "#0F1A1A",
    "border": "#15202B",
    "text": "#DDE9F1",
    "muted": "#6D8296",
    "accent": "#FF4D5E",
    "accent_dark": "#D43348",
    "accent_soft": "#2A1219",
    "plot_bg": "#03080A",
    "grid": "#0D1B18",
    "grid_major": "#15342A",
    "wave": "#3DFF9A",
    "glow": 1,
    "peak": "#FF4D5E",
    "good": "#3DE59A",
    "warn": "#FFC24A",
    "bad": "#FF5D6E",
    "idle": "#3A4959",
    "button": "#101A24",
    "button_hover": "#18242F",
    "nav_active": "#13222B",
    # Bahnschrift is the DIN style face that ships with Windows 10 and 11.
    "title_font": '"Bahnschrift", "Segoe UI Variable Display", "Segoe UI", sans-serif',
    "numeric_font": '"Bahnschrift", "Segoe UI Variable Display", "Segoe UI", sans-serif',
}

THEMES = {"light": LIGHT, "dark": DARK}

FONT_FAMILY = '"Segoe UI Variable Text", "Segoe UI", sans-serif'


def stylesheet(c: dict) -> str:
    return f"""
* {{ font-family: {FONT_FAMILY}; font-size: 13px; color: {c['text']}; }}
QMainWindow, QWidget#root, QWidget#page, QStackedWidget {{ background: {c['bg']}; }}
QFrame#sidebar {{ background: {c['sidebar']}; border: none; border-right: 1px solid {c['border']}; }}
QFrame#card {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; }}
QFrame#cardTint {{ background: {c['card_tint']}; border: 1px solid {c['border']}; border-radius: 14px; }}
QFrame#divider {{ background: {c['border']}; border: none; max-height: 1px; min-height: 1px; }}
QLabel {{ background: transparent; }}
QLabel#appName {{ font-family: {c['title_font']}; font-size: 19px; font-weight: 600; }}
QLabel#pageTitle {{ font-family: {c['title_font']}; font-size: 34px; font-weight: 700; }}
QLabel#sub {{ color: {c['muted']}; font-size: 14px; }}
QLabel#sectionTitle {{ font-family: {c['title_font']}; font-size: 24px; font-weight: 700; }}
QLabel#cardTitle {{ color: {c['text']}; font-size: 14px; font-weight: 600; }}
QLabel#miniTitle {{ color: {c['muted']}; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; }}
QLabel#value {{ font-family: {c['numeric_font']}; font-size: 40px; font-weight: 700; }}
QLabel#valueSmall {{ font-family: {c['numeric_font']}; font-size: 28px; font-weight: 700; }}
QLabel#word {{ font-family: {c['title_font']}; font-size: 36px; font-weight: 700; }}
QLabel#unit {{ color: {c['muted']}; font-size: 15px; }}
QLabel#hint {{ color: {c['muted']}; font-size: 12px; }}
QLabel#note {{ color: {c['muted']}; font-size: 11px; }}
QLabel#bpm {{ font-family: {c['numeric_font']}; font-size: 76px; font-weight: 700; }}
QLabel#status {{ color: {c['text']}; font-size: 13px; font-weight: 600; }}
QLabel#chip {{ border-radius: 11px; padding: 3px 12px; font-size: 12px; font-weight: 700; }}
QPushButton {{ background: {c['button']}; border: none; border-radius: 10px;
               padding: 8px 16px; font-weight: 600; }}
QPushButton:hover {{ background: {c['button_hover']}; }}
QPushButton:disabled {{ color: {c['idle']}; }}
QPushButton#primary {{ background: {c['accent']}; color: white; }}
QPushButton#primary:hover {{ background: {c['accent_dark']}; }}
QPushButton#primary:disabled {{ background: {c['button']}; color: {c['idle']}; }}
QPushButton#outline {{ background: transparent; border: 1px solid {c['border']}; }}
QPushButton#outline:hover {{ background: {c['button']}; }}
QPushButton#seg {{ background: transparent; border-radius: 8px; padding: 5px 13px; color: {c['muted']}; }}
QPushButton#seg:checked {{ background: {c['accent_soft']}; color: {c['text']}; }}
QPushButton#seg:hover {{ background: {c['button_hover']}; }}
QPushButton#nav {{ background: transparent; text-align: left; padding: 11px 14px; border-radius: 10px;
                    font-size: 15px; font-weight: 500; color: {c['text']}; }}
QPushButton#nav:hover {{ background: {c['button']}; }}
QPushButton#nav:checked {{ background: {c['nav_active']}; font-weight: 700; }}
QPushButton#link {{ background: transparent; color: {c['muted']}; padding: 4px 8px; }}
QPushButton#link:hover {{ color: {c['text']}; }}
QComboBox {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 10px;
             padding: 7px 12px; min-width: 200px; font-weight: 600; }}
QComboBox:hover {{ background: {c['button']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {c['card']}; border: 1px solid {c['border']};
             selection-background-color: {c['button_hover']}; selection-color: {c['text']};
             padding: 4px; outline: none; }}
QLineEdit {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 7px 12px; }}
QCheckBox {{ spacing: 8px; }}
QTableWidget {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px;
                gridline-color: transparent; outline: none; }}
QTableWidget::item {{ padding: 6px 10px; border-bottom: 1px solid {c['border']}; }}
QTableWidget::item:selected {{ background: {c['accent_soft']}; color: {c['text']}; }}
QHeaderView::section {{ background: {c['card']}; color: {c['muted']}; border: none;
                        border-bottom: 1px solid {c['border']}; padding: 8px 10px; font-weight: 700; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {c['idle']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: {c['card']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 4px; }}
"""
