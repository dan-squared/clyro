from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QCheckBox, QFrame, QPushButton, QRadioButton, QButtonGroup,
    QSpinBox, QComboBox
)
from PyQt6.QtCore import Qt
from clyro.config.presets import QUALITY_PRESETS
from clyro.ui import settings_theme as theme

LABEL_STYLE = theme.LABEL_STYLE
SECTION_STYLE = theme.SECTION_STYLE
CHECKBOX_STYLE = theme.CHECKBOX_STYLE
RADIO_STYLE = theme.RADIO_STYLE
SLIDER_STYLE = theme.SLIDER_STYLE

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

def _spinbox_row(label: str, min_val: int, max_val: int, suffix: str = "") -> tuple[QHBoxLayout, QSpinBox]:
    row = QHBoxLayout()
    lbl = QLabel(label)
    lbl.setStyleSheet(theme.BODY_TEXT_STYLE)
    lbl.setFixedWidth(140)
    
    sb = QSpinBox()
    sb.setRange(min_val, max_val)
    sb.setSuffix(suffix)
    sb.setStyleSheet(theme.SPINBOX_STYLE)
    sb.setFixedWidth(110)
    
    info_lbl = QLabel("(0 to disable)")
    info_lbl.setStyleSheet(theme.HINT_STYLE)
    
    row.addWidget(lbl)
    row.addWidget(sb)
    row.addWidget(info_lbl)
    row.addStretch()
    return row, sb

def _slider_row(label: str, lo: int, hi: int) -> tuple[QHBoxLayout, QSlider, QLabel]:
    row = QHBoxLayout()
    lbl = QLabel(label)
    lbl.setStyleSheet(theme.BODY_TEXT_STYLE)
    lbl.setFixedWidth(140)
    sl = QSlider(Qt.Orientation.Horizontal)
    sl.setRange(lo, hi)
    sl.setStyleSheet(SLIDER_STYLE)
    val_lbl = QLabel(str(sl.value()))
    val_lbl.setStyleSheet(
        f"font-size: 12px; color: {theme.TEXT_MUTED}; min-width: 28px; font-family: {theme.NUMERIC_FONT_STACK};"
    )
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
    sl.valueChanged.connect(lambda v: val_lbl.setText(str(v)))
    row.addWidget(lbl)
    row.addWidget(sl, 1)
    row.addWidget(val_lbl)
    return row, sl, val_lbl

