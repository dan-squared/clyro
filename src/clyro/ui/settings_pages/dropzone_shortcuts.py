from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QFrame
)
from clyro.ui import settings_theme as theme

LABEL_STYLE = theme.LABEL_STYLE
SECTION_STYLE = theme.SECTION_STYLE
CHECKBOX_STYLE = theme.CHECKBOX_STYLE

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
        self.setStyleSheet(
            f"background: transparent; color: {theme.TEXT_PRIMARY}; font-family: {theme.FONT_STACK};"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ── Dropzone Behavior ─────────────────────────────────────────
        sec, inner = _section("Dropzone")

        self.chk_enabled = QCheckBox("Keep floating dropzone available")
        self.chk_enabled.setStyleSheet(CHECKBOX_STYLE)
        self.chk_require_alt = QCheckBox("Require Alt before accepting drops")
        self.chk_require_alt.setStyleSheet(CHECKBOX_STYLE)
        self.chk_enabled.toggled.connect(lambda _: self._update_summary())
        self.chk_require_alt.toggled.connect(lambda _: self._update_summary())

        inner.addWidget(self.chk_enabled)
        inner.addWidget(self.chk_require_alt)
        hint = QLabel(
            "This controls the floating dropzone itself. It does not enable automatic drag-triggered reveal from anywhere on screen."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(theme.HINT_STYLE)
        inner.addWidget(hint)

        self.lbl_access_summary = QLabel("")
        self.lbl_access_summary.setWordWrap(True)
        self.lbl_access_summary.setStyleSheet(theme.VALUE_STYLE)
        inner.addWidget(self.lbl_access_summary)
        layout.addWidget(sec)

        # ── Drop Modes Reference Card ─────────────────────────────────
        sec2, inner2 = _section("Drop Modes")

        ref = QLabel(
            f"<span style='color: {theme.TEXT_MUTED};'>These are fixed by design and not configurable:</span>"
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
                f"font-size: 12px; font-weight: 700; color: {theme.ACCENT}; min-width: 130px;"
            )
            arrow = QLabel("→")
            arrow.setStyleSheet(
                f"font-size: 12px; color: {theme.TEXT_MUTED}; margin: 0 10px;"
            )
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet(theme.VALUE_STYLE)
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
        self._update_summary()

    def save_settings(self):
        self.settings.dropzone_enabled = self.chk_enabled.isChecked()
        self.settings.dropzone_require_alt = self.chk_require_alt.isChecked()
        self._update_summary()

    def _update_summary(self):
        access = "floating dropzone"
        if getattr(self.settings, "show_tray", True):
            access += " + tray"
        if self.chk_require_alt.isChecked():
            access += "  ·  Alt required before dropping"
        shortcut = getattr(self.settings, "shortcut_toggle_dropzone", "Ctrl+Alt+D")
        access += f"  ·  Toggle shortcut: {shortcut}"
        self.lbl_access_summary.setText(f"Current saved access path: {access}")
