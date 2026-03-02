import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QPushButton, QProgressBar, QGraphicsDropShadowEffect,
    QStackedWidget, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QIcon, QColor, QCursor

from clyro.core.types import DropIntent, OptimiseCommand, ConvertCommand, MediaType
from clyro.core.classify import classify, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, DOCUMENT_EXTENSIONS
from clyro.ui.result_card import ResultCard

logger = logging.getLogger(__name__)

_ALL_SUPPORTED = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | DOCUMENT_EXTENSIONS

# ── Layout constants ─────────────────────────────────────────────────────────
SHELL_W    = 240   # shell/card body width
PAD_L      = 20    # root left margin
PAD_R      = 0     # no right margin so buttons bleed out right
PAD_TOP    = 50
PAD_BOT    = 110   # Increased from 70 to give breathing room for tall dropdown pills
IDLE_H     = 160
CARD_ITEM_H = 80   # each BatchItem height (pill 30 + card 48 + gap 2)
CARD_GAP   = 6
MAX_SHOW   = 5

def _icon(name: str) -> QIcon:
    from clyro.utils.paths import resource_path
    return QIcon(str(resource_path(f"clyro/assets/icons/phosphor/{name}")))

def _fmt(b: int) -> str:
    if b < 1024:        return f"{b} B"
    if b < 1024 ** 2:   return f"{b/1024:.0f} KB"
    return f"{b/(1024**2):.1f} MB"

