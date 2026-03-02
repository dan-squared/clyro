import sys
from importlib.metadata import version as _pkg_version, PackageNotFoundError
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PyQt6.QtCore import Qt

try:
    _CLYRO_VERSION = _pkg_version("clyro")
except PackageNotFoundError:
    _CLYRO_VERSION = "dev"

LABEL_STYLE = "font-size: 11px; font-weight: 600; color: rgba(255,255,255,0.45); letter-spacing: 0.8px;"
SECTION_STYLE = """
    QFrame#section {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 10px;
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


class AboutPage(QWidget):
    def __init__(self, tools_availability):
        super().__init__()
        self.tools = tools_availability
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ── App Info ──────────────────────────────────────────────────
        sec, inner = _section("About Clyro")

        title_row = QHBoxLayout()
        title_lbl = QLabel("Clyro")
        title_lbl.setStyleSheet(
            "font-size: 22px; font-weight: 700; color: rgba(255,255,255,0.9); letter-spacing: -0.5px;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        inner.addLayout(title_row)

        ver_lbl = QLabel(
            f"Version {_CLYRO_VERSION}  ·  Python {sys.version.split()[0]}  ·  PyQt6"
        )
        ver_lbl.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.35);")
        inner.addWidget(ver_lbl)

        desc = QLabel("Drop a file. Hold a key to pick what happens. Get the result.")
        desc.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.5); margin-top: 4px;")
        desc.setWordWrap(True)
        inner.addWidget(desc)
        layout.addWidget(sec)

        # ── Tool Status ───────────────────────────────────────────────
        sec2, inner2 = _section("Tool Status")

        tools_info = [
            ("FFmpeg",       getattr(self.tools, "ffmpeg", None),       "Video optimization & conversion"),
            ("FFprobe",      getattr(self.tools, "ffprobe", None),      "Video duration detection"),
            ("Ghostscript",  getattr(self.tools, "ghostscript", None),  "PDF optimization"),
            ("pngquant",     getattr(self.tools, "pngquant", None),     "PNG compression"),
        ]

        for name, path, purpose in tools_info:
            row = QHBoxLayout()
            row.setSpacing(8)

            dot = QLabel("●")
            if path:
                dot.setStyleSheet("font-size: 9px; color: rgba(255,255,255,0.5); padding-top: 2px;")
            else:
                dot.setStyleSheet("font-size: 9px; color: rgba(255,255,255,0.15); padding-top: 2px;")

            name_lbl = QLabel(name)
            name_lbl.setFixedWidth(100)
            if path:
                name_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.8);")
            else:
                name_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.25);")

            if path:
                status_lbl = QLabel("Found")
                status_lbl.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.45);")
            else:
                status_lbl = QLabel("Not found")
                status_lbl.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.2);")
            status_lbl.setFixedWidth(70)

            purpose_lbl = QLabel(purpose)
            purpose_lbl.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.2);")

            row.addWidget(dot)
            row.addWidget(name_lbl)
            row.addWidget(status_lbl)
            row.addWidget(purpose_lbl)
            row.addStretch()
            inner2.addLayout(row)

        # Python libraries (no path check, import check)
        lib_divider = QFrame()
        lib_divider.setFrameShape(QFrame.Shape.HLine)
        lib_divider.setStyleSheet("color: rgba(255,255,255,0.06); margin: 4px 0;")
        inner2.addWidget(lib_divider)

        def _check(mod: str) -> bool:
            try:
                __import__(mod)
                return True
            except ImportError:
                return False

        libs = [
            ("mozjpeg",     getattr(self.tools, 'mozjpeg', False)),
            ("pillow-heif", _check("pillow_heif")),
            ("pymupdf",     _check("fitz")),
            ("pdf2docx",    _check("pdf2docx")),
        ]
        for display, found in libs:
            row = QHBoxLayout()
            dot = QLabel("●")
            dot.setStyleSheet(
                f"font-size: 9px; color: rgba(255,255,255,{'0.5' if found else '0.15'}); padding-top: 2px;"
            )
            name_lbl = QLabel(display)
            name_lbl.setFixedWidth(100)
            name_lbl.setStyleSheet(
                f"font-size: 13px; font-weight: 600; color: rgba(255,255,255,{'0.8' if found else '0.25'});"
            )
            status_lbl = QLabel("Available" if found else "Not installed")
            status_lbl.setFixedWidth(100)
            status_lbl.setStyleSheet(
                f"font-size: 12px; color: rgba(255,255,255,{'0.45' if found else '0.2'});"
            )
            row.addWidget(dot)
            row.addWidget(name_lbl)
            row.addWidget(status_lbl)
            row.addStretch()
            inner2.addLayout(row)

        layout.addWidget(sec2)

        footer = QLabel("Missing tools reduce capability — Clyro still runs fine.")
        footer.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.2); margin-top: 4px;")
        layout.addWidget(footer)
        layout.addStretch()
