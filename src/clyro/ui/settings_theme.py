from __future__ import annotations

from PyQt6.QtGui import QFontDatabase

WINDOW_BG = "#f4f5f7"
WINDOW_PANEL = "#ffffff"
SIDEBAR_BG = "#ffffff"
SURFACE_BG = "#ffffff"
SURFACE_ALT = "#f7f8fa"
BORDER = "#e7e9ee"
BORDER_STRONG = "#d6dae3"
TEXT_PRIMARY = "#14171c"
TEXT_SECONDARY = "#333844"
TEXT_MUTED = "#717784"
TEXT_FAINT = "#b0b6c2"
ACCENT = "#353b45"
ACCENT_HOVER = "#444b57"
SUCCESS = "#138a5c"
WARNING = "#a26b14"
ERROR = "#d64e4e"

_FONT_FILES = ()
_fonts_loaded = False


def ensure_fonts_loaded():
    global _fonts_loaded
    if _fonts_loaded:
        return

    for relative_path in _FONT_FILES:
        path = resource_path(relative_path)
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))

    _fonts_loaded = True


FONT_STACK = '-apple-system, "Segoe UI", BlinkMacSystemFont, sans-serif'
VALUE_FONT_STACK = FONT_STACK
NUMERIC_FONT_STACK = '"JetBrains Mono", "Consolas", monospace'

_CHECKMARK = (
    "data:image/svg+xml;base64,"
    "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIg"
    "ZmlsbD0ibm9uZSIgc3Ryb2tlPSIjZmZmZmZmIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2Fw"
    "PSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBvbHlsaW5lIHBvaW50cz0iMjAgNiA5IDE3"
    "IDQgMTIiPjwvcG9seWxpbmU+PC9zdmc+"
)

LABEL_STYLE = (
    f"font-size: 11px; font-weight: 700; color: {TEXT_MUTED}; font-family: {FONT_STACK}; "
    "letter-spacing: 1px; text-transform: uppercase;"
)
HINT_STYLE = (
    f"font-size: 12px; color: {TEXT_MUTED}; line-height: 1.45; font-family: {FONT_STACK};"
)
BODY_TEXT_STYLE = f"font-size: 14px; color: {TEXT_SECONDARY}; font-family: {FONT_STACK};"
VALUE_STYLE = f"font-size: 13px; color: {TEXT_SECONDARY}; font-family: {FONT_STACK};"
DIVIDER_STYLE = f"color: {BORDER}; background: {BORDER};"
SECTION_STYLE = f"""
    QFrame#section {{
        background: {SURFACE_BG};
        border: 1px solid {BORDER};
        border-radius: 16px;
    }}
"""

RADIO_STYLE = f"""
    QRadioButton {{
        font-size: 14px;
        color: {TEXT_PRIMARY};
        spacing: 10px;
        padding: 5px 0;
        font-family: {FONT_STACK};
    }}
    QRadioButton::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 8px;
        border: 1px solid {BORDER_STRONG};
        background: {SURFACE_BG};
    }}
    QRadioButton::indicator:hover {{
        border: 1px solid {ACCENT};
    }}
    QRadioButton::indicator:checked {{
        border: 5px solid {ACCENT};
        background: {SURFACE_BG};
    }}
"""

CHECKBOX_STYLE = f"""
    QCheckBox {{
        font-size: 14px;
        color: {TEXT_PRIMARY};
        spacing: 10px;
        padding: 5px 0;
        font-family: {FONT_STACK};
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 5px;
        border: 1px solid {BORDER_STRONG};
        background: {SURFACE_BG};
    }}
    QCheckBox::indicator:hover {{
        border: 1px solid {ACCENT};
    }}
    QCheckBox::indicator:checked {{
        border: 1px solid {ACCENT};
        background: {ACCENT};
        image: url("{_CHECKMARK}");
    }}
"""

