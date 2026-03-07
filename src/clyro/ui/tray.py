from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction

class TrayIcon(QSystemTrayIcon):
    def __init__(self, app_manager, icon: QIcon, parent=None):
        super().__init__(icon, parent)
        self.app_manager = app_manager
        
        self.setToolTip("Clyro - Drag and Drop Optimizer")
        
        menu = QMenu()
        
        act_show = QAction("Show Dropzone", self)
        act_show.triggered.connect(self.app_manager.show_dropzone)
        menu.addAction(act_show)
        
        act_settings = QAction("Settings", self)
        act_settings.triggered.connect(self.app_manager.show_settings)
        menu.addAction(act_settings)

        act_updates = QAction("Check for Updates", self)
        act_updates.triggered.connect(self.app_manager.request_manual_update_check)
        menu.addAction(act_updates)
        
        menu.addSeparator()
        
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self.app_manager.quit)
        menu.addAction(act_quit)
        
        self.setContextMenu(menu)
        self.activated.connect(self._on_activate)
        
    def _on_activate(self, reason):
        try:
            is_trigger = (reason == QSystemTrayIcon.ActivationReason.Trigger)
        except TypeError:
            try:
                is_trigger = (int(reason) == int(QSystemTrayIcon.ActivationReason.Trigger))
            except Exception:
                is_trigger = False
        if is_trigger:
            self.app_manager.toggle_dropzone()
