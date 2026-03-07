from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QRadioButton, QButtonGroup,
    QCheckBox, QLineEdit, QPushButton, QLabel, QFrame, QFileDialog,
    QComboBox
)
from PyQt6.QtCore import Qt
from clyro.ui import settings_theme as theme

LABEL_STYLE = theme.LABEL_STYLE
SECTION_STYLE = theme.SECTION_STYLE
RADIO_STYLE = theme.RADIO_STYLE
CHECKBOX_STYLE = theme.CHECKBOX_STYLE
INPUT_STYLE = theme.INPUT_STYLE
BTN_STYLE = theme.BUTTON_STYLE
COMBO_STYLE = theme.COMBO_STYLE

def _section(title: str) -> tuple[QFrame, QVBoxLayout]:
    """Returns a styled section card and its inner layout."""
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

class GeneralPage(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setStyleSheet(
            f"background: transparent; color: {theme.TEXT_PRIMARY}; font-family: {theme.FONT_STACK};"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ── Output Mode ──────────────────────────────────────────────
        sec, inner = _section("Output")
        self.mode_group = QButtonGroup(self)

        self.rb_same = QRadioButton("Same folder  (adds _optimized suffix)")
        self.rb_same.setStyleSheet(RADIO_STYLE)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        self.rb_specific = QRadioButton("Specific folder:")
        self.rb_specific.setStyleSheet(RADIO_STYLE)
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Choose a folder…")
        self.folder_edit.setStyleSheet(INPUT_STYLE)
        self.folder_edit.setEnabled(False)
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setStyleSheet(BTN_STYLE)
        self.browse_btn.setEnabled(False)
        self.browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.rb_specific)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(self.browse_btn)

        self.rb_inplace = QRadioButton("In-place  (overwrites original)")
        self.rb_inplace.setStyleSheet(RADIO_STYLE)

        for rb in [self.rb_same, self.rb_specific, self.rb_inplace]:
            self.mode_group.addButton(rb)

        inner.addWidget(self.rb_same)
        inner.addLayout(folder_row)
        inner.addWidget(self.rb_inplace)

        output_hint = QLabel(
            "Same folder is the safest default. In-place rewrites the original file, so backups matter more."
        )
        output_hint.setWordWrap(True)
        output_hint.setStyleSheet(theme.HINT_STYLE)
        inner.addWidget(output_hint)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(theme.DIVIDER_STYLE)
        inner.addWidget(divider)

        self.chk_skip = QCheckBox("Skip if output is larger\nthan original")
        self.chk_skip.setStyleSheet(CHECKBOX_STYLE)
        inner.addWidget(self.chk_skip)
        skip_hint = QLabel("Keeps the source untouched when compression would produce a larger file.")
        skip_hint.setWordWrap(True)
        skip_hint.setStyleSheet(theme.HINT_STYLE)
        inner.addWidget(skip_hint)

        layout.addWidget(sec)

        # ── Web Downloads ─────────────────────────────────────────────
        sec_web, inner_web = _section("Web Downloads")
        
        web_folder_row = QHBoxLayout()
        web_folder_row.setSpacing(8)
        self.lbl_web_folder = QLabel("Save dropped URLs to:")
        self.lbl_web_folder.setStyleSheet(theme.BODY_TEXT_STYLE)
        
        self.web_folder_edit = QLineEdit()
        self.web_folder_edit.setPlaceholderText("Default Downloads folder...")
        self.web_folder_edit.setStyleSheet(INPUT_STYLE)
        self.web_folder_edit.setReadOnly(True)
        
        self.web_browse_btn = QPushButton("Browse")
        self.web_browse_btn.setStyleSheet(BTN_STYLE)
        self.web_browse_btn.clicked.connect(self._browse_web_folder)
        
        web_folder_row.addWidget(self.lbl_web_folder)
        web_folder_row.addWidget(self.web_folder_edit, 1)
        web_folder_row.addWidget(self.web_browse_btn)
        
        inner_web.addLayout(web_folder_row)

        self.chk_keep_web_originals = QCheckBox("Keep original downloaded files\nwhen dropping URLs")
        self.chk_keep_web_originals.setStyleSheet(CHECKBOX_STYLE)
        inner_web.addWidget(self.chk_keep_web_originals)
        web_hint = QLabel(
            "Use this if dropped URLs should leave the original download intact and create a second optimized or converted file."
        )
        web_hint.setWordWrap(True)
        web_hint.setStyleSheet(theme.HINT_STYLE)
        inner_web.addWidget(web_hint)

        layout.addWidget(sec_web)

        # ── App Behavior ──────────────────────────────────────────────
        sec2, inner2 = _section("App Behavior")

        self.chk_preserve_dates = QCheckBox("Preserve original file dates")
        self.chk_preserve_dates.setStyleSheet(CHECKBOX_STYLE)

        self.chk_auto_copy = QCheckBox("Auto-copy optimized items to clipboard")
        self.chk_auto_copy.setStyleSheet(CHECKBOX_STYLE)

        self.chk_login = QCheckBox("Launch at login")
        self.chk_login.setStyleSheet(CHECKBOX_STYLE)
        self.chk_tray = QCheckBox("Show in system tray")
        self.chk_tray.setStyleSheet(CHECKBOX_STYLE)
        self.chk_auto_update = QCheckBox("Install updates automatically")
        self.chk_auto_update.setStyleSheet(CHECKBOX_STYLE)

        inner2.addWidget(self.chk_preserve_dates)
        inner2.addWidget(self.chk_auto_copy)
        inner2.addWidget(self.chk_login)
        inner2.addWidget(self.chk_tray)
        inner2.addWidget(self.chk_auto_update)
        behavior_hint = QLabel(
            "If the tray is hidden, keep the floating dropzone enabled or rely on the toggle shortcut for access."
        )
        behavior_hint.setWordWrap(True)
        behavior_hint.setStyleSheet(theme.HINT_STYLE)
        inner2.addWidget(behavior_hint)
        update_hint = QLabel(
            "Automatic updates are enabled by default. When turned on, Clyro downloads and installs the latest release in the background."
        )
        update_hint.setWordWrap(True)
        update_hint.setStyleSheet(theme.HINT_STYLE)
        inner2.addWidget(update_hint)
        layout.addWidget(sec2)

        # ── Auto Convert ──────────────────────────────────────────────
        sec_ac, inner_ac = _section("Auto Convert")

        self.chk_auto_convert = QCheckBox("Enable auto-convert on drop")
        self.chk_auto_convert.setStyleSheet(CHECKBOX_STYLE)
        inner_ac.addWidget(self.chk_auto_convert)

        # Format mapping: from → valid targets
        self._convert_map = {
            "jpg":  ["png", "webp", "pdf"],
            "jpeg": ["png", "webp", "pdf"],
            "png":  ["jpg", "webp", "pdf"],
            "webp": ["jpg", "png", "pdf"],
            "bmp":  ["jpg", "png", "webp", "pdf"],
            "tiff": ["jpg", "png", "webp", "pdf"],
            "heic": ["jpg", "png", "webp", "pdf"],
            "avif": ["jpg", "png", "webp", "pdf"],
            "ico":  ["jpg", "png", "webp"],
            "gif":  ["mp4", "webm", "jpg", "png", "webp"],
            "mp4":  ["webm", "gif"],
            "mov":  ["mp4", "webm", "gif"],
            "mkv":  ["mp4", "webm"],
            "webm": ["mp4", "gif"],
            "avi":  ["mp4", "webm", "gif"],
            "pdf":  ["jpg", "png"],
        }

        from_to_row = QHBoxLayout()
        from_to_row.setSpacing(8)
        lbl_from = QLabel("From")
        lbl_from.setStyleSheet(theme.BODY_TEXT_STYLE)
        self.combo_ac_from = QComboBox()
        self.combo_ac_from.setStyleSheet(COMBO_STYLE)
        for fmt in sorted(self._convert_map.keys()):
            self.combo_ac_from.addItem(fmt.upper(), fmt)

        lbl_arrow = QLabel("→")
        lbl_arrow.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {theme.TEXT_MUTED};")
        lbl_arrow.setFixedWidth(20)
        lbl_arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_to = QLabel("To")
        lbl_to.setStyleSheet(theme.BODY_TEXT_STYLE)
        self.combo_ac_to = QComboBox()
        self.combo_ac_to.setStyleSheet(COMBO_STYLE)

        from_to_row.addWidget(lbl_from)
        from_to_row.addWidget(self.combo_ac_from)
        from_to_row.addWidget(lbl_arrow)
        from_to_row.addWidget(lbl_to)
        from_to_row.addWidget(self.combo_ac_to)
        from_to_row.addStretch()
        inner_ac.addLayout(from_to_row)

        # Replace / Keep copy
        self.ac_mode_group = QButtonGroup(self)
        self.rb_ac_copy    = QRadioButton("Keep a copy  (original stays)")
        self.rb_ac_replace = QRadioButton("Replace original")
        for rb in [self.rb_ac_copy, self.rb_ac_replace]:
            rb.setStyleSheet(RADIO_STYLE)
            self.ac_mode_group.addButton(rb)
        self.rb_ac_copy.setChecked(True)
        inner_ac.addWidget(self.rb_ac_copy)
        inner_ac.addWidget(self.rb_ac_replace)

        layout.addWidget(sec_ac)

        # Wire auto-convert controls
        self.combo_ac_from.currentIndexChanged.connect(self._update_ac_to_options)
        self.chk_auto_convert.toggled.connect(self._toggle_ac_controls)

        layout.addStretch()

        # Wire up specific-folder toggling
        self.rb_specific.toggled.connect(lambda on: (
            self.folder_edit.setEnabled(on),
            self.browse_btn.setEnabled(on)
        ))

        self.load_settings()

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder",
                                                self.folder_edit.text() or "")
        if path:
            self.folder_edit.setText(path)

    def _browse_web_folder(self):
        default_dir = self.web_folder_edit.text() or str(Path.home() / "Downloads")
        path = QFileDialog.getExistingDirectory(self, "Select Web Download Folder", default_dir)
        if path:
            self.web_folder_edit.setText(path)

    def _update_ac_to_options(self):
        """Repopulate 'To' combo based on selected 'From' format."""
        from_fmt = self.combo_ac_from.currentData()
        if not from_fmt:
            return
        prev_to = self.combo_ac_to.currentData()
        self.combo_ac_to.blockSignals(True)
        self.combo_ac_to.clear()
        targets = self._convert_map.get(from_fmt, [])
        for t in targets:
            self.combo_ac_to.addItem(t.upper(), t)
        # Try to keep previous selection if still valid
        idx = self.combo_ac_to.findData(prev_to)
        self.combo_ac_to.setCurrentIndex(idx if idx >= 0 else 0)
        self.combo_ac_to.blockSignals(False)

    def _toggle_ac_controls(self, on: bool):
        """Enable/disable auto-convert sub-controls."""
        self.combo_ac_from.setEnabled(on)
        self.combo_ac_to.setEnabled(on)
        self.rb_ac_copy.setEnabled(on)
        self.rb_ac_replace.setEnabled(on)

    def load_settings(self):
        mode = self.settings.output_mode
        if mode == "same_folder":
            self.rb_same.setChecked(True)
        elif mode == "specific_folder":
            self.rb_specific.setChecked(True)
            self.folder_edit.setEnabled(True)
            self.browse_btn.setEnabled(True)
        else:
            self.rb_inplace.setChecked(True)

        self.folder_edit.setText(self.settings.output_folder or "")
        self.web_folder_edit.setText(self.settings.web_download_folder or "")
        self.chk_skip.setChecked(self.settings.skip_if_larger)
        self.chk_keep_web_originals.setChecked(self.settings.keep_web_originals)
        self.chk_preserve_dates.setChecked(getattr(self.settings, 'preserve_dates', True))
        self.chk_auto_copy.setChecked(getattr(self.settings, 'auto_copy_to_clipboard', False))
        self.chk_login.setChecked(self.settings.start_on_login)
        self.chk_tray.setChecked(self.settings.show_tray)
        self.chk_auto_update.setChecked(getattr(self.settings, 'auto_update_enabled', True))

        # Auto-convert
        ac_on = getattr(self.settings, 'auto_convert_enabled', False)
        self.chk_auto_convert.setChecked(ac_on)
        ac_from = getattr(self.settings, 'auto_convert_from', 'png')
        idx = self.combo_ac_from.findData(ac_from)
        if idx >= 0:
            self.combo_ac_from.setCurrentIndex(idx)
        self._update_ac_to_options()
        ac_to = getattr(self.settings, 'auto_convert_to', 'webp')
        idx_to = self.combo_ac_to.findData(ac_to)
        if idx_to >= 0:
            self.combo_ac_to.setCurrentIndex(idx_to)
        if getattr(self.settings, 'auto_convert_replace', False):
            self.rb_ac_replace.setChecked(True)
        else:
            self.rb_ac_copy.setChecked(True)
        self._toggle_ac_controls(ac_on)

    def save_settings(self):
        if self.rb_same.isChecked():
            self.settings.output_mode = "same_folder"
        elif self.rb_specific.isChecked():
            self.settings.output_mode = "specific_folder"
        else:
            self.settings.output_mode = "in_place"

        self.settings.output_folder = self.folder_edit.text() or None
        self.settings.web_download_folder = self.web_folder_edit.text() or None
        self.settings.skip_if_larger = self.chk_skip.isChecked()
        self.settings.keep_web_originals = self.chk_keep_web_originals.isChecked()
        self.settings.preserve_dates = self.chk_preserve_dates.isChecked()
        self.settings.auto_copy_to_clipboard = self.chk_auto_copy.isChecked()
        self.settings.start_on_login = self.chk_login.isChecked()
        self.settings.show_tray = self.chk_tray.isChecked()
        self.settings.auto_update_enabled = self.chk_auto_update.isChecked()

        # Auto-convert
        self.settings.auto_convert_enabled = self.chk_auto_convert.isChecked()
        self.settings.auto_convert_from = self.combo_ac_from.currentData() or 'png'
        self.settings.auto_convert_to = self.combo_ac_to.currentData() or 'webp'
        self.settings.auto_convert_replace = self.rb_ac_replace.isChecked()
