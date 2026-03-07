from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from clyro.ui import settings_theme as theme
from clyro.ui.settings_pages.about import AboutPage
from clyro.ui.settings_pages.dropzone_shortcuts import DropzoneShortcutsPage
from clyro.ui.settings_pages.general import GeneralPage
from clyro.ui.settings_pages.quality import QualityPage


class _NavItem(QPushButton):
    def __init__(self, label: str, index: int):
        super().__init__(label)
        self.index = index
        self.setCheckable(True)
        self.setStyleSheet(
            f"""
            QPushButton {{
                text-align: left;
                background: {theme.SURFACE_BG};
                border: 1px solid transparent;
                border-radius: 10px;
                padding: 12px 14px;
                font-size: 14px;
                font-weight: 700;
                color: {theme.TEXT_MUTED};
                font-family: {theme.FONT_STACK};
            }}
            QPushButton:checked {{
                background: {theme.SURFACE_ALT};
                border: 1px solid {theme.BORDER};
                color: {theme.TEXT_PRIMARY};
            }}
            QPushButton:hover:!checked {{
                background: {theme.SURFACE_ALT};
                border: 1px solid {theme.BORDER};
                color: {theme.TEXT_SECONDARY};
            }}
            """
        )


class SettingsWindow(QDialog):
    settings_saved = pyqtSignal()

    def __init__(self, settings, settings_store, tools_availability, app_manager=None):
        super().__init__()
        theme.ensure_fonts_loaded()
        self.settings = settings
        self.store = settings_store
        self.app_manager = app_manager

        self.setWindowTitle("Clyro - Settings")
        self.setFixedSize(736, 544)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {theme.WINDOW_BG};
                color: {theme.TEXT_PRIMARY};
                font-family: {theme.FONT_STACK};
            }}
            QScrollArea, QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                width: 8px;
                background: transparent;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: #cfd4dd;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #bcc3ce;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            """
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QWidget()
        sidebar.setFixedWidth(188)
        sidebar.setStyleSheet(
            f"""
            QWidget {{
                background: {theme.SIDEBAR_BG};
                border-right: 1px solid {theme.BORDER};
            }}
            """
        )
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(14, 24, 14, 18)
        sb_layout.setSpacing(4)

        sidebar_title = QLabel("Settings")
        sidebar_title.setStyleSheet(
            f"""
            font-size: 28px;
            font-weight: 700;
            color: {theme.TEXT_PRIMARY};
            padding-left: 4px;
            background: transparent;
            font-family: {theme.FONT_STACK};
            """
        )
        sidebar_subtitle = QLabel("Output, quality, updates, and access in one place.")
        sidebar_subtitle.setWordWrap(True)
        sidebar_subtitle.setStyleSheet(
            f"font-size: 12px; color: {theme.TEXT_MUTED}; padding: 0 4px 12px 4px; font-family: {theme.FONT_STACK};"
        )

        sb_layout.addWidget(sidebar_title)
        sb_layout.addWidget(sidebar_subtitle)

        self._nav_items: list[_NavItem] = []
        for index, label in enumerate(["General", "Quality", "Dropzone", "About"]):
            item = _NavItem(label, index)
            item.clicked.connect(lambda _, idx=index: self._switch(idx))
            sb_layout.addWidget(item)
            self._nav_items.append(item)

        sb_layout.addStretch()
        root.addWidget(sidebar)

        content_wrapper = QWidget()
        content_wrapper.setStyleSheet(
            f"background: {theme.WINDOW_PANEL}; border: none;"
        )
        content_main = QVBoxLayout(content_wrapper)
        content_main.setContentsMargins(0, 0, 0, 0)
        content_main.setSpacing(0)

        self.pages = QStackedWidget()
        self.pages.setStyleSheet("background: transparent;")

        def _scrollable(page_widget: QWidget) -> QScrollArea:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setWidget(page_widget)
            return scroll

        self.page_general = GeneralPage(self.settings)
        self.page_quality = QualityPage(self.settings)
        self.page_dropzone = DropzoneShortcutsPage(self.settings)
        self.page_about = AboutPage(
            self.settings,
            tools_availability,
            check_updates_callback=(
                self.app_manager.request_manual_update_check if self.app_manager else None
            ),
            update_now_callback=(
                self.app_manager.trigger_update_now if self.app_manager else None
            ),
        )

        for page in [
            self.page_general,
            self.page_quality,
            self.page_dropzone,
            self.page_about,
        ]:
            page.setContentsMargins(28, 24, 28, 24)
            self.pages.addWidget(_scrollable(page))

        content_main.addWidget(self.pages, 1)

        footer = QWidget()
        footer.setFixedHeight(60)
        footer.setStyleSheet(
            f"""
            QWidget {{
                background: {theme.WINDOW_PANEL};
                border-top: none;
            }}
            """
        )
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(22, 0, 22, 0)
        footer_layout.setSpacing(10)

        self.btn_restore = QPushButton("Restore Defaults")
        self.btn_restore.setFixedHeight(36)
        self.btn_restore.setStyleSheet(theme.LINK_BUTTON_STYLE)
        self.btn_restore.clicked.connect(self._restore_defaults)
        footer_layout.addWidget(self.btn_restore)

        footer_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedSize(96, 36)
        self.btn_cancel.setStyleSheet(theme.SUBTLE_BUTTON_STYLE)
        self.btn_cancel.clicked.connect(self.close)

        self.btn_save = QPushButton("Save")
        self.btn_save.setFixedSize(96, 36)
        self.btn_save.setDefault(True)
        self.btn_save.setStyleSheet(theme.PRIMARY_BUTTON_STYLE)
        self.btn_save.clicked.connect(self._save_and_close)

        footer_layout.addWidget(self.btn_cancel)
        footer_layout.addWidget(self.btn_save)

        content_main.addWidget(footer)
        root.addWidget(content_wrapper, 1)

        self._switch(0)
        self.refresh_status()

    def _switch(self, index: int):
        self.pages.setCurrentIndex(index)
        for i, item in enumerate(self._nav_items):
            item.setChecked(i == index)
        if hasattr(self.page_about, "refresh_status"):
            self.page_about.refresh_status()

    def refresh_status(self):
        if hasattr(self.page_about, "refresh_status"):
            self.page_about.refresh_status()

    def set_update_status(self, message: str, tone: str = "muted"):
        if hasattr(self.page_about, "set_update_status"):
            self.page_about.set_update_status(message, tone)

    def set_update_action(self, label: str | None = None, *, enabled: bool = True, visible: bool = True):
        if hasattr(self.page_about, "set_update_action"):
            self.page_about.set_update_action(label, enabled=enabled, visible=visible)

    def _save_and_close(self):
        self.page_general.save_settings()
        self.page_quality.save_settings()
        self.page_dropzone.save_settings()
        self.page_about.refresh_status()
        self.store.save(self.settings)
        self.settings_saved.emit()
        self.accept()

    def _restore_defaults(self):
        from clyro.config.schema import Settings

        defaults = Settings()
        for key in Settings.__annotations__:
            setattr(self.settings, key, getattr(defaults, key))

        self.page_general.load_settings()
        self.page_quality.load_settings()
        self.page_dropzone.load_settings()
        self.page_about.refresh_status()
