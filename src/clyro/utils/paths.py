import os
import sys
from pathlib import Path

def get_app_data_dir() -> Path:
    """Get the path to store application data (settings, logs, etc.)."""
    if sys.platform == "win32":
        path = os.getenv("APPDATA")
        if path:
            return Path(path) / "Clyro"
    
    # Fallback for local development or other platforms
    return Path.home() / ".clyro"

def get_temp_dir() -> Path:
    """Get a directory for temporary files."""
    import tempfile
    path = Path(tempfile.gettempdir()) / "clyro_temp"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_bundle_dir() -> Path:
    """Gets the base directory, whether running as an executable or as a script."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    # When running as script (src/clyro/utils/paths.py)
    # Parent 1: utils, Parent 2: clyro, Parent 3: src
    return Path(__file__).resolve().parent.parent.parent

def resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    return get_bundle_dir() / relative_path