# ─────────────────────────────────────────────────────────────────────────────
class DropzoneWindow(QWidget):

    def __init__(self, queue_service, settings):
        super().__init__()
        self.queue    = queue_service
        self.settings = settings

        self.setWindowTitle("Drop Zone")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAcceptDrops(True)

        self._drag_over = False
        self._window_dragging = False
        self._window_drag_start_global = None
        self._window_drag_start_pos    = None
        self._file_drag_start_pos      = None   # must be initialized to avoid AttributeError
        self._single_job_id  = None
        self._single_result  = None
        self._batch_items: dict[str, "BatchItem"] = {}   # job_id → BatchItem
        self._download_workers = {}
        self._auto_dismiss_timer: QTimer | None = None  # auto-dismiss completed single results
        self._cached_timer: QTimer | None = None  # auto-dismiss cached single results
        self._hovering_result = False

        # ── Root: outer margins then a horizontal content row ─────────
        root = QVBoxLayout(self)
        root.setContentsMargins(PAD_L, PAD_TOP, PAD_R, PAD_BOT)
        root.setSpacing(0)

        self._content_row = QHBoxLayout()
        self._content_row.setContentsMargins(0, 0, 0, 0)
        self._content_row.setSpacing(8)
        root.addLayout(self._content_row)

        # ── Shell ─────────────────────────────────────────────────────
        self._shell = QFrame()
        self._shell.setObjectName("shell")
        self._shell.setFixedWidth(SHELL_W)
        self._shell.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        sh = QGraphicsDropShadowEffect(self._shell)
        sh.setBlurRadius(18); sh.setOffset(0, 7)
        sh.setColor(QColor(0, 0, 0, 120))
        self._shell.setGraphicsEffect(sh)

        sl = QVBoxLayout(self._shell)
        sl.setContentsMargins(0, 0, 0, 0); sl.setSpacing(0)

        self._shell_stack = QStackedWidget()
        sl.addWidget(self._shell_stack)

        # ── Pages inside shell ────────────────────────────────────────
        self._page_idle   = self._build_idle_page()
        self._page_single = self._build_single_content()  # content only, no side buttons
        self._page_batch  = self._build_batch_page()

        self._shell_stack.addWidget(self._page_idle)    # 0
        self._shell_stack.addWidget(self._page_single)  # 1
        self._shell_stack.addWidget(self._page_batch)   # 2

        self._content_row.addWidget(self._shell)

        # ── Action buttons — OUTSIDE the shell ───────────────────────
        self._s_actions = self._build_actions_panel()
        self._content_row.addWidget(
            self._s_actions,
            alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self._content_row.addStretch()

        # ── Floating name pill (above shell, for single mode) ─────────
        self._name_pill = QFrame(self)
        self._name_pill.setStyleSheet(
            "QFrame{background:rgba(40,35,30,240);border-radius:12px;}"
        )
        pr = QHBoxLayout(self._name_pill)
        # Add slight extra bottom margin to optically center fonts
        pr.setContentsMargins(12, 4, 8, 6)
        pr.setSpacing(8)
        self._pill_stem = QLabel()
        self._pill_stem.setStyleSheet(
            "font-size:11px;font-weight:700;color:rgba(255,255,255,0.9);background:transparent;"
        )
        self._pill_ext = QLabel()
        self._pill_ext.setStyleSheet(
            "font-size:10px;font-weight:700;color:rgba(255,255,255,0.75);"
            "background:rgba(255,255,255,0.14);border-radius:8px;padding:3px 8px;"
        )
        pr.addWidget(self._pill_stem, alignment=Qt.AlignmentFlag.AlignVCenter)
        pr.addStretch()
        pr.addWidget(self._pill_ext, alignment=Qt.AlignmentFlag.AlignVCenter)
        self._name_pill.hide()

        # ── Convert pill (below shell) ────────────────────────────────
        self._conv_pill = QFrame(self)
        self._conv_pill.setObjectName("convert_pill")
        self._conv_pill.setFixedWidth(SHELL_W)
        self._conv_pill.setStyleSheet(
            "QFrame#convert_pill{background:rgba(35,30,30,245);border-radius:16px;border:1px solid rgba(255,255,255,10);}"
        )
        self._conv_row = QHBoxLayout(self._conv_pill)
        self._conv_row.setContentsMargins(8, 6, 8, 6)
        self._conv_row.setSpacing(6)
        self._conv_pill.hide()

        # ── Merge pill (below shell) ──────────────────────────────────
        self._merge_pill = QFrame(self)
        self._merge_pill.setFixedWidth(SHELL_W)
        self._merge_pill.setStyleSheet(
            "QFrame{background:rgba(40,35,30,240);border-radius:16px;}"
        )
        self._merge_row = QHBoxLayout(self._merge_pill)
        self._merge_row.setContentsMargins(8, 6, 8, 6)
        self._merge_row.setSpacing(6)
        self._merge_pill.hide()

        # ── Stylesheet ────────────────────────────────────────────────
        self.setStyleSheet("""
            QWidget{
                background:transparent;
                color:rgba(255,255,255,0.85);
                font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
            }
            QFrame#shell{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(60,60,60,180), stop:1 rgba(40,40,40,200));
                border-radius:20px;
                border:1px solid rgba(255,255,255,30);
            }
            QFrame#shell[drag=true]{
                border:1.5px dashed rgba(255,255,255,80);
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(80,80,80,200), stop:1 rgba(60,60,60,220));
            }
            QFrame#shell[mode=err]{
                border:1.5px solid rgba(220,80,80,110);
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(220,80,80,150), stop:1 rgba(220,80,80,180));
            }
            QScrollArea,QScrollArea>QWidget>QWidget{background:transparent;}
            QScrollArea{border:none;}
            QScrollBar:vertical{width:3px;background:transparent;}
            QScrollBar::handle:vertical{background:rgba(255,255,255,0.15);border-radius:1px;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
        """)

        self._apply_size(mode="idle")
        self.queue.job_added.connect(self._on_job_added)
        self.queue.job_updated.connect(self._on_job_updated)

    # ─── Page builders ───────────────────────────────────────────────────────

    def _build_idle_page(self) -> QWidget:
        p = QWidget(); p.setFixedWidth(SHELL_W)
        lay = QVBoxLayout(p)
        lay.setContentsMargins(16, 28, 16, 28)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._idle_title = QLabel("Drop files")
        self._idle_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._idle_title.setWordWrap(True)
        self._idle_title.setStyleSheet(
            "font-size:16px;font-weight:700;color:rgba(255,255,255,0.9);"
        )
        self._idle_hint = QLabel("⌥ Convert  ·  ⇧ Max")
        self._idle_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._idle_hint.setStyleSheet("font-family: 'Segoe UI Symbol', sans-serif; font-size:12px; color:rgba(255,255,255,0.45);")
        lay.addWidget(self._idle_title); lay.addSpacing(6); lay.addWidget(self._idle_hint)
        return p

    def _build_single_content(self) -> QWidget:
        """Content area ONLY — action buttons live outside the shell."""
        p = QWidget(); p.setFixedWidth(SHELL_W)
        lay = QVBoxLayout(p)
        lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(0)

        # Header: close / type icon match exactly like top-left / top-right
        hdr = QHBoxLayout(); hdr.setContentsMargins(0,0,0,0)
        self._s_close = QPushButton()
        self._s_close.setIcon(_icon("x-bold.svg"))
        self._s_close.setFixedSize(24, 24)
        self._s_close.setStyleSheet("""
            QPushButton{background:rgba(255,255,255,120);border-radius:6px;border:none;}
            QPushButton:hover{background:rgba(255,255,255,160);}
        """)
        self._s_close.clicked.connect(self._reset_to_idle)
        self._s_type_icon = QLabel()
        self._s_type_icon.setPixmap(_icon("image-bold.svg").pixmap(16,16))
        self._s_type_icon.setStyleSheet(
            "background:rgba(255,255,255,120);border-radius:6px;padding:4px;"
        )
        hdr.addWidget(self._s_close); hdr.addStretch(); hdr.addWidget(self._s_type_icon)
        lay.addLayout(hdr)

        self._s_center = QStackedWidget()

        # ── Processing Page (Bottom-left aligned) ──
        proc = QWidget(); pl = QVBoxLayout(proc)
        pl.setContentsMargins(0,0,0,0); pl.setSpacing(0)
        pl.addStretch() # Push everything to the bottom

        self._s_proc_label = QLabel("Optimizing")
        self._s_proc_label.setStyleSheet(
            "font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;"
            "font-size:16px;font-weight:600;color:rgba(255,255,255,0.95);"
        )
        
        self._s_bar = QProgressBar()
        self._s_bar.setRange(0,100); self._s_bar.setValue(0)
        self._s_bar.setFixedHeight(3); self._s_bar.setTextVisible(False)
        self._s_bar.setStyleSheet("""
            QProgressBar{border:none;background:rgba(255,255,255,30);border-radius:2px;}
            QProgressBar::chunk{background:#FFFFFF;border-radius:2px;}
        """)
        
        self._s_detail = QLabel("")
        self._s_detail.setStyleSheet(
            "font-family: 'Space Mono', Consolas, monospace;"
            "font-size:13px;font-weight:600;color:rgba(255,255,255,0.85);"
        )
        self._s_detail.setWordWrap(False)
        
        pl.addWidget(self._s_proc_label); pl.addSpacing(6)
        pl.addWidget(self._s_bar); pl.addSpacing(4); pl.addWidget(self._s_detail)

        # ── Result Page (Bottom-center aligned) ──
        res = QWidget(); rl = QVBoxLayout(res)
        rl.setContentsMargins(0,0,0,0); rl.setSpacing(0)
        rl.addStretch() # Push everything to the bottom
        
        self._s_diff = QLabel("…")
        self._s_diff.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._s_diff.setStyleSheet(
            "font-family: 'Space Mono', Consolas, monospace;"
            "font-size:17px;font-weight:700;"
        )
        self._s_res_lbl = QLabel("")
        self._s_res_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._s_res_lbl.setStyleSheet(
            "font-family: 'Space Mono', Consolas, monospace;"
            "font-size:12px;font-weight:600;color:rgba(255,255,255,0.85);"
        )
        rl.addWidget(self._s_diff)
        rl.addSpacing(4); rl.addWidget(self._s_res_lbl)

        self._s_center.addWidget(proc); self._s_center.addWidget(res)
        lay.addWidget(self._s_center)
        return p

    def _build_actions_panel(self) -> QWidget:
        """4 circle buttons that sit to the RIGHT of the shell."""
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(10)

        def _cb(svg: str) -> QPushButton:
            btn = QPushButton()
            btn.setIcon(_icon(svg)); btn.setIconSize(QSize(16,16))
            btn.setFixedSize(32,32)
            btn.setStyleSheet("""
                QPushButton{background:#F8F8F8;border-radius:16px;border:none;}
                QPushButton:hover{background:#FFFFFF;}
            """)
            return btn

        self._btn_minus = _cb("minus-bold.svg")
        self._btn_eye   = _cb("eye-bold.svg")
        self._btn_undo  = _cb("arrow-u-up-left-bold.svg")
        self._btn_zap   = _cb("lightning-bold.svg")
        self._btn_play  = _cb("play-bold.svg")
        self._btn_minus.setToolTip("Downscale")
        self._btn_eye.setToolTip("Show in folder")
        self._btn_undo.setToolTip("Undo optimization")
        self._btn_zap.setToolTip("Aggressive optimization")
        self._btn_play.setToolTip("Force re-optimize")
        self._btn_minus.clicked.connect(self._downscale_single)
        self._btn_eye.clicked.connect(self._reveal_single)
        self._btn_undo.clicked.connect(self._undo_single)
        self._btn_zap.clicked.connect(self._aggressive_single)
        self._btn_play.clicked.connect(self._force_reoptimize_single)

        for b in [self._btn_minus, self._btn_eye, self._btn_undo, self._btn_zap, self._btn_play]:
            lay.addWidget(b)
        panel.hide()
        return panel

    def _build_batch_page(self) -> QWidget:
        p = QWidget(); p.setFixedWidth(SHELL_W)
        lay = QVBoxLayout(p)
        lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget(); container.setStyleSheet("background:transparent;")
        self._items_lay = QVBoxLayout(container)
        self._items_lay.setContentsMargins(8, 8, 8, 4)
        self._items_lay.setSpacing(CARD_GAP)
        self._items_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(container)
        lay.addWidget(self._scroll, 1)

        _FOOT_BTN = """
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                font-size: 11px;
                font-weight: 500;
                color: rgba(255, 255, 255, 0.6);
                padding: 6px 12px;
                margin: 2px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                color: rgba(255, 255, 255, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.03);
            }
        """
        _FOOT_BTN_DANGER = """
            QPushButton {
                background: rgba(255, 80, 80, 0.05);
                border: 1px solid rgba(255, 80, 80, 0.15);
                border-radius: 6px;
                font-size: 11px;
                font-weight: 500;
                color: rgba(255, 100, 100, 0.7);
                padding: 6px 12px;
                margin: 2px;
            }
            QPushButton:hover {
                background: rgba(255, 80, 80, 0.15);
                color: rgba(255, 120, 120, 0.9);
                border: 1px solid rgba(255, 80, 80, 0.3);
            }
            QPushButton:pressed {
                background: rgba(255, 80, 80, 0.03);
            }
        """

        foot = QWidget()
        foot.setStyleSheet("background: transparent;")
        
        # Main layout for footer
        fl = QVBoxLayout(foot)
        fl.setContentsMargins(12, 8, 12, 12)
        fl.setSpacing(6)

        # Row 1: Actions
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        
        self._copy_all_btn = QPushButton("Copy all")
        self._copy_all_btn.setStyleSheet(_FOOT_BTN)
        self._copy_all_btn.clicked.connect(self._copy_all_results)

        self._save_to_folder_btn = QPushButton("Save to folder")
        self._save_to_folder_btn.setStyleSheet(_FOOT_BTN)
        self._save_to_folder_btn.clicked.connect(self._save_to_folder)

        row1.addWidget(self._copy_all_btn)
        row1.addWidget(self._save_to_folder_btn)

        # Row 2: Management
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        
        self._clear_btn = QPushButton("Clear all")
        self._clear_btn.setStyleSheet(_FOOT_BTN)
        self._clear_btn.clicked.connect(self._clear_all)

        self._cancel_all_btn = QPushButton("Cancel all")
        self._cancel_all_btn.setStyleSheet(_FOOT_BTN_DANGER)
        self._cancel_all_btn.clicked.connect(self._cancel_all)

        row2.addWidget(self._clear_btn)
        row2.addWidget(self._cancel_all_btn)

        fl.addLayout(row1)
        fl.addLayout(row2)
        lay.addWidget(foot)
        
        # Store base styles for later state resets (Copied/Saved)
        self._base_foot_btn_style = _FOOT_BTN
        
        return p

    # ─── Sizing ──────────────────────────────────────────────────────────────

    def _apply_size(self, mode: str = "idle", card_count: int = 0):
        if mode in ("idle", "single"):
            shell_h = IDLE_H
            total_w = PAD_L + SHELL_W + (50 if mode == "single" else 20)
        else:  # batch
            visible = min(card_count, MAX_SHOW)
            # scroll_h calculates the height for the cards area
            scroll_h = visible * CARD_ITEM_H + max(0, visible-1) * CARD_GAP + 8
            # The 2x2 footer is ~80px tall. We add that to the scroll area height.
            shell_h  = scroll_h + 84
            self._scroll.setFixedHeight(scroll_h)
            total_w = PAD_L + SHELL_W + 20

        self._shell.setFixedHeight(shell_h)
        self.setFixedSize(total_w, shell_h + PAD_TOP + PAD_BOT + 20)

    # ─── Pill helpers ─────────────────────────────────────────────────────────

    def _show_name_pill(self, filename: str):
        stem = Path(filename).stem; ext = Path(filename).suffix
        self._pill_stem.setText(stem[:20] + "…" if len(stem) > 20 else stem)
        self._pill_ext.setText(ext)
        self._name_pill.setFixedWidth(SHELL_W)
        self._name_pill.setFixedHeight(28)
        
        # Shell is always physically located at PAD_L, PAD_TOP 
        # relative to the widget because of the root margins.
        # Moving this back up slightly to add a small gap
        self._name_pill.move(PAD_L, PAD_TOP - 28 + 4)
        self._name_pill.show(); self._name_pill.raise_()

    def _position_pill(self, pill: QFrame):
        pill.adjustSize()
        px = PAD_L + (SHELL_W - pill.width()) // 2
        py = PAD_TOP + self._shell.height() + 16
        
        # Ensure it doesn't clip on the left
        if px < 10:
            px = 10
            
        required_w = px + pill.width() + 20
        if required_w > self.width():
            self.setFixedWidth(required_w)
            
        pill.move(px, py)
        pill.show(); pill.raise_()

    def _position_conv_pill(self):
        self._position_pill(self._conv_pill)

    # ─── Drag / Drop ─────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        # Ignore our own drag events (e.g. dragging a file OUT of the app)
        if event.source() == self:
            return

        if not event.mimeData().hasUrls(): return

        # Drop validation: reject unsupported-only drops
        urls = event.mimeData().urls()
        has_supported = any(
            u.scheme() in ('http', 'https')
            or (u.isLocalFile() and (
                Path(u.toLocalFile()).is_dir()
                or Path(u.toLocalFile()).suffix.lower() in _ALL_SUPPORTED
            ))
            for u in urls
        )
        if not has_supported:
            self._idle_title.setText("Unsupported"); self._idle_hint.setText("Not a supported file type")
            self._shell.setProperty("drag", "true")
            self._shell.style().unpolish(self._shell); self._shell.style().polish(self._shell)
            event.ignore()
            QTimer.singleShot(1500, lambda: (
                self._idle_title.setText("Drop files"),
                self._idle_hint.setText("⌥ Convert  ·  ⇧ Max"),
                self._clear_drag_style(),
            ))
            return

        self._drag_over = True
        self._shell.setProperty("drag","true")
        self._shell.style().unpolish(self._shell); self._shell.style().polish(self._shell)
        self._update_drag_hints(event.modifiers())
        event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent):
        """Live modifier key feedback — updates hint in real-time."""
        self._update_drag_hints(event.modifiers())
        event.acceptProposedAction()

    def _update_drag_hints(self, mods):
        if mods & Qt.KeyboardModifier.AltModifier:
            self._idle_title.setText("Convert"); self._idle_hint.setText("Same type only")
        elif mods & Qt.KeyboardModifier.ShiftModifier:
            self._idle_title.setText("Max compression"); self._idle_hint.setText("Aggressive")
        else:
            self._idle_title.setText("Optimise"); self._idle_hint.setText("Drop to process")

    def dragLeaveEvent(self, event):
        self._drag_over = False; self._clear_drag_style()
        self._idle_title.setText("Drop files"); self._idle_hint.setText("⌥ Convert  ·  ⇧ Max")

    def _clear_drag_style(self):
        self._shell.setProperty("drag","false"); self._shell.setProperty("mode","")
        self._shell.style().unpolish(self._shell); self._shell.style().polish(self._shell)

    def dropEvent(self, event: QDropEvent):
        self._drag_over = False; self._clear_drag_style()

        local_paths = []
        web_urls = []
        for u in event.mimeData().urls():
            if u.isLocalFile():
                p = Path(u.toLocalFile())
                # Recursive directory drop
                if p.is_dir():
                    for child in p.rglob('*'):
                        if child.is_file() and child.suffix.lower() in _ALL_SUPPORTED:
                            local_paths.append(child)
                else:
                    local_paths.append(p)
            elif u.scheme() in ('http', 'https'):
                web_urls.append(u.url())

        if not local_paths and not web_urls: return

        mods = event.modifiers()
        intent_mode = "optimize"
        if mods & Qt.KeyboardModifier.AltModifier:
            intent_mode = "convert"
        elif mods & Qt.KeyboardModifier.ShiftModifier:
            intent_mode = "aggressive"

        if web_urls:
            if intent_mode == "convert" and len(web_urls) > 1:
                self._flash_error("Convert only 1 link at a time")
                return
            for url in web_urls:
                self._start_download(url, intent_mode)

        if local_paths:
            if intent_mode == "convert":
                types = {classify(p) for p in local_paths}
                if len(types) > 1 or MediaType.UNSUPPORTED in types:
                    self._flash_error("Same type required for batch convert"); return
                self._show_convert_pill(DropIntent(mode="convert", files=local_paths))
            elif intent_mode == "aggressive":
                self._submit(DropIntent(mode="aggressive", files=local_paths))
            else:
                self._submit(DropIntent(mode="optimize", files=local_paths))

    def _start_download(self, url: str, intent_mode: str):
        import uuid
        job_id = f"dl_{uuid.uuid4().hex[:8]}"
        
        already_has_single = self._single_job_id is not None
        already_has_batch  = bool(self._batch_items)
        
        if not already_has_single and not already_has_batch:
            self._single_job_id = job_id
            self._shell_stack.setCurrentIndex(1)
            self._apply_size(mode="single")
            
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            filename = Path(parsed.path).name or "download"
            self._show_name_pill(filename)
            self._s_actions.show()
            self._s_type_icon.setPixmap(_icon("image-bold.svg").pixmap(16,16))
            self._s_close.setIcon(_icon("stop-bold.svg"))
            self._s_center.setCurrentIndex(0)
            self._s_proc_label.setText("Downloading...")
            self._s_detail.setText("Downloading..."); self._s_bar.setValue(0)
            self._btn_undo.hide()
        else:
            if already_has_single and self._single_job_id not in self._batch_items:
                stem_text = self._pill_stem.text()
                ext_text  = self._pill_ext.text()
                self._make_batch_item(self._single_job_id, stem_text + ext_text)
                self._single_job_id = None
                self._s_actions.hide()

            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            filename = Path(parsed.path).name or "download"
            item = self._make_batch_item(job_id, filename)
            item.set_queued()
            item.set_processing(0, "Downloading...")
            self._enter_batch_mode()

        from clyro.utils.download import DownloadWorker
        from clyro.utils.paths import get_app_data_dir
        
        temp_dir = get_app_data_dir() / "downloads"
        worker = DownloadWorker(url, temp_dir)
        self._download_workers[job_id] = worker
        
        def _on_progress(pct, detail):
            # QThread signals are delivered to the main thread via slots, so it is safe to touch UI
            if self._single_job_id == job_id:
                safe_detail = detail[:25]
                text = f"{pct}% - {safe_detail}" if pct > 0 else f"{safe_detail}"
                self._s_bar.setValue(pct); self._s_detail.setText(text)
            elif job_id in self._batch_items:
                self._batch_items[job_id].set_processing(pct, detail)
                
        def _on_completed(temp_path: Path, orig_url: str):
            worker.wait()  # ensure the thread has fully exited before we clean up
            self._download_workers.pop(job_id, None)
            from clyro.core.types import OptimiseCommand, ConvertCommand
            import shutil
            
            output_folder = self.settings.web_download_folder
            if not output_folder:
                output_folder = str(Path.home() / "Downloads")
                
            out_dir_path = Path(output_folder)
            out_dir_path.mkdir(parents=True, exist_ok=True)
            
            # 1. ALWAYS move the web download from Temp -> Output Folder permanently first
            #    This solves "not saving them on the destination folder" natively
            from clyro.core.output import _handle_collision
            final_src_path = _handle_collision(out_dir_path / temp_path.name)
            shutil.move(str(temp_path), str(final_src_path))
            
            was_single = (self._single_job_id == job_id)
            if was_single:
                self._single_job_id = None
            else:
                self._remove_item(job_id)

            # 2. Dispatch command based on user intent (Optimization vs Conversion)
            if intent_mode == "convert" or intent_mode == "aggressive":
                is_convert = (intent_mode == "convert")
                if is_convert:
                    if was_single:
                        self._reset_to_idle()
                    # Let the convert UI pill handle it, just pretend we dropped a local file
                    self._show_convert_pill(DropIntent(mode="convert", files=[final_src_path]))
                else:
                    cmd = OptimiseCommand(
                        path=final_src_path, 
                        aggressive=True, 
                        output_mode="in_place" if not self.settings.keep_web_originals else "specific_folder",
                        output_dir=out_dir_path if self.settings.keep_web_originals else None
                    )
                    self.queue.submit(cmd)
            else:
                cmd = OptimiseCommand(
                    path=final_src_path, 
                    aggressive=False, 
                    output_mode="in_place" if not self.settings.keep_web_originals else "specific_folder", 
                    output_dir=out_dir_path if self.settings.keep_web_originals else None
                )
                self.queue.submit(cmd)
            
        def _on_failed(msg: str, orig_url: str):
            worker.wait()  # ensure thread fully stopped before cleanup
            self._download_workers.pop(job_id, None)
            if self._single_job_id == job_id:
                self._s_close.setIcon(_icon("x-bold.svg"))
                self._s_center.setCurrentIndex(1)
                self._s_diff.setText("Failed")
                self._s_res_lbl.setText(f"<span style='color:rgba(220,80,80,0.85);'>Download Failed</span>")
                self._btn_undo.show()
            elif job_id in self._batch_items:
                self._batch_items[job_id].set_failed("Download failed")
            
        worker.progress_updated.connect(_on_progress)
        worker.download_completed.connect(_on_completed)
        worker.download_failed.connect(_on_failed)
        worker.start()

    def _flash_error(self, msg: str):
        self._shell_stack.setCurrentIndex(0)
        self._idle_title.setText(msg)
        self._idle_title.setStyleSheet("font-size:12px;font-weight:600;color:rgba(220,80,80,0.85);")
        self._shell.setProperty("mode","err")
        self._shell.style().unpolish(self._shell); self._shell.style().polish(self._shell)
        def _r():
            self._idle_title.setStyleSheet("font-size:16px;font-weight:700;color:rgba(255,255,255,0.9);")
            self._idle_title.setText("Drop files"); self._idle_hint.setText("⌥ Convert  ·  ↑ Max")
            self._clear_drag_style()
        QTimer.singleShot(2000, _r)

    # ─── Convert pill ─────────────────────────────────────────────────────────

    def _show_convert_pill(self, intent: DropIntent):
        while self._conv_row.count():
            item = self._conv_row.takeAt(0)
            if w := item.widget():
                w.setParent(None)
                w.deleteLater()
            elif lay := item.layout():
                while lay.count():
                    sub = lay.takeAt(0)
                    if sub_w := sub.widget():
                        sub_w.setParent(None)
                        sub_w.deleteLater()
                lay.setParent(None)
                lay.deleteLater()
                
        options = {
            MediaType.IMAGE:    ["JPG","PNG","WEBP","PDF"],
            MediaType.VIDEO:    ["MP4","WEBM","GIF"],
            MediaType.DOCUMENT: ["Word"],
        }.get(classify(intent.files[0]), [])
        _B = ("QPushButton{background:rgba(255,255,255,0.12);color:rgba(255,255,255,0.85);"
              "border-radius:8px;padding:4px 10px;font-size:11px;font-weight:600;border:none;}"
              "QPushButton:hover{background:rgba(255,255,255,0.22);}")
        _C = ("QPushButton{background:rgba(255,255,255,0.06);color:rgba(255,255,255,0.35);"
              "border-radius:8px;padding:4px 8px;font-size:11px;border:none;}"
              "QPushButton:hover{background:rgba(255,255,255,0.12);}")
        def _h(fmt):
            def _do(): 
                # If we have multiple images and the target is PDF, we ask for merge/separate instead of submitting right away.
                if fmt == "PDF" and len(intent.files) > 1 and classify(intent.files[0]) == MediaType.IMAGE:
                    intent.target_format = "pdf"
                    self._show_pdf_merge_pill(intent)
                    return
                # Otherwise, proceed as usual (single file or non-merge format)
                if fmt == "Word":
                    intent.target_format = "docx"
                else:
                    intent.target_format = fmt.lower()
                self._conv_pill.hide()
                self._submit(intent)
            return _do
            
        self._conv_row.addStretch()
        for fmt in options:
            b = QPushButton(fmt); b.setStyleSheet(_B); b.clicked.connect(_h(fmt))
            self._conv_row.addWidget(b)
        cx = QPushButton("✕"); cx.setStyleSheet(_C); cx.setFixedWidth(28)
        cx.clicked.connect(self._conv_pill.hide); self._conv_row.addWidget(cx)
        self._conv_row.addStretch()
        self._position_conv_pill()

    def _show_pdf_merge_pill(self, intent: DropIntent):
        """Show second pill options when merging multiple images to PDF."""
        while self._merge_row.count():
            item = self._merge_row.takeAt(0)
            if w := item.widget():
                w.setParent(None)
                w.deleteLater()

        _B = ("QPushButton{background:rgba(255,255,255,0.12);color:rgba(255,255,255,0.85);"
              "border-radius:8px;padding:4px 10px;font-size:11px;font-weight:600;border:none;}"
              "QPushButton:hover{background:rgba(255,255,255,0.22);}")
        _C = ("QPushButton{background:rgba(255,255,255,0.06);color:rgba(255,255,255,0.35);"
              "border-radius:8px;padding:4px 8px;font-size:11px;border:none;}"
              "QPushButton:hover{background:rgba(255,255,255,0.12);}")
              
        def _do_merge():
            intent.mode = "merge"
            self._merge_pill.hide()
            self._submit(intent)
            
        def _do_separate():
            intent.mode = "convert"
            self._merge_pill.hide()
            self._submit(intent)

        b_merge = QPushButton("Merge to PDF"); b_merge.setStyleSheet(_B); b_merge.clicked.connect(_do_merge)
        b_sep = QPushButton("Separate PDFs"); b_sep.setStyleSheet(_B); b_sep.clicked.connect(_do_separate)
        self._merge_row.addStretch()
        self._merge_row.addWidget(b_merge)
        self._merge_row.addWidget(b_sep)

        cx = QPushButton("✕"); cx.setStyleSheet(_C); cx.setFixedWidth(28)
        cx.clicked.connect(self._merge_pill.hide); self._merge_row.addWidget(cx)
        self._merge_row.addStretch()
        
        # Hide convert pill and show merge pill
        self._conv_pill.hide()
        self._position_pill(self._merge_pill)

    # ─── Submit ───────────────────────────────────────────────────────────────

    def _submit(self, intent: DropIntent):
        from clyro.core.types import MergeCommand
        if intent.mode == "merge":
            # For merge, we only submit ONE command that contains all files
            cmd = MergeCommand(
                path=intent.files[0],  # Primary path is used for UI tracking and base name
                files_to_merge=intent.files,
                target_format=intent.target_format,
                sort_order=getattr(self.settings, 'pdf_merge_sort_order', 'none'),
                output_mode=self.settings.output_mode
            )
            self.queue.submit(cmd)
            return

        for path in intent.files:
            if intent.mode == "aggressive":
                cmd = OptimiseCommand(path, aggressive=True, output_mode=self.settings.output_mode)
            elif intent.mode == "convert":
                # Web Download Conversion: Respect "keep originals" if the file is already in the download destination
                if str(path.parent) == self.settings.web_download_folder:
                    cmd_mode = "specific_folder" if self.settings.keep_web_originals else "in_place"
                    cmd_dir  = Path(self.settings.web_download_folder) if self.settings.keep_web_originals else None
                    cmd = ConvertCommand(path, target_format=intent.target_format, output_mode=cmd_mode, output_dir=cmd_dir)
                else:
                    cmd = ConvertCommand(path, target_format=intent.target_format, output_mode=self.settings.output_mode)
            else:
                # ── Auto-convert check ────────────────────────────────
                ac = self.settings
                ac_ext = path.suffix.lower().lstrip(".")
                if (getattr(ac, 'auto_convert_enabled', False)
                        and ac_ext == getattr(ac, 'auto_convert_from', '')):
                    out_mode = "in_place" if getattr(ac, 'auto_convert_replace', False) else self.settings.output_mode
                    cmd = ConvertCommand(
                        path, target_format=getattr(ac, 'auto_convert_to', 'webp'),
                        output_mode=out_mode
                    )
                else:
                    cmd = OptimiseCommand(path, aggressive=False, output_mode=self.settings.output_mode)
            self.queue.submit(cmd)

    # ─── Queue callbacks ──────────────────────────────────────────────────────

    def _on_job_added(self, job):
        # Cancel auto-dismiss timer when new work arrives
        if self._auto_dismiss_timer:
            self._auto_dismiss_timer.stop(); self._auto_dismiss_timer = None

        already_has_single = self._single_job_id is not None
        already_has_batch  = bool(self._batch_items)

        # ── Auto-clear stale completed single result ──────────────────
        # If the single result page is showing (index 1 = result), the old
        # job is finished.  Clear it so new files get a fresh slot instead
        # of a broken upgrade to batch where the old item stays "Queued".
        if already_has_single and not already_has_batch:
            if self._s_center.currentIndex() == 1:          # result / failed page
                self._single_job_id = None
                self._single_result = None
                self._name_pill.hide()
                self._s_actions.hide()
                already_has_single = False

        # ── Batch resume: auto-clear stale completed items ─
        if already_has_batch and all(
            (bi.card._bar.isHidden() if hasattr(bi.card, '_bar') else True)
            for bi in self._batch_items.values()
        ):
            for item in list(self._batch_items.values()):
                self._items_lay.removeWidget(item); item.deleteLater()
            self._batch_items.clear()
            already_has_batch = False
            already_has_single = False
            self._single_job_id = None
            self._single_result = None
            self._name_pill.hide()
            self._s_actions.hide()

        if not already_has_single and not already_has_batch:
            # First and (so far) only file → single mode
            self._single_job_id = job.id
            self._enter_single_mode(job)
        else:
            # Second+ file: upgrade to / stay in batch mode
            if already_has_single and self._single_job_id not in self._batch_items:
                stem_text = self._pill_stem.text()
                ext_text  = self._pill_ext.text()
                self._make_batch_item(self._single_job_id, stem_text + ext_text)
                self._single_job_id = None
                self._s_actions.hide()

            self._make_batch_item(job.id, job.command.path.name)
            self._enter_batch_mode()

    def _enter_single_mode(self, job):
        self._shell_stack.setCurrentIndex(1)
        self._apply_size(mode="single")
        self._show_name_pill(job.command.path.name)
        self._s_actions.show()
        self._single_aggressive = getattr(job.command, 'aggressive', False)

        ext = job.command.path.suffix.lower()
        svg = ("video-camera-bold.svg" if ext in ('.mp4','.mov','.mkv','.avi','.webm')
               else "file-text-bold.svg" if ext in ('.pdf','.doc','.docx','.txt')
               else "image-bold.svg")
        self._s_type_icon.setPixmap(_icon(svg).pixmap(16,16))
        self._s_close.setIcon(_icon("stop-bold.svg"))
        self._s_center.setCurrentIndex(0)
        self._s_proc_label.setText("Optimising...")
        self._s_detail.setText(""); self._s_bar.setValue(0)
        self._btn_undo.hide()
        self._btn_minus.hide()
        self._btn_play.hide()
        # Hide aggressive button if already optimizing aggressively
        if self._single_aggressive:
            self._btn_zap.hide()
        else:
            self._btn_zap.show()

    def _enter_batch_mode(self):
        self._name_pill.hide()
        self._s_actions.hide()
        self._shell_stack.setCurrentIndex(2)
        self._apply_size(mode="batch", card_count=len(self._batch_items))

    def _make_batch_item(self, job_id: str, filename: str) -> "BatchItem":
        if job_id in self._batch_items:
            return self._batch_items[job_id]
        item = BatchItem(job_id, filename)
        item.dismiss_requested.connect(self._remove_item)
        self._items_lay.addWidget(item)
        self._batch_items[job_id] = item
        return item

    # ─── Job status ───────────────────────────────────────────────────────────

    def _on_job_updated(self, job):
        if job.id == self._single_job_id:
            self._update_single(job); return
        item = self._batch_items.get(job.id)
        if item: self._update_batch_item(item, job)

    def _update_single(self, job):
        if job.status == "processing":
            self._s_center.setCurrentIndex(0)
            pct, detail = 0, ""
            if isinstance(job.progress, tuple) and len(job.progress) == 2:
                pct, detail = int(job.progress[0]), job.progress[1]
            elif isinstance(job.progress, (int, float)):
                pct = int(job.progress * 100)
            self._s_bar.setValue(pct); self._s_detail.setText(detail)
            self._btn_undo.hide()
        elif job.status == "completed" and job.result:
            self._s_close.setIcon(_icon("x-bold.svg"))
            self._s_center.setCurrentIndex(1)
            self._single_result = job.result.output_path
            orig = job.result.original_size; opt = job.result.optimized_size
            if orig > 0:
                self._s_diff.setText(
                    f"<span style='color:#FF5252;'>{_fmt(orig)}</span>"
                    f"<span style='color:rgba(255,255,255,0.45);'>&nbsp;→&nbsp;</span>"
                    f"<span style='color:#FFD54F;'>{_fmt(opt)}</span>"
                )
            else:
                self._s_diff.setText(f"<span style='color:#FFD54F;'>{_fmt(opt)}</span>")

            if job.result.resolution:
                self._s_res_lbl.setText(job.result.resolution)
            else:
                self._s_res_lbl.setText("Done")
            self._btn_undo.show()
            self._btn_minus.show()
            # Show aggressive button only if this was a normal optimization
            if self._single_aggressive:
                self._btn_zap.hide()
            else:
                self._btn_zap.show()

            # Auto-dismiss completed single result after 30s
            self._start_auto_dismiss()
            
            if getattr(self.settings, 'auto_copy_to_clipboard', False):
                self._do_auto_copy(job.result.output_path)
        elif job.status == "failed":
            self._s_close.setIcon(_icon("x-bold.svg"))
            self._s_center.setCurrentIndex(1)
            self._s_diff.setText("Failed")
            self._s_res_lbl.setText(
                f"<span style='color:rgba(220,80,80,0.85);'>{job.error_message}</span>"
            )
            self._btn_undo.show()
        elif job.status == "cached":
            # Render "Already optimized" cache hit state with force-reoptimize option and auto-dismissal
            self._s_close.setIcon(_icon("x-bold.svg"))
            self._s_center.setCurrentIndex(1)
            self._s_diff.setText(
                "<span style='color:rgba(76,175,80,0.9);font-weight:600;'>Already optimized</span>"
            )
            self._s_res_lbl.setText(
                "<span style='color:rgba(255,255,255,0.45);'>Skipped — file unchanged</span>"
            )
            self._btn_undo.hide()
            self._btn_minus.hide()
            self._btn_zap.hide()
            self._btn_play.show()  # Let user force re-optimize

            # Auto-dismiss back to idle after 5 seconds instead of 3
            if self._cached_timer:
                self._cached_timer.stop()
            self._cached_timer = QTimer(self)
            self._cached_timer.setSingleShot(True)
            self._cached_timer.timeout.connect(self._reset_to_idle)
            self._cached_timer.start(5000)

    def _update_batch_item(self, item: "BatchItem", job):
        if job.status == "processing":
            pct, detail = 0, ""
            if isinstance(job.progress, tuple) and len(job.progress) == 2:
                pct, detail = int(job.progress[0]), job.progress[1]
            elif isinstance(job.progress, (int, float)):
                pct = int(job.progress * 100)
            item.card.set_processing(pct, detail)
        elif job.status == "completed" and job.result:
            item.card.set_done(job.result.original_size, job.result.optimized_size, job.result.output_path)
            if getattr(self.settings, 'auto_copy_to_clipboard', False):
                self._do_auto_copy(job.result.output_path)
        elif job.status == "failed":
            item.card.set_failed(job.error_message or "Failed")
        elif job.status == "cached":
            item.card.set_failed("Already optimized")

    # ─── Side button actions ──────────────────────────────────────────────────

    def _downscale_single(self):
        """Downscale the current file."""
        if not self._single_job_id:
            return
        job = self.queue.jobs.get(self._single_job_id)
        if not job or not job.result:
            return
        # Re-optimize dynamically based on media thresholds. 
        # (Currently implemented as a fallback to aggressive mode; actual downscaling pending).
        src = job.result.output_path or job.command.path
        if not src.exists():
            return
        # Clear old result state
        self._single_job_id = None
        self._single_result = None
        # Create an aggressive command for smaller output
        cmd = OptimiseCommand(src, aggressive=True, output_mode=self.settings.output_mode)
        self.queue.submit(cmd)

    def _force_reoptimize_single(self):
        """Re-optimize the current file bypassing the cache with normal settings."""
        if self._cached_timer:
            self._cached_timer.stop()
            self._cached_timer = None

        if not self._single_job_id:
            return
        job = self.queue.jobs.get(self._single_job_id)
        if not job:
            return
        src = job.command.path
        if not src.exists():
            return
            
        # Clear cached hash so it doesn't get skipped
        from clyro.core.backup import file_hash
        try:
            fhash = file_hash(src)
            self.queue._optimised_cache.pop(fhash, None)
        except Exception:
            pass
            
        # Clear old result state
        self._single_job_id = None
        self._single_result = None
        # Submit normal optimization
        cmd = OptimiseCommand(src, aggressive=False, output_mode=self.settings.output_mode)
        self.queue.submit(cmd)

    def _aggressive_single(self):
        """Re-optimize the current file with aggressive settings."""
        if not self._single_job_id:
            return
        job = self.queue.jobs.get(self._single_job_id)
        if not job:
            return
        # Use the source path, not the output, to re-optimize from original
        src = job.command.path
        if not src.exists():
            return
        # Clear cached hash so it doesn't get skipped
        from clyro.core.backup import file_hash
        try:
            fhash = file_hash(src)
            self.queue._optimised_cache.pop(fhash, None)
        except Exception:
            pass
        # Clear old result state
        self._single_job_id = None
        self._single_result = None
        # Submit aggressive optimization
        cmd = OptimiseCommand(src, aggressive=True, output_mode=self.settings.output_mode)
        self.queue.submit(cmd)

    def _undo_single(self):
        """Restore the original file from backup."""
        if not self._single_job_id:
            return
        job = self.queue.jobs.get(self._single_job_id)
        if not job:
            self._reset_to_idle()
            return
        from clyro.core.backup import restore_file
        backup_path = getattr(job, 'backup_path', None)
        if backup_path and Path(backup_path).exists():
            try:
                restore_file(Path(backup_path), job.command.path)
            except Exception as e:
                logger.warning(f"Undo failed: {e}")
        self._reset_to_idle()

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _do_auto_copy(self, path: Path):
        if not path or not path.exists(): return
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QMimeData, QUrl
        clipboard = QApplication.clipboard()
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(path))])
        clipboard.setMimeData(mime)

    def _reveal_single(self):
        import sys, subprocess
        if self._single_result and self._single_result.exists():
            if sys.platform == "win32":
                subprocess.call(["explorer", "/select,", str(self._single_result)])

    def _start_auto_dismiss(self):
        """Auto-dismiss completed single result after 30s."""
        if self._auto_dismiss_timer:
            self._auto_dismiss_timer.stop()
        self._auto_dismiss_timer = QTimer()
        self._auto_dismiss_timer.setSingleShot(True)
        self._auto_dismiss_timer.setInterval(30_000)
        self._auto_dismiss_timer.timeout.connect(self._auto_dismiss_result)
        self._auto_dismiss_timer.start()

    def _auto_dismiss_result(self):
        """Reset to idle if user hasn't interacted with the completed result."""
        if self._single_job_id and self._s_center.currentIndex() == 1:
            self._reset_to_idle()
        self._auto_dismiss_timer = None

    def enterEvent(self, event):
        """Pause auto-dismiss while user hovers over the dropzone."""
        if self._auto_dismiss_timer:
            self._auto_dismiss_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Resume auto-dismiss when user leaves the dropzone."""
        if self._auto_dismiss_timer:
            self._auto_dismiss_timer.start()
        super().leaveEvent(event)

    def _reset_to_idle(self):
        if self._auto_dismiss_timer:
            self._auto_dismiss_timer.stop(); self._auto_dismiss_timer = None
        if self._single_job_id:
            self.queue.cancel_job(self._single_job_id)
        self._single_job_id = None; self._single_result = None
        self._name_pill.hide(); self._conv_pill.hide(); self._merge_pill.hide(); self._s_actions.hide()
        self._shell_stack.setCurrentIndex(0)
        self._idle_title.setText("Drop files"); self._idle_hint.setText("⌥ Convert  ·  ⇧ Max")
        self._apply_size(mode="idle")

    def _remove_item(self, job_id: str):
        self.queue.cancel_job(job_id)
        item = self._batch_items.pop(job_id, None)
        if item: self._items_lay.removeWidget(item); item.deleteLater()
        if not self._batch_items: self._clear_all()
        else: self._apply_size(mode="batch", card_count=len(self._batch_items))

    def _clear_all(self):
        for item in list(self._batch_items.values()):
            self._items_lay.removeWidget(item); item.deleteLater()
        self._batch_items.clear(); 
        self.queue.clear_history() 
        self._reset_to_idle()

    def _copy_all_results(self):
        """FloatingResult 'Copy all' pattern for batch items."""
        urls = []
        for item in self._batch_items.values():
            if item.output_path and item.output_path.exists():
                from PyQt6.QtCore import QUrl
                urls.append(QUrl.fromLocalFile(str(item.output_path)))
        
        if not urls: return
        
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QMimeData
        
        clipboard = QApplication.clipboard()
        mime = QMimeData()
        mime.setUrls(urls)
        clipboard.setMimeData(mime)
        
        # visual feedback
        old_text = self._copy_all_btn.text()
        self._copy_all_btn.setText("Copied!")
        self._copy_all_btn.setStyleSheet("""
            QPushButton {
                background: rgba(76, 175, 80, 0.15);
                border: 1px solid rgba(76, 175, 80, 0.3);
                border-radius: 6px;
                font-size: 11px;
                font-weight: bold;
                color: #4CAF50;
                padding: 6px 12px;
                margin: 2px;
            }
        """)
        
        QTimer.singleShot(2000, lambda: (
            self._copy_all_btn.setText(old_text),
            self._copy_all_btn.setStyleSheet(self._base_foot_btn_style)
        ))

    def _save_to_folder(self):
        """FloatingResult 'Save to folder' pattern for batch items."""
        paths = [item.output_path for item in self._batch_items.values() if item.output_path and item.output_path.exists()]
        if not paths: return

        from PyQt6.QtWidgets import QFileDialog
        import shutil, sys, os, subprocess

        dest_dir = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if not dest_dir: return
        dest_path = Path(dest_dir)

        try:
            for p in paths:
                shutil.copy2(p, dest_path / p.name)
            
            # visual feedback
            old_text = self._save_to_folder_btn.text()
            self._save_to_folder_btn.setText("Saved!")
            self._save_to_folder_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(76, 175, 80, 0.15);
                    border: 1px solid rgba(76, 175, 80, 0.3);
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: bold;
                    color: #4CAF50;
                    padding: 6px 12px;
                    margin: 2px;
                }
            """)
            QTimer.singleShot(2000, lambda: (
                self._save_to_folder_btn.setText(old_text),
                self._save_to_folder_btn.setStyleSheet(self._base_foot_btn_style)
            ))

            # Reveal folder
            if sys.platform == "win32":
                os.startfile(dest_dir)
            elif sys.platform == "darwin":
                subprocess.call(["open", dest_dir])
        except Exception as e:
            self._flash_error("Failed to save all files")
            logger.error(f"Save to folder failed: {e}")

    def _cancel_all(self):
        for job_id in list(self._batch_items.keys()):
            self.queue.cancel_job(job_id)

    def quit(self):
        """Cancel all in-flight downloads and wait for threads to stop cleanly."""
        for job_id, worker in list(self._download_workers.items()):
            worker.cancel()
            worker.wait(2000)  # max 2 seconds per worker
        self._download_workers.clear()

    # ─── Window drag & double click ───────────────────────────────────────────

    def mouseDoubleClickEvent(self, e):
        """Double-click to open result."""
        if e.button() == Qt.MouseButton.LeftButton:
            if self._shell_stack.currentIndex() == 1 and self._s_center.currentIndex() == 1:
                if self._single_result and self._single_result.exists():
                    import os, sys, subprocess
                    if sys.platform == "win32":
                        os.startfile(self._single_result)
                    elif sys.platform == "darwin":
                        subprocess.call(["open", str(self._single_result)])
        super().mouseDoubleClickEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self._shell_stack.currentIndex() == 1 and self._s_center.currentIndex() == 1:
                if self._single_result and self._single_result.exists():
                    if self._shell.geometry().contains(e.pos()):
                        shell_y = e.pos().y() - self._shell.y()
                        if shell_y > 50:
                            self._file_drag_start_pos = e.pos()
                            e.accept()
                            return
            self._window_dragging = True
            self._window_drag_start_global = e.globalPosition().toPoint()
            self._window_drag_start_pos    = self.pos()
            self._shell.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if getattr(self, '_file_drag_start_pos', None):
            if not (e.buttons() & Qt.MouseButton.LeftButton): return
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QDrag
            from PyQt6.QtCore import QMimeData, QUrl
            if (e.pos() - self._file_drag_start_pos).manhattanLength() < QApplication.startDragDistance(): return
            drag = QDrag(self)
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(self._single_result))])
            drag.setMimeData(mime)
            self._file_drag_start_pos = None
            drag.exec(Qt.DropAction.CopyAction)
            return

        if getattr(self, '_window_dragging', False) and getattr(self, '_window_drag_start_global', None):
            self.move(self._window_drag_start_pos +
                      (e.globalPosition().toPoint() - self._window_drag_start_global))
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._file_drag_start_pos = None
        if e.button() == Qt.MouseButton.LeftButton:
            self._window_dragging = False
            self._window_drag_start_global = None
            self._shell.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        super().mouseReleaseEvent(e)

    def contextMenuEvent(self, event):
        if self._shell_stack.currentIndex() == 1 and self._s_center.currentIndex() == 1:
            if self._single_result and self._single_result.exists():
                from PyQt6.QtWidgets import QMenu, QApplication
                from PyQt6.QtCore import QMimeData, QUrl, QTimer
                
                menu = QMenu(self)
                menu.setStyleSheet("""
                    QMenu { background: #2A2A2A; color: white; border: 1px solid #444; border-radius: 6px; }
                    QMenu::item { padding: 6px 24px; font-size: 12px; }
                    QMenu::item:selected { background: rgba(255,255,255,0.1); border-radius: 4px; }
                """)
                copy_action = menu.addAction("Copy")
                if menu.exec(event.globalPos()) == copy_action:
                    clipboard = QApplication.clipboard()
                    mime = QMimeData()
                    mime.setUrls([QUrl.fromLocalFile(str(self._single_result))])
                    clipboard.setMimeData(mime)
                    
                    old_text = self._s_res_lbl.text()
                    self._s_res_lbl.setText("Copied!")
                    self._s_res_lbl.setStyleSheet("font-family: 'Space Mono', Consolas, monospace; font-size:12px;font-weight:600;color:#4CAF50;")
                    QTimer.singleShot(1500, lambda: [
                        self._s_res_lbl.setText(old_text),
                        self._s_res_lbl.setStyleSheet("font-family: 'Space Mono', Consolas, monospace; font-size:12px;font-weight:600;color:rgba(255,255,255,0.85);")
                    ])
        super().contextMenuEvent(event)

