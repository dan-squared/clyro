import sys
import platform

def is_windows() -> bool:
    return sys.platform == "win32"

def get_os_info() -> str:
    return f"{platform.system()} {platform.release()}"