INPUT_STYLE = f"""
    QLineEdit {{
        background: {SURFACE_BG};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 9px 12px;
        font-size: 12px;
        color: {TEXT_PRIMARY};
        font-family: {FONT_STACK};
    }}
    QLineEdit:focus {{
        border-color: {ACCENT};
        background: {SURFACE_BG};
    }}
    QLineEdit:disabled {{
        color: {TEXT_MUTED};
        background: {SURFACE_ALT};
    }}
"""

BUTTON_STYLE = f"""
    QPushButton {{
        background: {SURFACE_ALT};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 9px 14px;
        font-size: 12px;
        color: {TEXT_PRIMARY};
        font-family: {FONT_STACK};
    }}
    QPushButton:hover {{
        background: #f0f2f5;
        border-color: {BORDER_STRONG};
    }}
    QPushButton:pressed {{
        background: #eceff3;
    }}
    QPushButton:disabled {{
        color: {TEXT_FAINT};
        background: {SURFACE_ALT};
    }}
"""

PRIMARY_BUTTON_STYLE = f"""
    QPushButton {{
        background: {ACCENT};
        border: 1px solid {ACCENT};
        border-radius: 10px;
        padding: 9px 16px;
        font-size: 12px;
        font-weight: 700;
        color: {SURFACE_BG};
        font-family: {FONT_STACK};
    }}
    QPushButton:hover {{
        background: {ACCENT_HOVER};
        border-color: {ACCENT_HOVER};
    }}
    QPushButton:pressed {{
        background: #000000;
    }}
"""

SUBTLE_BUTTON_STYLE = f"""
    QPushButton {{
        background: {SURFACE_BG};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 9px 14px;
        font-size: 12px;
        color: {TEXT_SECONDARY};
        font-family: {FONT_STACK};
    }}
    QPushButton:hover {{
        background: {SURFACE_ALT};
        border-color: {BORDER_STRONG};
    }}
    QPushButton:pressed {{
        background: #f0f2f5;
    }}
"""

LINK_BUTTON_STYLE = f"""
    QPushButton {{
        background: transparent;
        border: none;
        font-size: 13px;
        font-weight: 600;
        color: {TEXT_MUTED};
        text-align: left;
        font-family: {FONT_STACK};
    }}
    QPushButton:hover {{
        color: {ACCENT};
    }}
"""

COMBO_STYLE = f"""
    QComboBox {{
        background: {SURFACE_BG};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 9px 12px;
        font-size: 12px;
        color: {TEXT_PRIMARY};
        min-width: 96px;
        font-family: {FONT_STACK};
    }}
    QComboBox:hover {{
        border-color: {BORDER_STRONG};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
        subcontrol-position: right center;
    }}
    QComboBox::down-arrow {{
        image: none;
        border: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {TEXT_MUTED};
        width: 0;
        height: 0;
    }}
    QComboBox QAbstractItemView {{
        background: {SURFACE_BG};
        border: 1px solid {BORDER};
        border-radius: 10px;
        color: {TEXT_PRIMARY};
        selection-background-color: {SURFACE_ALT};
        selection-color: {TEXT_PRIMARY};
        padding: 4px;
        font-family: {FONT_STACK};
    }}
"""

SPINBOX_STYLE = f"""
    QSpinBox {{
        background: {SURFACE_BG};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 8px 30px 8px 12px;
        font-size: 12px;
        color: {TEXT_PRIMARY};
        font-family: {NUMERIC_FONT_STACK};
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        width: 20px;
        background: {SURFACE_BG};
        border: none;
    }}
    QSpinBox::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        margin: 5px 5px 0 0;
    }}
    QSpinBox::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        margin: 0 5px 5px 0;
    }}
    QSpinBox::up-arrow {{
        image: none;
        border: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-bottom: 5px solid {TEXT_MUTED};
        width: 0;
        height: 0;
    }}
    QSpinBox::down-arrow {{
        image: none;
        border: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {TEXT_MUTED};
        width: 0;
        height: 0;
    }}
"""

SLIDER_STYLE = f"""
    QSlider::groove:horizontal {{
        height: 4px;
        background: #eceef2;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
        background: {ACCENT};
        border: none;
    }}
    QSlider::sub-page:horizontal {{
        background: {ACCENT};
        border-radius: 2px;
    }}
"""
