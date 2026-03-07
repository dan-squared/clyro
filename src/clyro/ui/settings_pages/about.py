import sys
from importlib.metadata import PackageNotFoundError, version as _pkg_version

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
)

from clyro import __version__
from clyro.ui import settings_theme as theme

try:
    _CLYRO_VERSION = _pkg_version("clyro")
except PackageNotFoundError:
    _CLYRO_VERSION = __version__

LABEL_STYLE = theme.LABEL_STYLE
SECTION_STYLE = theme.SECTION_STYLE
BTN_STYLE = theme.BUTTON_STYLE


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


class AboutPage(QWidget):
    def __init__(self, settings, tools_availability, check_updates_callback=None, update_now_callback=None):
        super().__init__()
        self.settings = settings
        self.tools = tools_availability
        self._check_updates_callback = check_updates_callback
        self._update_now_callback = update_now_callback
        self.setStyleSheet(
            f"background: transparent; color: {theme.TEXT_PRIMARY}; font-family: {theme.FONT_STACK};"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        sec, inner = _section("About Clyro")

        title_row = QHBoxLayout()
        title_lbl = QLabel("Clyro")
        title_lbl.setStyleSheet(
            f"font-size: 24px; font-weight: 700; color: {theme.TEXT_PRIMARY}; letter-spacing: -0.5px; font-family: {theme.FONT_STACK};"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        inner.addLayout(title_row)

        ver_lbl = QLabel(
            f"Version {_CLYRO_VERSION}  ·  Python {sys.version.split()[0]}  ·  PyQt6"
        )
        ver_lbl.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_MUTED};")
        inner.addWidget(ver_lbl)

        desc = QLabel("Drop a file. Hold a key to pick what happens. Get the result.")
        desc.setStyleSheet(f"font-size: 13px; color: {theme.TEXT_SECONDARY}; margin-top: 4px;")
        desc.setWordWrap(True)
        inner.addWidget(desc)
        layout.addWidget(sec)

        sec_status, inner_status = _section("System Status")
        self._access_value = QLabel("")
        self._disabled_value = QLabel("")
        self._update_mode_value = QLabel("")
        self._update_value = QLabel("Checks run in the background at startup.")
        for value in [self._access_value, self._disabled_value, self._update_mode_value, self._update_value]:
            value.setWordWrap(True)
            value.setStyleSheet(theme.VALUE_STYLE)

        inner_status.addLayout(self._status_row("Access", self._access_value))
        inner_status.addLayout(self._status_row("Features", self._disabled_value))
        inner_status.addLayout(self._status_row("Mode", self._update_mode_value))
        inner_status.addLayout(self._status_row("Updates", self._update_value))

        update_row = QHBoxLayout()
        update_row.setSpacing(8)
        self.btn_updates = QPushButton("Check for Updates")
        self.btn_updates.setStyleSheet(BTN_STYLE)
        self.btn_updates.setEnabled(self._check_updates_callback is not None)
        self.btn_updates.clicked.connect(self._request_update_check)
        self.btn_update_now = QPushButton("Update Now")
        self.btn_update_now.setStyleSheet(theme.PRIMARY_BUTTON_STYLE)
        self.btn_update_now.setVisible(False)
        self.btn_update_now.setEnabled(self._update_now_callback is not None)
        self.btn_update_now.clicked.connect(self._trigger_update_now)
        helper = QLabel("Use this for an immediate check or when automatic updates are turned off.")
        helper.setWordWrap(True)
        helper.setStyleSheet(theme.HINT_STYLE)
        update_row.addWidget(self.btn_updates)
        update_row.addWidget(self.btn_update_now)
        update_row.addWidget(helper, 1)
        inner_status.addLayout(update_row)
        layout.addWidget(sec_status)

        sec2, inner2 = _section("Tool Status")

        tools_info = [
            ("FFmpeg", getattr(self.tools, "ffmpeg", None), "Video optimization and conversion"),
            ("FFprobe", getattr(self.tools, "ffprobe", None), "Video duration and progress detection"),
            ("Ghostscript", getattr(self.tools, "ghostscript", None), "PDF optimization"),
            ("pngquant", getattr(self.tools, "pngquant", None), "PNG compression"),
        ]

        for name, path, purpose in tools_info:
            row = QHBoxLayout()
            row.setSpacing(8)

            dot = QLabel("●")
            dot.setStyleSheet(
                f"font-size: 9px; color: {theme.SUCCESS if path else theme.TEXT_FAINT}; padding-top: 2px;"
            )

            name_lbl = QLabel(name)
            name_lbl.setFixedWidth(100)
            name_lbl.setStyleSheet(
                f"font-size: 13px; font-weight: 700; color: {theme.TEXT_PRIMARY if path else theme.TEXT_MUTED};"
            )

            status_lbl = QLabel("Found" if path else "Not found")
            status_lbl.setFixedWidth(70)
            status_lbl.setStyleSheet(
                f"font-size: 12px; color: {theme.SUCCESS if path else theme.TEXT_MUTED};"
            )

            purpose_lbl = QLabel(purpose)
            purpose_lbl.setStyleSheet(theme.HINT_STYLE)

            row.addWidget(dot)
            row.addWidget(name_lbl)
            row.addWidget(status_lbl)
            row.addWidget(purpose_lbl)
            row.addStretch()
            inner2.addLayout(row)

        lib_divider = QFrame()
        lib_divider.setFrameShape(QFrame.Shape.HLine)
        lib_divider.setStyleSheet(f"{theme.DIVIDER_STYLE} margin: 4px 0;")
        inner2.addWidget(lib_divider)

        def _check(mod: str) -> bool:
            try:
                __import__(mod)
                return True
            except ImportError:
                return False

        libs = [
            ("mozjpeg", getattr(self.tools, 'mozjpeg', False)),
            ("pillow-heif", _check("pillow_heif")),
            ("pymupdf", _check("fitz")),
            ("pdf2docx", _check("pdf2docx")),
        ]
        for display, found in libs:
            row = QHBoxLayout()
            dot = QLabel("●")
            dot.setStyleSheet(
                f"font-size: 9px; color: {theme.SUCCESS if found else theme.TEXT_FAINT}; padding-top: 2px;"
            )
            name_lbl = QLabel(display)
            name_lbl.setFixedWidth(100)
            name_lbl.setStyleSheet(
                f"font-size: 13px; font-weight: 700; color: {theme.TEXT_PRIMARY if found else theme.TEXT_MUTED};"
            )
            status_lbl = QLabel("Available" if found else "Not installed")
            status_lbl.setFixedWidth(100)
            status_lbl.setStyleSheet(
                f"font-size: 12px; color: {theme.SUCCESS if found else theme.TEXT_MUTED};"
            )
            row.addWidget(dot)
            row.addWidget(name_lbl)
            row.addWidget(status_lbl)
            row.addStretch()
            inner2.addLayout(row)

        layout.addWidget(sec2)

        footer = QLabel("Missing tools reduce capability, but the app should remain usable.")
        footer.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_MUTED}; margin-top: 4px;")
        layout.addWidget(footer)
        layout.addStretch()

        self.refresh_status()

    def _status_row(self, label: str, value_label: QLabel) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        key = QLabel(label)
        key.setFixedWidth(70)
        key.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {theme.TEXT_MUTED};")
        row.addWidget(key)
        row.addWidget(value_label, 1)
        return row

    def _request_update_check(self):
        if self._check_updates_callback:
            self.set_update_status("Checking for updates…", "muted")
            self._check_updates_callback()

    def _trigger_update_now(self):
        if self._update_now_callback:
            self._update_now_callback()

    def _missing_feature_summary(self) -> str:
        missing = []
        if not getattr(self.tools, "ffmpeg", None):
            missing.append("video optimization and conversion")
        if not getattr(self.tools, "ghostscript", None):
            missing.append("PDF optimization")
        if not getattr(self.tools, "ffprobe", None):
            missing.append("video duration detection")
        if not any([getattr(self.tools, "pngquant", None), getattr(self.tools, "jpegoptim", None), getattr(self.tools, "gifsicle", None)]):
            missing.append("advanced image compression")

        if not missing:
            return "All core feature groups are available."
        return "Reduced availability: " + ", ".join(missing) + "."

    def refresh_status(self):
        access_parts = []
        if getattr(self.settings, "show_tray", True):
            access_parts.append("tray")
        if getattr(self.settings, "dropzone_enabled", True) or not getattr(self.settings, "show_tray", True):
            access_parts.append("floating dropzone")
        if not access_parts:
            access_parts.append("floating dropzone (forced visible for safety)")

        access_text = " + ".join(access_parts).title()
        if getattr(self.settings, "dropzone_require_alt", False):
            access_text += "  ·  Alt required before dropping"

        shortcut = getattr(self.settings, "shortcut_toggle_dropzone", "Ctrl+Alt+D")
        access_text += f"  ·  Toggle shortcut: {shortcut}"

        self._access_value.setText(access_text)
        self._disabled_value.setText(self._missing_feature_summary())
        if getattr(self.settings, "auto_update_enabled", True):
            self._update_mode_value.setText("Automatic install is on.")
        else:
            self._update_mode_value.setText("Automatic install is off. Manual checks stay available.")

    def set_update_status(self, message: str, tone: str = "muted"):
        tones = {
            "muted": theme.TEXT_SECONDARY,
            "success": theme.SUCCESS,
            "warning": theme.WARNING,
            "error": theme.ERROR,
        }
        self._update_value.setText(message)
        self._update_value.setStyleSheet(
            f"font-size: 12px; color: {tones.get(tone, tones['muted'])};"
        )

    def set_update_action(self, label: str | None = None, *, enabled: bool = True, visible: bool = True):
        if label:
            self.btn_update_now.setText(label)
        self.btn_update_now.setEnabled(enabled and self._update_now_callback is not None)
        self.btn_update_now.setVisible(visible)
