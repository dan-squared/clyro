from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout

from clyro.ui import settings_theme as theme


class UpdateDialog(QDialog):
    def __init__(self, current_version: str, update_info: dict, parent=None):
        super().__init__(parent)
        theme.ensure_fonts_loaded()
        self.choice = "later"
        self.update_info = update_info

        self.setWindowTitle("Clyro Update Available")
        self.setMinimumSize(560, 400)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {theme.WINDOW_BG};
                color: {theme.TEXT_PRIMARY};
                font-family: {theme.FONT_STACK};
            }}
            QLabel {{
                background: transparent;
            }}
            QTextEdit {{
                background: {theme.SURFACE_BG};
                border: 1px solid {theme.BORDER};
                border-radius: 12px;
                color: {theme.TEXT_PRIMARY};
                padding: 10px;
                font-size: 12px;
                font-family: {theme.VALUE_FONT_STACK};
            }}
            QPushButton {{
                border-radius: 10px;
                padding: 9px 14px;
                font-size: 12px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title = QLabel(f"Version {update_info['version']} is ready")
        title.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel(
            f"Current version: {current_version}  -  New version: {update_info['version']}"
        )
        subtitle.setStyleSheet(
            f"font-size: 12px; color: {theme.TEXT_MUTED}; font-family: {theme.VALUE_FONT_STACK};"
        )
        layout.addWidget(subtitle)

        helper = QLabel("Review the release notes, then choose how Clyro should proceed.")
        helper.setStyleSheet(f"font-size: 13px; color: {theme.TEXT_SECONDARY};")
        layout.addWidget(helper)

        checksum = update_info.get("sha256")
        checksum_source = update_info.get("checksum_source")
        trust = QLabel()
        trust.setWordWrap(True)
        if checksum:
            source_text = checksum_source or "published metadata"
            trust.setText(
                f"Published SHA-256 from {source_text}: {checksum[:16]}...{checksum[-16:]}"
            )
            trust.setStyleSheet(
                f"font-size: 12px; color: {theme.SUCCESS}; font-family: {theme.VALUE_FONT_STACK};"
            )
        else:
            trust.setText(
                "No published installer checksum was found for this release. Automatic verification is unavailable."
            )
            trust.setStyleSheet(
                f"font-size: 12px; color: {theme.WARNING}; font-family: {theme.VALUE_FONT_STACK};"
            )
        layout.addWidget(trust)

        notes = QTextEdit()
        notes.setReadOnly(True)
        body = (update_info.get("notes") or "").strip() or "No release notes were provided for this version."
        notes.setPlainText(body[:5000])
        layout.addWidget(notes, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        later_btn = QPushButton("Later")
        later_btn.setStyleSheet(theme.SUBTLE_BUTTON_STYLE)
        later_btn.clicked.connect(self._later)

        skip_btn = QPushButton("Skip This Version")
        skip_btn.setStyleSheet(theme.BUTTON_STYLE)
        skip_btn.clicked.connect(self._skip)

        install_label = "Update Now" if update_info.get("download_url") else "Open Release Page"
        install_btn = QPushButton(install_label)
        install_btn.setDefault(True)
        install_btn.setStyleSheet(theme.PRIMARY_BUTTON_STYLE)
        install_btn.clicked.connect(self._install)

        button_row.addWidget(later_btn)
        button_row.addStretch()
        button_row.addWidget(skip_btn)
        button_row.addWidget(install_btn)
        layout.addLayout(button_row)

    def _later(self):
        self.choice = "later"
        self.accept()

    def _skip(self):
        self.choice = "skip"
        self.accept()

    def _install(self):
        self.choice = "install"
        self.accept()


class UpdateReadyDialog(QDialog):
    def __init__(self, version: str, parent=None):
        super().__init__(parent)
        theme.ensure_fonts_loaded()
        self.choice = "later"

        self.setWindowTitle("Update Ready")
        self.setFixedSize(400, 176)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {theme.WINDOW_BG};
                color: {theme.TEXT_PRIMARY};
                font-family: {theme.FONT_STACK};
            }}
            QLabel {{
                background: transparent;
            }}
            QPushButton {{
                border-radius: 10px;
                padding: 9px 14px;
                font-size: 12px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        title = QLabel("Update ready")
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        layout.addWidget(title)

        body = QLabel(
            f"Version {version} has been downloaded. Install it now, or choose Later to install when Clyro closes."
        )
        body.setWordWrap(True)
        body.setStyleSheet(
            f"font-size: 12px; color: {theme.TEXT_SECONDARY}; font-family: {theme.VALUE_FONT_STACK};"
        )
        layout.addWidget(body)

        actions = QHBoxLayout()
        actions.setSpacing(10)

        later_btn = QPushButton("Later")
        later_btn.setStyleSheet(theme.SUBTLE_BUTTON_STYLE)
        later_btn.clicked.connect(self._later)

        now_btn = QPushButton("Install Now")
        now_btn.setDefault(True)
        now_btn.setStyleSheet(theme.PRIMARY_BUTTON_STYLE)
        now_btn.clicked.connect(self._now)

        actions.addWidget(now_btn)
        actions.addWidget(later_btn)
        actions.addStretch()
        layout.addLayout(actions)

    def _later(self):
        self.choice = "later"
        self.accept()

    def _now(self):
        self.choice = "now"
        self.accept()
