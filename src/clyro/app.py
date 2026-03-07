import sys
import logging
import atexit
import os
import glob
import time
import webbrowser
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from clyro import __version__
# Lightweight config — no heavy deps
from clyro.config.store import SettingsStore
from clyro.ui.dropzone import DropzoneWindow
from clyro.ui.global_shortcuts import GlobalHotkeyManager
from clyro.ui.tray import TrayIcon
from clyro.ui.theme import Theme

# Heavy modules imported lazily inside methods:
#   clyro.core.tools, clyro.core.dispatcher, clyro.core.optimize,
#   clyro.core.convert, clyro.core.image, clyro.core.video,
#   clyro.core.pdf, clyro.ipc.server, clyro.updater, winreg

logger = logging.getLogger(__name__)

class AppManager(QObject):
    update_check_completed = pyqtSignal(object, bool)
    update_check_failed = pyqtSignal(str, bool)
    update_install_failed = pyqtSignal(str, bool)
    update_download_ready = pyqtSignal(object, str, bool)

    def __init__(self, app: QApplication, icon: QIcon | None = None):
        super().__init__()
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
        self._update_check_in_flight = False
        self._update_install_in_flight = False
        self._last_update_info: dict | None = None
        self._pending_update_info: dict | None = None
        self._pending_update_installer: str | None = None
        self._install_update_on_quit = False
        self.update_check_completed.connect(self._handle_update_check_result)
        self.update_check_failed.connect(self._handle_update_check_error)
        self.update_install_failed.connect(self._handle_update_install_error)
        self.update_download_ready.connect(self._handle_update_download_ready)
        self.shortcut_manager = GlobalHotkeyManager(self.app)
        self.app.aboutToQuit.connect(self.shortcut_manager.unregister_all)
        
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
        self._apply_shortcuts()
        self._apply_surface_visibility()
        
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
            self.dropzone.reveal()
            
    def show_dropzone(self):
        self.dropzone.reveal()

    def show_settings(self):
        self._ensure_handlers()  # need tools for settings page
        if not self.settings_window:
            from clyro.ui.settings_window import SettingsWindow
            self.settings_window = SettingsWindow(self.settings, self.store, self.tools, self)
            # Re-read settings instance changes when closed
            self.settings_window.settings_saved.connect(self._on_settings_saved)

        if (
            self._last_update_info
            and not self.settings.auto_update_enabled
            and self.settings.skipped_update_version == self._last_update_info.get("version")
        ):
            self.settings_window.set_update_action(visible=False)
        elif self._pending_update_installer and self._pending_update_info:
            self.settings_window.set_update_status(
                f"Version {self._pending_update_info['version']} is ready to install.",
                "success",
            )
            self.settings_window.set_update_action("Install Now", enabled=True, visible=True)
        elif self._update_install_in_flight and self._last_update_info:
            self.settings_window.set_update_status(
                f"Downloading update {self._last_update_info['version']}...",
                "warning",
            )
            self.settings_window.set_update_action("Downloading...", enabled=False, visible=True)
        elif self._last_update_info:
            self.settings_window.set_update_status(
                f"Version {self._last_update_info['version']} is available.",
                "warning",
            )
            self.settings_window.set_update_action("Update Now", enabled=True, visible=True)
        else:
            self.settings_window.set_update_action(visible=False)
            
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
        i_i = ImageToImageHandler(self.settings, self.tools)
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
        self._apply_shortcuts()
        self._apply_surface_visibility()
        if self.settings_window:
            self.settings_window.refresh_status()

    def _apply_shortcuts(self):
        self.shortcut_manager.sync(
            {
                "toggle_dropzone": (self.settings.shortcut_toggle_dropzone, self.toggle_dropzone),
            }
        )

    def _apply_surface_visibility(self):
        # Never allow the app to hide both its tray surface and dropzone.
        show_tray = self.settings.show_tray
        show_dropzone = self.settings.dropzone_enabled or not show_tray

        if show_tray and not self.tray.isVisible():
            self.tray.show()
        elif not show_tray and self.tray.isVisible():
            self.tray.hide()

        if show_dropzone:
            self.dropzone.show()
        else:
            self.dropzone.hide()

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
        if self.settings_window:
            self.settings_window.refresh_status()
            
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

    def request_manual_update_check(self):
        self._check_for_updates(manual=True)

    def trigger_update_now(self):
        if self._pending_update_installer:
            self._install_pending_update(now=True)
            return

        if self._last_update_info and self._last_update_info.get("download_url"):
            self._start_update_download(self._last_update_info, manual=True)
            return

        if self._last_update_info and self._last_update_info.get("release_url"):
            webbrowser.open(self._last_update_info["release_url"])

    def _set_update_status_text(self, message: str, tone: str = "muted"):
        if self.settings_window:
            self.settings_window.set_update_status(message, tone)

    def _set_update_action(self, label: str | None = None, *, enabled: bool = True, visible: bool = True):
        if self.settings_window:
            self.settings_window.set_update_action(label, enabled=enabled, visible=visible)

    def _check_for_updates(self, manual: bool = False):
        """Spawns an async task to check for updates using the background thread."""
        if self._update_check_in_flight:
            if manual:
                self._set_update_status_text("Already checking for updates…", "muted")
            return

        try:
            import asyncio
            import threading
            from clyro.updater import AutoUpdater

            self._update_check_in_flight = True
            self._set_update_status_text("Checking for updates…", "muted")
            updater = AutoUpdater(current_version=__version__)

            def _run_updater():
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    update_info = loop.run_until_complete(updater.check_for_updates())
                    self.update_check_completed.emit(update_info, manual)
                except Exception as exc:
                    self.update_check_failed.emit(str(exc), manual)
                finally:
                    loop.close()

            t = threading.Thread(target=_run_updater, daemon=True)
            t.start()
        except Exception as e:
            self._update_check_in_flight = False
            logger.error(f"Updater failure: {e}")
            if manual:
                QMessageBox.warning(self.settings_window or self.dropzone, "Clyro", f"Update check failed.\n\n{e}")

    def _handle_update_check_result(self, update_info, manual: bool):
        self._update_check_in_flight = False
        self._last_update_info = update_info

        if not update_info:
            self._set_update_status_text("You are up to date.", "success")
            self._set_update_action(visible=False)
            if manual:
                QMessageBox.information(self.settings_window or self.dropzone, "Clyro", "You are already on the latest version.")
            return

        version = update_info["version"]
        self._set_update_status_text(f"Version {version} is available.", "warning")
        self._set_update_action("Update Now", enabled=True, visible=True)

        if not manual and not self.settings.auto_update_enabled and self.settings.skipped_update_version == version:
            logger.info("Update %s was skipped previously; suppressing automatic dialog.", version)
            self._set_update_action(visible=False)
            return

        if self._pending_update_info and self._pending_update_info.get("version") == version and self._pending_update_installer:
            self._set_update_status_text(f"Version {version} is ready to install.", "success")
            self._set_update_action("Install Now", enabled=True, visible=True)
            if not manual and self.settings.auto_update_enabled:
                self._prompt_update_ready(update_info)
            return

        if self.settings.auto_update_enabled and not manual and update_info.get("download_url"):
            logger.info("Update available to %s. Starting background download.", version)
            self._start_update_download(update_info, manual=False)
            return

        logger.info("Update available to %s. Waiting for user action.", version)
        self._show_update_dialog(update_info, manual=manual)

    def _handle_update_check_error(self, message: str, manual: bool):
        self._update_check_in_flight = False
        logger.error("Updater failure: %s", message)
        self._set_update_status_text("Update check failed.", "error")
        if manual:
            QMessageBox.warning(self.settings_window or self.dropzone, "Clyro", f"Update check failed.\n\n{message}")

    def _start_update_download(self, update_info: dict, manual: bool):
        if self._update_install_in_flight:
            self._set_update_action("Downloading...", enabled=False, visible=True)
            if manual:
                QMessageBox.information(self.settings_window or self.dropzone, "Clyro", "An update download is already in progress.")
            return

        try:
            import asyncio
            import threading
            from clyro.updater import AutoUpdater

            self._update_install_in_flight = True
            self.settings.skipped_update_version = None
            self.store.save(self.settings)
            self._set_update_action("Downloading...", enabled=False, visible=True)

            version = update_info["version"]
            if update_info.get("sha256"):
                self._set_update_status_text(f"Downloading update {version}...", "warning")
            else:
                self._set_update_status_text(f"Downloading update {version} without published checksum...", "warning")

            if self.tray.isVisible():
                self.tray.showMessage("Clyro update", f"Downloading version {version}.", msecs=5000)

            updater = AutoUpdater(current_version=__version__)

            def _run_download():
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    installer_path = loop.run_until_complete(
                        updater.download_installer(
                            update_info["download_url"],
                            update_info.get("sha256"),
                        )
                    )
                    self.update_download_ready.emit(update_info, installer_path, manual)
                except Exception as exc:
                    self.update_install_failed.emit(str(exc), manual)
                finally:
                    loop.close()

            threading.Thread(target=_run_download, daemon=True).start()
        except Exception as exc:
            self._update_install_in_flight = False
            logger.error("Failed to start update download: %s", exc)
            if manual:
                QMessageBox.warning(self.settings_window or self.dropzone, "Clyro", f"Update download failed.\n\n{exc}")

    def _handle_update_download_ready(self, update_info, installer_path: str, manual: bool):
        self._update_install_in_flight = False
        self._pending_update_info = update_info
        self._pending_update_installer = installer_path
        self._install_update_on_quit = False
        self._set_update_status_text(f"Version {update_info['version']} is ready to install.", "success")
        self._set_update_action("Install Now", enabled=True, visible=True)
        if self.tray.isVisible():
            self.tray.showMessage("Clyro update", f"Version {update_info['version']} is ready to install.", msecs=6000)
        self._prompt_update_ready(update_info)

    def _prompt_update_ready(self, update_info: dict):
        from clyro.ui.update_dialog import UpdateReadyDialog

        if not self._pending_update_installer:
            return

        parent = self.settings_window if self.settings_window and self.settings_window.isVisible() else self.dropzone
        dialog = UpdateReadyDialog(update_info["version"], parent=parent)
        dialog.exec()

        if dialog.choice == "now":
            self._install_pending_update(now=True)
            return

        self._install_update_on_quit = True
        self._set_update_status_text(
            f"Version {update_info['version']} will install when Clyro closes.",
            "muted",
        )

    def _handle_update_install_error(self, message: str, manual: bool):
        self._update_install_in_flight = False
        logger.error("Update transfer failed: %s", message)
        self._set_update_status_text("Update failed.", "error")
        if self._last_update_info:
            self._set_update_action("Update Now", enabled=True, visible=True)
        if self.tray.isVisible():
            self.tray.showMessage("Clyro update", "Automatic update failed.", msecs=5000)
        if manual:
            QMessageBox.warning(self.settings_window or self.dropzone, "Clyro", f"Update install failed.\n\n{message}")

    def _install_pending_update(self, *, now: bool):
        if not self._pending_update_installer:
            return

        try:
            from clyro.updater import AutoUpdater

            installer_path = self._pending_update_installer
            version = self._pending_update_info["version"] if self._pending_update_info else "update"
            self._pending_update_installer = None
            self._pending_update_info = None
            self._install_update_on_quit = False
            self._set_update_action(visible=False)
            self._set_update_status_text(f"Installing version {version}...", "warning")
            AutoUpdater.launch_installer(installer_path)
            if self.tray.isVisible():
                self.tray.showMessage("Clyro update", f"Installing version {version}.", msecs=5000)
            if now:
                self.quit()
        except Exception as exc:
            logger.error("Failed to launch installer: %s", exc)
            self._set_update_status_text("Failed to launch installer.", "error")
            if self._last_update_info:
                self._set_update_action("Install Now", enabled=True, visible=True)
            QMessageBox.warning(self.settings_window or self.dropzone, "Clyro", f"Failed to launch installer.\n\n{exc}")

    def _show_update_dialog(self, update_info: dict, *, manual: bool = False):
        from clyro.ui.update_dialog import UpdateDialog

        parent = self.settings_window if self.settings_window and self.settings_window.isVisible() else self.dropzone
        dialog = UpdateDialog(__version__, update_info, parent=parent)
        dialog.exec()

        if dialog.choice == "skip":
            self.settings.skipped_update_version = update_info["version"]
            self.store.save(self.settings)
            self._set_update_status_text(f"Version {update_info['version']} will be skipped.", "muted")
            self._set_update_action(visible=False)
            return

        if dialog.choice == "install":
            self.settings.skipped_update_version = None
            self.store.save(self.settings)
            if update_info.get("download_url"):
                self._start_update_download(update_info, True)
                return

            target = update_info.get("release_url")
            if target:
                webbrowser.open(target)
                self._set_update_status_text(f"Opened release page for {update_info['version']}.", "success")
            elif self.tray.isVisible():
                self.tray.showMessage("Clyro update available", "Release page could not be opened.", msecs=5000)

    def quit(self):
        if self._install_update_on_quit and self._pending_update_installer:
            self._install_pending_update(now=False)
        self.shortcut_manager.unregister_all()
        self.dropzone.quit()    # cancel in-flight downloads first
        if self.ipc:
            self.ipc.stop()
        if hasattr(self, '_cleanup_timer'):
            self._cleanup_timer.stop()
        self._kill_orphan_processes()
        self.store.save(self.settings)
        self.app.quit()
