from PyQt6.QtGui import QColor

class Theme:
    BG_DEFAULT = QColor("#1E1E1E")
    BG_HOVER = QColor("#2D2D2D")
    
    BORDER_DEFAULT = QColor("#444444")
    BORDER_OPTIMIZE = QColor("#4CAF50")      # Green
    BORDER_AGGRESSIVE = QColor("#FF9800")    # Orange
    BORDER_CONVERT = QColor("#2196F3")       # Blue
    
    TEXT_PRIMARY = QColor("#FFFFFF")
    TEXT_SECONDARY = QColor("#AAAAAA")
    
    SUCCESS = QColor("#4CAF50")
    ERROR = QColor("#F44336")
    PROGRESS = QColor("#2196F3")
    
    FONT_FAMILY = "Segoe UI"
    
    STYLE_SHEET = """
        QWidget {
            background-color: #1E1E1E;
            color: #FFFFFF;
            font-family: 'Segoe UI';
        }
        QProgressBar {
            border: 1px solid #444;
            border-radius: 4px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #2196F3;
            width: 1px;
        }
        QPushButton {
            background-color: #2D2D2D;
            border: 1px solid #444;
            border-radius: 4px;
            padding: 4px 12px;
        }
        QPushButton:hover {
            background-color: #444444;
        }
    """
