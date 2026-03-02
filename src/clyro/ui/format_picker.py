from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGridLayout
from PyQt6.QtCore import Qt, pyqtSignal
from clyro.core.types import MediaType

class FormatPicker(QWidget):
    format_selected = pyqtSignal(str) # format string like 'jpg', 'pdf'
    cancelled = pyqtSignal()
    
    def __init__(self, filename: str, media_type: MediaType, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        
        # Container to give styling (borders, background) since WA_TranslucentBackground is used
        self.container = QWidget(self)
        self.container.setObjectName("pickerContainer")
        self.container.setStyleSheet("""
            #pickerContainer {
                background-color: #2D2D2D;
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 8px;
            }
        """)
        self.container_layout = QVBoxLayout(self.container)
        
        self.label = QLabel(f"Convert: {filename}")
        self.label.setStyleSheet("font-weight: bold; margin-bottom: 8px;")
        self.container_layout.addWidget(self.label)
        
        self.grid = QGridLayout()
        self.container_layout.addLayout(self.grid)
        
        self._populate_options(media_type)
        
        self.btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancelled.emit)
        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.cancel_btn)
        self.container_layout.addLayout(self.btn_layout)
        
        self.layout.addWidget(self.container)
        
    def _populate_options(self, media_type: MediaType):
        options = []
        if media_type == MediaType.IMAGE:
            options = ["JPG", "PNG", "WebP", "PDF", "BMP", "TIFF"]
        elif media_type == MediaType.VIDEO:
            options = ["MP4", "WebM", "GIF", "MKV"]
        elif media_type == MediaType.DOCUMENT:
            options = ["JPG", "PNG", "DOCX"]
            
        row = 0
        col = 0
        for opt in options:
            btn = QPushButton(opt)
            btn.setFixedSize(60, 30)
            btn.clicked.connect(lambda checked, f=opt: self.format_selected.emit(f))
            self.grid.addWidget(btn, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1
