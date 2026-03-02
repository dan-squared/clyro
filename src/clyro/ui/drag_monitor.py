from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtWidgets import QApplication

class DragMonitor(QObject):
    modifiers_changed = pyqtSignal(object) # emit Qt.KeyboardModifiers
    
    def __init__(self):
        super().__init__()
        # In a real app we might use native OS hooks for global tracking,
        # but locally we can just poll QApplication.keyboardModifiers()
        # when needed or rely on the DragEnter events directly on the Dropzone.
        # This acts as a proxy if we implement a timer or hook layer.

    def get_current_modifiers(self):
        return QApplication.keyboardModifiers()