class QualityPage(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setStyleSheet(
            f"background: transparent; color: {theme.TEXT_PRIMARY}; font-family: {theme.FONT_STACK};"
        )
        self._block = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ── Preset Selector ───────────────────────────────────────────
        sec, inner = _section("Optimization Preset")

        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        self.preset_btns: dict[str, QPushButton] = {}
        for name in ["Balanced", "Max"]:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: {theme.SURFACE_ALT};
                    border: 1px solid {theme.BORDER};
                    border-radius: 8px;
                    padding: 7px 20px;
                    font-size: 12px;
                    font-weight: 700;
                    color: {theme.TEXT_SECONDARY};
                    font-family: {theme.FONT_STACK};
                }}
                QPushButton:checked {{
                    background: {theme.ACCENT};
                    border-color: {theme.ACCENT};
                    color: {theme.SURFACE_BG};
                }}
                QPushButton:hover:!checked {{
                    background: #ede1d0;
                    border-color: {theme.BORDER_STRONG};
                }}
                """
            )
            btn.clicked.connect(lambda _, n=name.lower(): self._apply_preset(n))
            self.preset_btns[name.lower()] = btn
            preset_row.addWidget(btn)

        self.preset_desc = QLabel("")
        self.preset_desc.setStyleSheet(
            f"font-size: 12px; color: {theme.TEXT_MUTED}; margin-top: 2px;"
        )
        self.preset_desc.setWordWrap(True)

        inner.addLayout(preset_row)
        inner.addWidget(self.preset_desc)
        layout.addWidget(sec)

        # ── Images ────────────────────────────────────────────────────
        sec2, inner2 = _section("Images")

        size_img_row, self.sb_img_size = _spinbox_row("Skip if >", 0, 9999, " MB")

        jpg_row, self.sl_jpg, _ = _slider_row("JPEG quality", 10, 100)
        webp_row, self.sl_webp, _ = _slider_row("WebP quality", 10, 100)

        self.sl_jpg.valueChanged.connect(self._mark_custom)
        self.sl_webp.valueChanged.connect(self._mark_custom)

        self.chk_meta = QCheckBox("Preserve metadata (EXIF)")
        self.chk_meta.setStyleSheet(CHECKBOX_STYLE)
        self.chk_meta.stateChanged.connect(self._mark_custom)

        inner2.addLayout(size_img_row)
        inner2.addLayout(jpg_row)
        inner2.addLayout(webp_row)
        inner2.addWidget(self.chk_meta)
        img_hint = QLabel(
            "Turning metadata preservation off removes EXIF and location data, which can improve privacy and reduce size."
        )
        img_hint.setWordWrap(True)
        img_hint.setStyleSheet(theme.HINT_STYLE)
        inner2.addWidget(img_hint)
        layout.addWidget(sec2)

        # ── Video ─────────────────────────────────────────────────────
        sec3, inner3 = _section("Video")

        size_vid_row, self.sb_vid_size = _spinbox_row("Skip if >", 0, 99999, " MB")

        crf_row, self.sl_crf, _ = _slider_row("CRF (quality)", 0, 51)
        self.sl_crf.valueChanged.connect(self._mark_custom)
        self.chk_no_audio = QCheckBox("Remove audio track")
        self.chk_no_audio.setStyleSheet(CHECKBOX_STYLE)
        self.chk_no_audio.stateChanged.connect(self._mark_custom)

        inner3.addLayout(size_vid_row)
        inner3.addLayout(crf_row)
        inner3.addWidget(self.chk_no_audio)
        vid_hint = QLabel("Lower CRF keeps more quality but produces larger files. Removing audio is irreversible.")
        vid_hint.setWordWrap(True)
        vid_hint.setStyleSheet(theme.HINT_STYLE)
        inner3.addWidget(vid_hint)
        layout.addWidget(sec3)

        # ── PDF ───────────────────────────────────────────────────────
        sec4, inner4 = _section("PDF")

        size_pdf_row, self.sb_pdf_size = _spinbox_row("Skip if >", 0, 9999, " MB")
        
        self.pdf_group = QButtonGroup(self)
        self.rb_pdf_rec  = QRadioButton("Normal  (good quality, moderate savings)")
        self.rb_pdf_ext  = QRadioButton("Aggressive  (smallest size, some quality loss)")
        inner4.addLayout(size_pdf_row)
        for rb in [self.rb_pdf_rec, self.rb_pdf_ext]:
            rb.setStyleSheet(RADIO_STYLE)
            self.pdf_group.addButton(rb)
            inner4.addWidget(rb)
            rb.toggled.connect(self._mark_custom)

        # ── Merge sort order ──
        divider_pdf = QFrame()
        divider_pdf.setFrameShape(QFrame.Shape.HLine)
        divider_pdf.setStyleSheet(theme.DIVIDER_STYLE)
        inner4.addWidget(divider_pdf)

        merge_lbl = QLabel("MERGE SORT ORDER")
        merge_lbl.setStyleSheet(LABEL_STYLE)
        inner4.addWidget(merge_lbl)

        merge_row = QHBoxLayout()
        merge_row.setSpacing(8)
        merge_desc = QLabel("Sort images before merging to PDF:")
        merge_desc.setStyleSheet(theme.BODY_TEXT_STYLE)
        self.combo_merge_sort = QComboBox()
        self.combo_merge_sort.setStyleSheet(theme.COMBO_STYLE)
        self.combo_merge_sort.addItem("Drop order", "none")
        self.combo_merge_sort.addItem("Name (A → Z)", "name_asc")
        self.combo_merge_sort.addItem("Name (Z → A)", "name_desc")
        self.combo_merge_sort.addItem("Date (Oldest first)", "date_asc")
        self.combo_merge_sort.addItem("Date (Newest first)", "date_desc")
        merge_row.addWidget(merge_desc)
        merge_row.addWidget(self.combo_merge_sort)
        merge_row.addStretch()
        inner4.addLayout(merge_row)
        pdf_hint = QLabel(
            "Aggressive PDF compression saves more space but may reduce fidelity. Merge sorting changes the output page order."
        )
        pdf_hint.setWordWrap(True)
        pdf_hint.setStyleSheet(theme.HINT_STYLE)
        inner4.addWidget(pdf_hint)

        layout.addWidget(sec4)

        layout.addStretch()
        self.load_settings()

    def _apply_preset(self, key: str):
        if self._block:
            return
        if key not in QUALITY_PRESETS:
            return
        p = QUALITY_PRESETS[key]
        self._block = True
        self.sl_jpg.setValue(p.get("image_jpeg_quality", 80))
        self.sl_webp.setValue(p.get("image_webp_quality", 75))
        self.sl_crf.setValue(p.get("video_crf", 23))
        self.chk_meta.setChecked(p.get("image_preserve_metadata", True))
        self.chk_no_audio.setChecked(p.get("video_remove_audio", False))
        pdf = p.get("pdf_compression", "recommended")
        if pdf == "extreme": self.rb_pdf_ext.setChecked(True)
        else: self.rb_pdf_rec.setChecked(True)

        # Update button states
        for name, btn in self.preset_btns.items():
            btn.setChecked(name == key)
        self._update_desc(key)
        self._block = False

    def _mark_custom(self):
        if self._block:
            return
        for btn in self.preset_btns.values():
            btn.setChecked(False)
        self._update_desc("custom")

    def _update_desc(self, key: str):
        descs = {
            "balanced": "Balanced — good trade-off between quality and file size.",
            "max":      "Max — aggressive compression, some visible quality loss.",
            "custom":   "Custom — your own manual adjustments.",
        }
        self.preset_desc.setText(descs.get(key, ""))

    def load_settings(self):
        self._block = True
        
        self.sb_img_size.setValue(getattr(self.settings, 'image_max_size_mb', 150))
        self.sb_vid_size.setValue(getattr(self.settings, 'video_max_size_mb', 1000))
        self.sb_pdf_size.setValue(getattr(self.settings, 'pdf_max_size_mb', 500))

        self.sl_jpg.setValue(self.settings.image_jpeg_quality)
        self.sl_webp.setValue(self.settings.image_webp_quality)
        self.sl_crf.setValue(self.settings.video_crf)
        self.chk_meta.setChecked(self.settings.image_preserve_metadata)
        self.chk_no_audio.setChecked(self.settings.video_remove_audio)

        pdf = self.settings.pdf_compression
        if pdf == "extreme": self.rb_pdf_ext.setChecked(True)
        else: self.rb_pdf_rec.setChecked(True)

        sort_order = getattr(self.settings, 'pdf_merge_sort_order', 'none')
        idx = self.combo_merge_sort.findData(sort_order)
        if idx >= 0:
            self.combo_merge_sort.setCurrentIndex(idx)

        pkey = self.settings.quality_preset
        for name, btn in self.preset_btns.items():
            btn.setChecked(name == pkey)
        self._update_desc(pkey)
        self._block = False

    def save_settings(self):
        # Determine active preset
        active = next((k for k, b in self.preset_btns.items() if b.isChecked()), "custom")
        self.settings.quality_preset = active

        self.settings.image_max_size_mb = self.sb_img_size.value()
        self.settings.video_max_size_mb = self.sb_vid_size.value()
        self.settings.pdf_max_size_mb = self.sb_pdf_size.value()

        self.settings.image_jpeg_quality = self.sl_jpg.value()
        self.settings.image_webp_quality = self.sl_webp.value()
        self.settings.video_crf = self.sl_crf.value()
        self.settings.image_preserve_metadata = self.chk_meta.isChecked()
        self.settings.video_remove_audio = self.chk_no_audio.isChecked()

        if self.rb_pdf_ext.isChecked():
            self.settings.pdf_compression = "extreme"
        else:
            self.settings.pdf_compression = "recommended"

        self.settings.pdf_merge_sort_order = self.combo_merge_sort.currentData() or "none"