# ─────────────────────────────────────────────────────────────────────────────
# BatchItem — a pill + card body pair for each file in batch mode
# ─────────────────────────────────────────────────────────────────────────────

from PyQt6.QtCore import pyqtSignal as _sig

class BatchItem(QWidget):
    """
    Vertical layout:
      ┌ NamePill (26px) ── filename.jpg ──────────────────┐
      │ CardBody (44px)  ████████░░░ 65%   Reveal   ✕     │
      └───────────────────────────────────────────────────┘
    """
    dismiss_requested = _sig(str)

    _PILL_STYLE = """
        QFrame#pill {
            background: rgba(40,35,30,230);
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
        }
    """
    _BODY_STYLE = """
        QFrame#body {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.07);
            border-top: none;
            border-top-left-radius: 0px;
            border-top-right-radius: 0px;
            border-bottom-left-radius: 12px;
            border-bottom-right-radius: 12px;
        }
    """
    _BODY_DONE_STYLE = """
        QFrame#body {
            background: rgba(255,255,255,0.07);
            border: 1px solid rgba(255,255,255,0.10);
            border-top: none;
            border-top-left-radius: 0px;
            border-top-right-radius: 0px;
            border-bottom-left-radius: 12px;
            border-bottom-right-radius: 12px;
        }
    """
    _BAR_STYLE = """
        QProgressBar{border:none;background:rgba(255,255,255,0.10);border-radius:1px;}
        QProgressBar::chunk{background:rgba(255,255,255,0.65);border-radius:1px;}
    """
    _BTN = ("QPushButton{background:rgba(255,255,255,0.18);border:none;border-radius:5px;}"
            "QPushButton:hover{background:rgba(255,255,255,0.28);}")

    def __init__(self, job_id: str, filename: str, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.output_path: Path | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        # ── Name pill ──────────────────────────────────────────────
        pill = QFrame(); pill.setObjectName("pill")
        pill.setStyleSheet(self._PILL_STYLE); pill.setFixedHeight(30)
        pr = QHBoxLayout(pill); pr.setContentsMargins(10,0,10,0); pr.setSpacing(6)

        stem = Path(filename).stem; ext = Path(filename).suffix
        if len(stem) > 16: stem = stem[:10] + "…" + stem[-4:]
        self._name_lbl = QLabel(stem)
        self._name_lbl.setMinimumWidth(10)
        self._name_lbl.setStyleSheet("font-size:11px;font-weight:700;color:rgba(255,255,255,0.40);background:transparent;")
        self._ext_lbl = QLabel(ext)
        self._ext_lbl.setStyleSheet("font-size:11px;font-weight:600;color:rgba(255,255,255,0.30);"
                               "background:transparent;")
        pr.addWidget(self._name_lbl); pr.addStretch(); pr.addWidget(self._ext_lbl)
        lay.addWidget(pill)

        # ── Card body ──────────────────────────────────────────────
        self._body = QFrame(); self._body.setObjectName("body")
        self._body.setStyleSheet(self._BODY_STYLE); self._body.setFixedHeight(48)
        bl = QVBoxLayout(self._body); bl.setContentsMargins(10,8,8,8); bl.setSpacing(4)

        row = QHBoxLayout(); row.setContentsMargins(0,0,0,0); row.setSpacing(6)
        self._status = QLabel("Queued")
        self._status.setMinimumWidth(10)
        self._status.setStyleSheet("font-size:11px;color:rgba(255,255,255,0.30);")
        dismiss = QPushButton()
        dismiss.setIcon(_icon("x-bold.svg"))
        dismiss.setIconSize(QSize(10, 10))
        dismiss.setStyleSheet(self._BTN); dismiss.setFixedSize(20,20)
        dismiss.clicked.connect(lambda: self.dismiss_requested.emit(self.job_id))
        row.addWidget(self._status,1); row.addWidget(dismiss)
        bl.addLayout(row)

        self._bar = QProgressBar()
        self._bar.setRange(0,100); self._bar.setValue(0)
        self._bar.setFixedHeight(2); self._bar.setTextVisible(False)
        self._bar.setStyleSheet(self._BAR_STYLE); self._bar.hide()
        bl.addWidget(self._bar)

        lay.addWidget(self._body)
        self.setFixedHeight(30 + 48)

        # expose to dropzone for updates
        self.card = self   # so dropzone can call item.card.set_*

    def set_queued(self):
        self._name_lbl.setStyleSheet("font-size:11px;font-weight:700;color:rgba(255,255,255,0.40);background:transparent;")
        self._ext_lbl.setStyleSheet("font-size:11px;font-weight:600;color:rgba(255,255,255,0.30);background:transparent;")
        self._status.setText("Queued")
        self._status.setStyleSheet("font-family: 'Segoe UI Variable Display', sans-serif; font-size:11px;color:rgba(255,255,255,0.25);")
        self._bar.hide()

    def set_processing(self, pct: int = 0, detail: str = ""):
        self._name_lbl.setStyleSheet("font-size:11px;font-weight:700;color:rgba(255,255,255,0.60);background:transparent;")
        self._ext_lbl.setStyleSheet("font-size:11px;font-weight:600;color:rgba(255,255,255,0.50);background:transparent;")
        self._bar.setValue(pct); self._bar.show()
        if detail:
            # downloading messages might be long
            text = f"{pct}% - {detail[:20]}" if pct > 0 else f"{detail[:25]}"
        else:
            text = f"{pct}%"
            
        self._status.setText(text)
        self._status.setStyleSheet("font-family: 'Space Mono', monospace; font-size:11px;color:rgba(255,255,255,0.45);")

    def set_done(self, orig: int, final: int, out: Path):
        self._name_lbl.setStyleSheet("font-size:11px;font-weight:700;color:rgba(255,255,255,0.95);background:transparent;")
        self._ext_lbl.setStyleSheet("font-size:11px;font-weight:600;color:rgba(255,255,255,0.85);background:transparent;")
        self.output_path = out; self._bar.hide()
        if orig > 0 and orig != final:
            txt = (f"<span style='color:#FF5252;'>{_fmt(orig)}</span>"
                   f"<span style='color:rgba(255,255,255,0.35);'>&nbsp;→&nbsp;</span>"
                   f"<span style='color:#FFD54F;'>{_fmt(final)}</span>")
        else:
            txt = f"<span style='color:#FFD54F;'>{_fmt(final)}</span>"
        self._status.setText(txt); self._status.setStyleSheet("font-family: 'Space Mono', monospace; font-size:11px;")
        self._body.setStyleSheet(self._BODY_DONE_STYLE)

    def set_failed(self, msg: str):
        self._name_lbl.setStyleSheet("font-size:11px;font-weight:700;color:rgba(255,50,50,0.80);background:transparent;")
        self._ext_lbl.setStyleSheet("font-size:11px;font-weight:600;color:rgba(255,50,50,0.70);background:transparent;")
        self._bar.hide()
        self._status.setText(msg[:38])
        self._status.setStyleSheet("font-family: 'Segoe UI Variable Display', sans-serif; font-size:11px;color:rgba(255,82,82,0.85);")

    # ─── Mouse Interaction (Drag Out, Copy, Double Click) ──────────────────────
    
    def mouseDoubleClickEvent(self, event):
        """Double-click to open result."""
        if event.button() == Qt.MouseButton.LeftButton and self.output_path and self.output_path.exists():
            import os, sys, subprocess
            if sys.platform == "win32":
                os.startfile(self.output_path)
            elif sys.platform == "darwin":
                subprocess.call(["open", str(self.output_path)])
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        if not self.output_path or not self.output_path.exists():
            return
            
        from PyQt6.QtWidgets import QMenu, QApplication
        from PyQt6.QtCore import QMimeData, QUrl, QTimer
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #2A2A2A; color: white; border: 1px solid #444; border-radius: 6px; }
            QMenu::item { padding: 6px 24px; font-size: 12px; }
            QMenu::item:selected { background: rgba(255,255,255,0.1); border-radius: 4px; }
        """)
        
        copy_action = menu.addAction("Copy")
        if menu.exec(event.globalPos()) == copy_action:
            clipboard = QApplication.clipboard()
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(self.output_path))])
            clipboard.setMimeData(mime)
            
            old_text = self._status.text()
            self._status.setText("Copied!")
            self._status.setStyleSheet("font-family: 'Space Mono', monospace; font-size:11px; color: #4CAF50; font-weight: bold;")
            
            QTimer.singleShot(1500, lambda: [
                self._status.setText(old_text),
                self._status.setStyleSheet("font-family: 'Space Mono', monospace; font-size:11px;")
            ])

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.output_path and self.output_path.exists():
            self._drag_start_pos = event.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not getattr(self, '_drag_start_pos', None):
            super().mouseMoveEvent(event)
            return
            
        if not (event.buttons() & Qt.MouseButton.LeftButton): return
            
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QDrag
        from PyQt6.QtCore import QMimeData, QUrl
        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
            
        drag = QDrag(self)
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.output_path))])
        drag.setMimeData(mime)
        self._drag_start_pos = None
        
        drag.exec(Qt.DropAction.CopyAction)

    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)
