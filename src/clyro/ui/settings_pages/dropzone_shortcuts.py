from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QFrame, QLineEdit
)
from PyQt6.QtCore import Qt

LABEL_STYLE = "font-size: 11px; font-weight: 600; color: rgba(255,255,255,0.45); letter-spacing: 0.8px;"
SECTION_STYLE = """
    QFrame#section {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 10px;
    }
"""
CHECKBOX_STYLE = """
    QCheckBox {
        font-size: 13px; color: rgba(255,255,255,0.85); spacing: 10px; padding: 2px 0;
    }
    QCheckBox::indicator {
        width: 18px; height: 18px; border-radius: 4px;
        border: 1.5px solid rgba(255,255,255,0.25); background: transparent;
    }
    QCheckBox::indicator:hover {
        border: 1.5px solid rgba(255,255,255,0.5);
    }
    QCheckBox::indicator:checked {
        border: 1.5px solid #FFFFFF; background: #FFFFFF;
        image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMjIyMjIyIiBzdHJva2Utd2lkdGg9IjQiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBvbHlsaW5lIHBvaW50cz0iMjAgNiA5IDE3IDQgMTIiPjwvcG9seWxpbmU+PC9zdmc+");
    }
"""
INPUT_STYLE = """
    QLineEdit {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 6px;
        padding: 5px 10px;
        font-size: 12px;
        color: rgba(255,255,255,0.75);
        font-family: 'SF Mono', Consolas, Menlo, monospace;
    }
    QLineEdit:focus {
        border-color: rgba(255,255,255,0.3);
        background: rgba(255,255,255,0.08);
    }
"""


def _section(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("section")
    frame.setStyleSheet(SECTION_STYLE)
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(16, 14, 16, 16)
    outer.setSpacing(12)
    if title:
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(LABEL_STYLE)
        outer.addWidget(lbl)
    inner = QVBoxLayout()
    inner.setContentsMargins(0, 0, 0, 0)
    inner.setSpacing(8)
    outer.addLayout(inner)
    return frame, inner


class DropzoneShortcutsPage(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ── Dropzone Behavior ─────────────────────────────────────────
        sec, inner = _section("Dropzone")

        self.chk_enabled = QCheckBox("Show dropzone when dragging files")
        self.chk_enabled.setStyleSheet(CHECKBOX_STYLE)
        self.chk_require_alt = QCheckBox("Require Alt key to show dropzone")
        self.chk_require_alt.setStyleSheet(CHECKBOX_STYLE)

        inner.addWidget(self.chk_enabled)
        inner.addWidget(self.chk_require_alt)
        layout.addWidget(sec)

        # ── Drop Modes Reference Card ─────────────────────────────────
        sec2, inner2 = _section("Drop Modes")

        ref = QLabel(
            "<span style='color: rgba(255,255,255,0.5);'>These are fixed by design and not configurable:</span>"
        )
        ref.setWordWrap(True)
        ref.setStyleSheet("font-size: 12px;")
        inner2.addWidget(ref)

        modes = [
            ("Drop",           "Optimize with current preset"),
            ("Shift + Drop",   "Aggressive optimization (max compression)"),
            ("Alt + Drop",     "Convert — opens format picker"),
        ]
        for key, desc in modes:
            row = QHBoxLayout()
            row.setSpacing(0)
            key_lbl = QLabel(key)
            key_lbl.setStyleSheet(
                "font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.7); "
                "font-family: 'SF Mono', Consolas, monospace; min-width: 130px;"
            )
            arrow = QLabel("→")
            arrow.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.25); margin: 0 10px;")
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.5);")
            row.addWidget(key_lbl)
            row.addWidget(arrow)
            row.addWidget(desc_lbl)
            row.addStretch()
            inner2.addLayout(row)

        layout.addWidget(sec2)

        layout.addStretch()
        self.load_settings()

    def load_settings(self):
        self.chk_enabled.setChecked(self.settings.dropzone_enabled)
        self.chk_require_alt.setChecked(self.settings.dropzone_require_alt)

    def save_settings(self):
        self.settings.dropzone_enabled = self.chk_enabled.isChecked()
        self.settings.dropzone_require_alt = self.chk_require_alt.isChecked()
