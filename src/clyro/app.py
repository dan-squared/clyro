import sys
import logging
import atexit
import os
import glob
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer

# Lightweight config — no heavy deps
from clyro.config.store import SettingsStore
from clyro.ui.dropzone import DropzoneWindow
from clyro.ui.tray import TrayIcon
from clyro.ui.theme import Theme

# Heavy modules imported lazily inside methods:
#   clyro.core.tools, clyro.core.dispatcher, clyro.core.optimize,
#   clyro.core.convert, clyro.core.image, clyro.core.video,
#   clyro.core.pdf, clyro.ipc.server, clyro.updater, winreg

logger = logging.getLogger(__name__)

class AppManager:
    def __init__(self, app: QApplication, icon: QIcon | None = None):
        self.app = app
        app.setStyleSheet(Theme.STYLE_SHEET)
        
        # ── Phase 1: Instant — load config + show window ──────────────
        self.store = SettingsStore()
        self.settings = self.store.load()
        
        # Lightweight placeholders (no heavy core imports yet)
        self.tools = None
        self.cmd_dispatch = None
        self.queue_service = None
        self._handlers_ready = False
        self.ipc = None
        self.settings_window = None
        
        # Build & show UI immediately (uses only PyQt6 — no heavy deps)
        self.dropzone = DropzoneWindow(None, self.settings)  # queue_service=None for now
        
        # Position at bottom right
        screen_geom = self.app.primaryScreen().availableGeometry()
        x = screen_geom.width() - self.dropzone.width() - 40
        y = screen_geom.height() - self.dropzone.height() - 40
        self.dropzone.move(x, y)
        
        # Tray icon (lightweight)
        app_icon = icon or QIcon()
        self.tray = TrayIcon(self, app_icon)
        if self.settings.show_tray:
            self.tray.show()
            
        # Show the window NOW — user sees it in <500ms
        self.dropzone.show()
        
        # ── Phase 2: Deferred — heavy init after event loop starts ────
        # QTimer.singleShot(0) runs immediately after the event loop
        # begins processing events, i.e. after the window is painted.
        QTimer.singleShot(0, self._deferred_init)
        
        # Graceful process cleanup on exit
        atexit.register(self._kill_orphan_processes)

    # ── Deferred initialization ────────────────────────────────────────────

    def _deferred_init(self):
        """Heavy init that runs after the window is already on screen."""
        self._ensure_handlers()   # discover tools + build handlers
        
        # Start IPC server (imports aiohttp lazily)
        QTimer.singleShot(200, self._start_ipc)
        
        # Non-critical deferred work
        QTimer.singleShot(500, lambda: self._apply_startup_registry(self.settings.start_on_login))
        QTimer.singleShot(2000, self._check_for_updates)
        QTimer.singleShot(2000, self._warn_missing_tools)
        
        # Temp file cleanup timer
        self._cleanup_timer = QTimer()
        self._cleanup_timer.timeout.connect(self._cleanup_temp_files)
        self._cleanup_timer.start(600_000)  # every 10 minutes
        QTimer.singleShot(5000, self._cleanup_temp_files)  # initial sweep after 5s

    def _ensure_handlers(self):
        """Lazily discover tools and build handlers. Safe to call multiple times.
        
        This is the on-demand fallback: if a file is dropped before
        _deferred_init() runs, the dropzone's _submit() will trigger this.
        """
        if self._handlers_ready:
            return
        
        from clyro.core.tools import discover_tools
        from clyro.core.dispatcher import CommandDispatcher
        from clyro.job_queue.service import QueueService
        
        self.tools = discover_tools()
        self.cmd_dispatch = CommandDispatcher(self.settings, self.tools, None, None)
        self.queue_service = QueueService(self.cmd_dispatch)
        self._build_handlers()
        
        # Wire up the dropzone to the now-ready queue service
        self.dropzone.queue = self.queue_service
        self.queue_service.job_added.connect(self.dropzone._on_job_added)
        self.queue_service.job_updated.connect(self.dropzone._on_job_updated)
        
        self._handlers_ready = True
        logger.info("Handlers initialized (deferred init complete)")

    def _start_ipc(self):
        """Start IPC server — imports aiohttp lazily."""
        from clyro.ipc.server import IpcServer
        self.ipc = IpcServer(self.dropzone)
        self.ipc.start()

    def toggle_dropzone(self):
        if self.dropzone.isVisible():
            self.dropzone.hide()
        else:
            self.dropzone.show()
            self.dropzone.activateWindow()
            
    def show_dropzone(self):
        self.dropzone.show()
        self.dropzone.activateWindow()
        
    def show_settings(self):
        self._ensure_handlers()  # need tools for settings page
        if not self.settings_window:
            from clyro.ui.settings_window import SettingsWindow
            self.settings_window = SettingsWindow(self.settings, self.store, self.tools)
            # Re-read settings instance changes when closed
            self.settings_window.settings_saved.connect(self._on_settings_saved)
            
        self.settings_window.show()
        self.settings_window.activateWindow()
        
    def _build_handlers(self):
        # Lazy-import heavy core modules only when actually needed
        from clyro.core.optimize import OptimizeDispatcher
        from clyro.core.convert import ConvertDispatcher
        from clyro.core.image import ImageHandler, ImageToImageHandler, ImageToPdfHandler
        from clyro.core.video import VideoHandler, VideoToVideoHandler, VideoToImageHandler
        from clyro.core.pdf import PdfHandler, PdfToImageHandler, PdfToWordHandler
        
        # Handlers
        ih = ImageHandler(self.settings, self.tools)
        vh = VideoHandler(self.settings, self.tools)
        ph = PdfHandler(self.settings, self.tools)
        i_i = ImageToImageHandler(self.tools)
        i_p = ImageToPdfHandler(self.tools)
        v_v = VideoToVideoHandler(self.tools)
        v_i = VideoToImageHandler(self.tools)
        p_i = PdfToImageHandler(self.tools)
        p_d = PdfToWordHandler(self.tools)
        
        opt_dispatch = OptimizeDispatcher(ih, vh, ph)
        conv_dispatch = ConvertDispatcher(i_i, i_p, v_v, v_i, p_i, p_d)
        
        # Update command router with newly instantiated handlers based on new settings
        self.cmd_dispatch.settings = self.settings
        self.cmd_dispatch.opt_dispatch = opt_dispatch
        self.cmd_dispatch.conv_dispatch = conv_dispatch
        if self.queue_service:
            self.queue_service.dispatcher = self.cmd_dispatch
        if hasattr(self, 'dropzone'):
            self.dropzone.settings = self.settings

    def _on_settings_saved(self):
        self.settings = self.store.load()
        self._build_handlers()
        self._apply_startup_registry(self.settings.start_on_login)
        if self.settings.show_tray and not self.tray.isVisible():
            self.tray.show()
        elif not self.settings.show_tray and self.tray.isVisible():
            self.tray.hide()

    def _apply_startup_registry(self, enabled: bool):
        """Write/remove Clyro from the Windows HKCU Run registry key."""
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enabled:
                # Use the actual frozen exe path if bundled, otherwise the Python interpreter
                exe = sys.executable
                winreg.SetValueEx(key, "Clyro", 0, winreg.REG_SZ, f'"{exe}"')
                logger.info("Clyro added to startup registry.")
            else:
                try:
                    winreg.DeleteValue(key, "Clyro")
                    logger.info("Clyro removed from startup registry.")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            logger.warning(f"Failed to update startup registry: {e}")

    def _warn_missing_tools(self):
        """Show a tray balloon if any critical external tool is not found."""
        if not self._handlers_ready:
            return
        missing = []
        if not self.tools.ffmpeg:
            missing.append("FFmpeg (video features disabled)")
        if not self.tools.ghostscript:
            missing.append("Ghostscript (PDF optimization disabled)")
        if missing and self.tray.isVisible():
            msg = "Missing tools: " + ", ".join(missing)
            self.tray.showMessage("Clyro \u2014 Tools Missing", msg, msecs=6000)
            
    def _cleanup_temp_files(self):
        """Delete stale Clyro temp files older than 1 hour."""
        max_age = 3600  # 1 hour in seconds
        now = time.time()
        patterns = ["_clyro_tmp_*", "_palette_*", "*.tmp.jpg", "*.tmp.png"]
        dirs_to_scan = [
            os.environ.get("TEMP", ""),
            os.path.join(os.environ.get("APPDATA", ""), "Clyro", "backups"),
        ]
        cleaned = 0
        for d in dirs_to_scan:
            if not d or not os.path.isdir(d):
                continue
            for pattern in patterns:
                for f in glob.glob(os.path.join(d, pattern)):
                    try:
                        if now - os.path.getmtime(f) > max_age:
                            os.unlink(f)
                            cleaned += 1
                    except Exception:
                        pass
        if cleaned:
            logger.debug(f"Temp cleanup: removed {cleaned} stale file(s)")

    @staticmethod
    def _kill_orphan_processes():
        """Kill any lingering child processes on app exit."""
        try:
            import psutil
            current = psutil.Process()
            children = current.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except Exception:
                    pass
        except ImportError:
            # psutil not available — use taskkill on Windows as fallback
            import subprocess
            try:
                pid = os.getpid()
                subprocess.call(
                    ['taskkill', '/F', '/T', '/PID', str(pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
            except Exception:
                pass
        except Exception:
            pass  # process already gone

    def _check_for_updates(self):
        """Spawns an async task to check for updates using the background thread."""
        try:
            import asyncio
            from clyro.updater import AutoUpdater
            
            # Note: We hardcode version to match pyproject.toml "0.1.0"
            updater = AutoUpdater(current_version="0.1.0")
            
            def _run_updater():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                update_info = loop.run_until_complete(updater.check_for_updates())
                if update_info:
                    logger.info(f"Update available to {update_info['version']}. Downloading...")
                    loop.run_until_complete(updater.download_and_install(update_info["download_url"]))
                loop.close()

            import threading
            t = threading.Thread(target=_run_updater, daemon=True)
            t.start()
        except Exception as e:
            logger.error(f"Updater failure: {e}")

    def quit(self):
        self.dropzone.quit()    # cancel in-flight downloads first
        if self.ipc:
            self.ipc.stop()
        if hasattr(self, '_cleanup_timer'):
            self._cleanup_timer.stop()
        self._kill_orphan_processes()
        self.store.save(self.settings)
        self.app.quit()
