import sys

def _check_vcruntime():
    """Check for VC++ runtime before anything else — PyQt6 needs it."""
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
    except ImportError as e:
        err = str(e).lower()
        if "dll" in err or "vcruntime" in err or "msvcp" in err or "not found" in err:
            # Show native Windows error — no PyQt6 available to show a dialog
            import ctypes
            msg = (
                "Clyro requires the Microsoft Visual C++ Redistributable to run.\n\n"
                "It appears to be missing on this system.\n\n"
                "Please download and install it from:\n"
                "https://aka.ms/vs/17/release/vc_redist.x64.exe\n\n"
                "After installing, restart Clyro."
            )
            ctypes.windll.user32.MessageBoxW(0, msg, "Clyro — Missing Dependency", 0x10)
            sys.exit(1)
        raise  # Re-raise if it's a different import error

if sys.platform == "win32":
    _check_vcruntime()

import logging
import logging.handlers
import http.client
import time
from PyQt6.QtWidgets import QApplication
import multiprocessing

from clyro.utils.paths import get_app_data_dir, resource_path
from clyro.app import AppManager
from PyQt6.QtGui import QIcon
import ctypes

def setup_logging():
    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.handlers.RotatingFileHandler(
                log_dir / "clyro.log",
                encoding="utf-8",
                maxBytes=2_000_000,
                backupCount=3,
            ),
            logging.StreamHandler(sys.stdout),
        ],
    )

def _install_crash_handler():
    """Ensure unhandled exceptions are written to the rotating log (invisible in .exe otherwise)."""
    import traceback
    _log = logging.getLogger("clyro.crash")

    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _log.critical(f"Unhandled exception:\n{msg}")

    sys.excepthook = _excepthook

def cleanup_stale_temp():
    """Remove partial/stale download files older than 24 hours."""
    temp_dir = get_app_data_dir() / "downloads"
    if not temp_dir.exists():
        return
    cutoff = time.time() - 86400  # 24 hours
    removed = 0
    for f in temp_dir.iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
                removed += 1
        except Exception:
            pass
    if removed:
        logging.getLogger(__name__).info(f"Cleaned up {removed} stale temp file(s) from {temp_dir}")

def check_single_instance():
    """Returns True if another instance is already running."""
    try:
        # Try to connect to existing instance's IPC server
        conn = http.client.HTTPConnection("localhost", 19847, timeout=1)
        conn.request("POST", "/show")
        resp = conn.getresponse()
        if resp.status == 200:
            return True
        return False
    except (OSError, ConnectionRefusedError, TimeoutError, http.client.HTTPException):
        return False

def main():
    multiprocessing.freeze_support()
    setup_logging()
    _install_crash_handler()
    cleanup_stale_temp()
    
    logger = logging.getLogger(__name__)
    
    if check_single_instance():
        # Exit quietly if another instance handled the show request
        sys.exit(0)
        
    logger.info("Starting Clyro...")

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("Clyro")
    
    # Ensure Windows Taskbar uses our custom AppUserModelID icon
    if sys.platform == "win32":
        try:
            myappid = u"dan.clyro.app.v1"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            logger.warning(f"Failed to set AppUserModelID: {e}")
            
    # Load the global application icon once to be passed into the AppManager
    icon_path = resource_path("clyro/assets/icons/app/256.ico")
    app_icon = None
    if icon_path.exists():
        app_icon = QIcon(str(icon_path))
    else:
        png_path = resource_path("clyro/assets/icons/app/PNG Icon.png")
        if png_path.exists():
            app_icon = QIcon(str(png_path))

    if app_icon:
        qt_app.setWindowIcon(app_icon)
    
    # Keep the application running in the background (for system tray support)
    qt_app.setQuitOnLastWindowClosed(False)
    
    AppManager(qt_app, app_icon)
    
    sys.exit(qt_app.exec())

if __name__ == "__main__":
    main()
