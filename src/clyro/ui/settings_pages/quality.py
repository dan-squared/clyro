from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QCheckBox, QFrame, QPushButton, QRadioButton, QButtonGroup,
    QSpinBox, QComboBox
)
from PyQt6.QtCore import Qt
from clyro.config.presets import QUALITY_PRESETS

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
RADIO_STYLE = """
    QRadioButton {
        font-size: 13px; color: rgba(255,255,255,0.85); spacing: 10px; padding: 2px 0;
    }
    QRadioButton::indicator {
        width: 16px; height: 16px; border-radius: 8px;
        border: 1.5px solid rgba(255,255,255,0.25); background: transparent;
    }
    QRadioButton::indicator:hover {
        border: 1.5px solid rgba(255,255,255,0.5);
    }
    QRadioButton::indicator:checked {
        border: 4px solid rgba(255,255,255,0.15); background: #FFFFFF;
    }
"""
SLIDER_STYLE = """
    QSlider::groove:horizontal {
        height: 4px; background: rgba(255,255,255,0.12); border-radius: 2px;
    }
    QSlider::handle:horizontal {
        width: 14px; height: 14px; margin: -5px 0;
        border-radius: 7px; background: rgba(255,255,255,0.85);
        border: none;
    }
    QSlider::sub-page:horizontal {
        background: rgba(255,255,255,0.6); border-radius: 2px;
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

def _spinbox_row(label: str, min_val: int, max_val: int, suffix: str = "") -> tuple[QHBoxLayout, QSpinBox]:
    row = QHBoxLayout()
    lbl = QLabel(label)
    lbl.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.75);")
    lbl.setFixedWidth(140)
    
    sb = QSpinBox()
    sb.setRange(min_val, max_val)
    sb.setSuffix(suffix)
    sb.setStyleSheet("""
        QSpinBox {
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 6px;
            padding: 4px 28px 4px 10px;
            font-size: 12px; color: rgba(255,255,255,0.85);
        }
        QSpinBox::up-button, QSpinBox::down-button {
            width: 20px;
            background: rgba(255,255,255,0.06);
            border: none;
            border-left: 1px solid rgba(255,255,255,0.08);
        }
        QSpinBox::up-button { border-top-right-radius: 6px; }
        QSpinBox::down-button { border-bottom-right-radius: 6px; }
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {
            background: rgba(255,255,255,0.12);
        }
        QSpinBox::up-arrow {
            image: none; border: none;
            border-left: 4px solid transparent; border-right: 4px solid transparent;
            border-bottom: 5px solid rgba(255,255,255,0.5);
            width: 0; height: 0;
        }
        QSpinBox::down-arrow {
            image: none; border: none;
            border-left: 4px solid transparent; border-right: 4px solid transparent;
            border-top: 5px solid rgba(255,255,255,0.5);
            width: 0; height: 0;
        }
    """)
    sb.setFixedWidth(110)
    
    info_lbl = QLabel("(0 to disable)")
    info_lbl.setStyleSheet("font-size: 11px; color: rgba(255,255,255,0.3);")
    
    row.addWidget(lbl)
    row.addWidget(sb)
    row.addWidget(info_lbl)
    row.addStretch()
    return row, sb

def _slider_row(label: str, lo: int, hi: int) -> tuple[QHBoxLayout, QSlider, QLabel]:
    row = QHBoxLayout()
    lbl = QLabel(label)
    lbl.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.75);")
    lbl.setFixedWidth(140)
    sl = QSlider(Qt.Orientation.Horizontal)
    sl.setRange(lo, hi)
    sl.setStyleSheet(SLIDER_STYLE)
    val_lbl = QLabel(str(sl.value()))
    val_lbl.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.5); font-family: monospace; min-width: 28px;")
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
        self.setStyleSheet("background: transparent;")
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
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,0.06);
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 7px; padding: 6px 20px;
                    font-size: 12px; font-weight: 600;
                    color: rgba(255,255,255,0.6);
                }
                QPushButton:checked {
                    background: rgba(255,255,255,0.14);
                    border-color: rgba(255,255,255,0.35);
                    color: rgba(255,255,255,0.95);
                }
                QPushButton:hover:!checked { background: rgba(255,255,255,0.09); }
            """)
            btn.clicked.connect(lambda _, n=name.lower(): self._apply_preset(n))
            self.preset_btns[name.lower()] = btn
            preset_row.addWidget(btn)

        self.preset_desc = QLabel("")
        self.preset_desc.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.4); margin-top: 2px;")
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
        divider_pdf.setStyleSheet("color: rgba(255,255,255,0.07);")
        inner4.addWidget(divider_pdf)

        merge_lbl = QLabel("MERGE SORT ORDER")
        merge_lbl.setStyleSheet(LABEL_STYLE)
        inner4.addWidget(merge_lbl)

        merge_row = QHBoxLayout()
        merge_row.setSpacing(8)
        merge_desc = QLabel("Sort images before merging to PDF:")
        merge_desc.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.75);")
        COMBO_STYLE = """
            QComboBox {
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 6px; padding: 5px 10px;
                font-size: 12px; color: rgba(255,255,255,0.85);
                min-width: 130px;
            }
            QComboBox:hover { border-color: rgba(255,255,255,0.25); }
            QComboBox::drop-down {
                border: none; width: 20px;
                subcontrol-position: right center;
            }
            QComboBox::down-arrow {
                image: none; border: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid rgba(255,255,255,0.5);
                width: 0; height: 0;
            }
            QComboBox QAbstractItemView {
                background: #2A2A2A; border: 1px solid rgba(255,255,255,0.15);
                border-radius: 6px; color: rgba(255,255,255,0.85);
                selection-background-color: rgba(255,255,255,0.12);
                padding: 4px;
            }
        """
        self.combo_merge_sort = QComboBox()
        self.combo_merge_sort.setStyleSheet(COMBO_STYLE)
        self.combo_merge_sort.addItem("Drop order", "none")
        self.combo_merge_sort.addItem("Name (A → Z)", "name_asc")
        self.combo_merge_sort.addItem("Name (Z → A)", "name_desc")
        self.combo_merge_sort.addItem("Date (Oldest first)", "date_asc")
        self.combo_merge_sort.addItem("Date (Newest first)", "date_desc")
        merge_row.addWidget(merge_desc)
        merge_row.addWidget(self.combo_merge_sort)
        merge_row.addStretch()
        inner4.addLayout(merge_row)

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
