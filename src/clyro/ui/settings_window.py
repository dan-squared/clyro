from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QWidget, QStackedWidget, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QFont

from clyro.ui.settings_pages.general import GeneralPage
from clyro.ui.settings_pages.quality import QualityPage
from clyro.ui.settings_pages.dropzone_shortcuts import DropzoneShortcutsPage
from clyro.ui.settings_pages.about import AboutPage

# ─── Design Tokens ──────────────────────────────────────────────────────────
BG_DARK      = "#1A1A1A"
BG_SIDEBAR   = "#141414"
SEPARATOR    = "rgba(255,255,255,0.06)"
TEXT_PRIMARY = "rgba(255,255,255,0.85)"
TEXT_MUTED   = "rgba(255,255,255,0.35)"
ACCENT       = "rgba(255,255,255,0.75)"


class _NavItem(QPushButton):
    def __init__(self, label: str, index: int):
        super().__init__(label)
        self.index = index
        self.setCheckable(True)
        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                background: transparent;
                border: none;
                border-radius: 7px;
                padding: 9px 14px;
                font-size: 13px;
                font-weight: 500;
                color: {TEXT_MUTED};
            }}
            QPushButton:checked {{
                background: rgba(255,255,255,0.07);
                color: {TEXT_PRIMARY};
                font-weight: 600;
            }}
            QPushButton:hover:!checked {{
                background: rgba(255,255,255,0.04);
                color: rgba(255,255,255,0.6);
            }}
        """)


class SettingsWindow(QDialog):
    settings_saved = pyqtSignal()

    def __init__(self, settings, settings_store, tools_availability):
        super().__init__()
        self.settings = settings
        self.store = settings_store

        self.setWindowTitle("Clyro — Settings")
        self.setFixedSize(660, 480)
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setStyleSheet(f"""
            QDialog {{
                background: {BG_DARK};
                color: {TEXT_PRIMARY};
                font-family: -apple-system, "Segoe UI", BlinkMacSystemFont, sans-serif;
            }}
            QScrollArea, QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                width: 5px; background: transparent; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.15); border-radius: 2px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(160)
        sidebar.setStyleSheet(f"""
            QWidget {{
                background: {BG_SIDEBAR};
                border-right: 1px solid {SEPARATOR};
            }}
        """)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(10, 20, 10, 10)
        sb_layout.setSpacing(2)

        sidebar_title = QLabel("Settings")
        sidebar_title.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: rgba(255,255,255,0.5); "
            "padding-left: 4px; margin-bottom: 12px; background: transparent;"
        )
        sb_layout.addWidget(sidebar_title)

        self._nav_items: list[_NavItem] = []
        nav_labels = ["General", "Quality", "Dropzone", "About"]
        for i, label in enumerate(nav_labels):
            item = _NavItem(label, i)
            item.clicked.connect(lambda _, idx=i: self._switch(idx))
            sb_layout.addWidget(item)
            self._nav_items.append(item)

        sb_layout.addStretch()
        root.addWidget(sidebar)

        # ── Content Area ──────────────────────────────────────────────
        content_wrapper = QWidget()
        content_wrapper.setStyleSheet("background: transparent;")
        content_main = QVBoxLayout(content_wrapper)
        content_main.setContentsMargins(0, 0, 0, 0)
        content_main.setSpacing(0)

        # Page container
        self.pages = QStackedWidget()
        self.pages.setStyleSheet("background: transparent;")

        def _scrollable(page_widget: QWidget) -> QScrollArea:
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            sa.setFrameShape(QFrame.Shape.NoFrame)
            sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            sa.setWidget(page_widget)
            return sa

        self.page_general  = GeneralPage(self.settings)
        self.page_quality  = QualityPage(self.settings)
        self.page_dropzone = DropzoneShortcutsPage(self.settings)
        self.page_about    = AboutPage(tools_availability)

        pages = [self.page_general, self.page_quality, self.page_dropzone, self.page_about]
        for page in pages:
            page.setContentsMargins(28, 24, 28, 24)
            self.pages.addWidget(_scrollable(page))

        content_main.addWidget(self.pages, 1)

        # ── Bottom Footer Bar ─────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet(f"""
            QWidget {{
                background: {BG_DARK};
                border-top: 1px solid {SEPARATOR};
            }}
        """)
        footer.setFixedHeight(52)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 0, 20, 0)
        footer_layout.setSpacing(10)

        self.btn_restore = QPushButton("Restore Defaults")
        self.btn_restore.setFixedSize(120, 32)
        self.btn_restore.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 13px;
                color: rgba(255,255,255,0.35);text-align: left;
            }
            QPushButton:hover {
                color: rgba(255,255,255,0.7);
            }
        """)
        self.btn_restore.clicked.connect(self._restore_defaults)
        footer_layout.addWidget(self.btn_restore)

        footer_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedSize(90, 32)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 7px;
                font-size: 13px;
                color: rgba(255,255,255,0.5);
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.05);
                color: rgba(255,255,255,0.7);
            }
        """)
        self.btn_cancel.clicked.connect(self.close)

        self.btn_save = QPushButton("Save")
        self.btn_save.setFixedSize(90, 32)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.12);
                border: 1px solid rgba(255,255,255,0.18);
                border-radius: 7px;
                font-size: 13px;
                font-weight: 600;
                color: rgba(255,255,255,0.9);
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.18);
            }
            QPushButton:pressed {
                background: rgba(255,255,255,0.08);
            }
        """)
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self._save_and_close)

        footer_layout.addWidget(self.btn_cancel)
        footer_layout.addWidget(self.btn_save)

        content_main.addWidget(footer)
        root.addWidget(content_wrapper, 1)

        # Initialise first page
        self._switch(0)

    def _switch(self, index: int):
        self.pages.setCurrentIndex(index)
        for i, item in enumerate(self._nav_items):
            item.setChecked(i == index)

    def _save_and_close(self):
        self.page_general.save_settings()
        self.page_quality.save_settings()
        self.page_dropzone.save_settings()
        self.store.save(self.settings)
        self.settings_saved.emit()
        self.accept()

    def _restore_defaults(self):
        from clyro.config.schema import Settings
        defaults = Settings()
        # Update the live settings with default values
        # This only takes effect if the user clicks Save afterwards
        for key in Settings.__annotations__:
            setattr(self.settings, key, getattr(defaults, key))
        
        self.page_general.load_settings()
        self.page_quality.load_settings()
        self.page_dropzone.load_settings()
