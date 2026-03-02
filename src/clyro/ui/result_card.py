import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QProgressBar, QFrame, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QMimeData, QUrl, QTimer
from PyQt6.QtGui import QIcon, QDrag, QMouseEvent
import logging

logger = logging.getLogger(__name__)

# ─── Helpers ────────────────────────────────────────────────────────────────

def _icon(name: str) -> QIcon:
    from clyro.utils.paths import resource_path
    return QIcon(str(resource_path(f"clyro/assets/icons/phosphor/{name}")))

def _fmt(bytes_: int) -> str:
    if bytes_ < 1024:
        return f"{bytes_} B"
    if bytes_ < 1024 ** 2:
        return f"{bytes_ / 1024:.0f} KB"
    return f"{bytes_ / (1024 ** 2):.1f} MB"

# ─── Compact Card ────────────────────────────────────────────────────────────

class ResultCard(QWidget):
    """
    A compact ~68px tall row card that lives inside the dropzone scroll area.

    States
    ------
    queued      → dimmed name, "Queued" text, no progress bar
    processing  → bright name, live progress bar, dimmed pct text
    done        → name, size diff text, reveal / dismiss buttons
    failed      → name, error text
    """
    dismiss_requested = pyqtSignal(str)   # emits job_id

    _CARD_STYLE = """
        QFrame#card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 12px;
        }
    """
    _BAR_STYLE = """
        QProgressBar {
            border: none;
            background: rgba(255,255,255,0.10);
            border-radius: 2px;
        }
        QProgressBar::chunk {
            background: rgba(255,255,255,0.70);
            border-radius: 2px;
        }
    """
    _BTN_STYLE = """
        QPushButton {
            background: rgba(255,255,255,0.08);
            border: none;
            border-radius: 6px;
            color: rgba(255,255,255,0.65);
            font-size: 11px;
            padding: 3px 9px;
        }
        QPushButton:hover { background: rgba(255,255,255,0.14); color: rgba(255,255,255,0.9); }
    """

    def __init__(self, job_id: str, filename: str, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.output_path: Path | None = None
        self._drag_start_pos = None
        self.setFixedHeight(68)

        # ── Card frame ──────────────────────────────────────────────
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._card = QFrame()
        self._card.setObjectName("card")
        self._card.setStyleSheet(self._CARD_STYLE)
        outer.addWidget(self._card)

        inner = QVBoxLayout(self._card)
        inner.setContentsMargins(14, 10, 14, 10)
        inner.setSpacing(4)

        # ── Row 1: name + right controls ────────────────────────────
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(8)

        # Truncate long filenames
        stem = Path(filename).stem
        ext  = Path(filename).suffix
        if len(stem) > 22:
            stem = stem[:14] + "…" + stem[-6:]

        self._name_lbl = QLabel(stem)
        self._name_lbl.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.85);"
        )

        self._ext_lbl = QLabel(ext)
        self._ext_lbl.setStyleSheet(
            "font-size: 10px; font-weight: 600; color: rgba(255,255,255,0.35);"
            " background: rgba(255,255,255,0.06); border-radius: 5px; padding: 1px 6px;"
        )

        self._status_lbl = QLabel("Queued")
        self._status_lbl.setStyleSheet(
            "font-size: 11px; color: rgba(255,255,255,0.30);"
        )
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Reveal button (shown after success)
        self._reveal_btn = QPushButton("Reveal")
        self._reveal_btn.setStyleSheet(self._BTN_STYLE)
        self._reveal_btn.setFixedHeight(22)
        self._reveal_btn.hide()
        self._reveal_btn.clicked.connect(self._reveal)

        # Dismiss button
        self._dismiss_btn = QPushButton("✕")
        self._dismiss_btn.setStyleSheet(self._BTN_STYLE)
        self._dismiss_btn.setFixedSize(22, 22)
        self._dismiss_btn.clicked.connect(lambda: self.dismiss_requested.emit(self.job_id))

        row1.addWidget(self._name_lbl)
        row1.addWidget(self._ext_lbl)
        row1.addStretch()
        row1.addWidget(self._status_lbl)
        row1.addWidget(self._reveal_btn)
        row1.addWidget(self._dismiss_btn)
        inner.addLayout(row1)

        # ── Row 2: progress bar ──────────────────────────────────────
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(3)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(self._BAR_STYLE)
        self._bar.hide()
        inner.addWidget(self._bar)

    # ── Public state setters ─────────────────────────────────────────────────

    def set_queued(self):
        self._name_lbl.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.35);"
        )
        self._status_lbl.setText("Queued")
        self._status_lbl.setStyleSheet("font-size: 11px; color: rgba(255,255,255,0.25);")
        self._bar.hide()
        self._reveal_btn.hide()

    def set_processing(self, pct: int = 0, detail: str = ""):
        self._name_lbl.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.85);"
        )
        self._bar.setValue(pct)
        self._bar.show()
        pct_text = f"{pct}%" if not detail else detail
        self._status_lbl.setText(pct_text)
        self._status_lbl.setStyleSheet("font-size: 11px; color: rgba(255,255,255,0.40);")
        self._reveal_btn.hide()

    def set_done(self, orig: int, final: int, out: Path):
        self.output_path = out
        self._bar.hide()

        if orig > 0 and orig != final:
            saved_pct = int((1 - final / orig) * 100)
            txt = (
                f"<span style='color:#FF5252;'>{_fmt(orig)}</span>"
                f"<span style='color:rgba(255,255,255,0.4);'>&nbsp;→&nbsp;</span>"
                f"<span style='color:#FFD54F;'>{_fmt(final)}</span>"
                f"<span style='color:rgba(255,255,255,0.3);font-size:10px;'>&nbsp;−{saved_pct}%</span>"
            )
        else:
            txt = f"<span style='color:#FFD54F;'>{_fmt(final)}</span>"

        self._status_lbl.setText(txt)
        self._status_lbl.setStyleSheet("font-size:11px;")
        self._reveal_btn.show()
        self._card.setStyleSheet("""
            QFrame#card {
                background: rgba(255,255,255,0.07);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 12px;
            }
        """)

    def set_failed(self, msg: str):
        self._bar.hide()
        self._status_lbl.setText(msg[:40])
        self._status_lbl.setStyleSheet("font-size: 11px; color: rgba(220,80,80,0.8);")
        self._reveal_btn.hide()

    # ── Actions ──────────────────────────────────────────────────────────────

    def _reveal(self):
        if self.output_path and self.output_path.exists():
            if sys.platform == "win32":
                subprocess.call(["explorer", "/select,", str(self.output_path)])
            elif sys.platform == "darwin":
                subprocess.call(["open", "-R", str(self.output_path)])

    # ── Mouse Interaction (Drag Out & Copy) ──────────────────────────────────
    
    def contextMenuEvent(self, event):
        if not self.output_path or not self.output_path.exists():
            return
            
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #2A2A2A; color: white; border: 1px solid #444; border-radius: 6px; }
            QMenu::item { padding: 6px 24px; font-size: 12px; }
            QMenu::item:selected { background: rgba(255,255,255,0.1); border-radius: 4px; }
        """)
        
        copy_action = menu.addAction("Copy")
        action = menu.exec(event.globalPos())
        
        if action == copy_action:
            self._do_copy()

    def _do_copy(self):
        # Copy file to clipboard (places it as a file payload for File Explorer)
        clipboard = QApplication.clipboard()
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.output_path))])
        clipboard.setMimeData(mime)
        
        # Flash status
        old_text = self._status_lbl.text()
        self._status_lbl.setText("Copied!")
        self._status_lbl.setStyleSheet("font-size: 11px; color: #4CAF50; font-weight: bold;")
        
        def _restore():
            self._status_lbl.setText(old_text)
            self._status_lbl.setStyleSheet("font-size:11px;")
        QTimer.singleShot(1500, _restore)

    def mousePressEvent(self, event: QMouseEvent):
        if not self.output_path or not self.output_path.exists():
            super().mousePressEvent(event)
            return
            
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
            
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.output_path or not self.output_path.exists():
            super().mouseMoveEvent(event)
            return
            
        if not (event.buttons() & Qt.MouseButton.LeftButton) or not self._drag_start_pos:
            super().mouseMoveEvent(event)
            return
            
        # Ensure minimum drag distance to trigger
        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
            
        drag = QDrag(self)
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.output_path))])
        drag.setMimeData(mime)
        
        # Initiate the drag operation outside the application
        drag.exec(Qt.DropAction.CopyAction)
        self._drag_start_pos = None
