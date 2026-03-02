import PyInstaller.__main__
from pathlib import Path
import os
import sys

def build():
    # Ensure we are running from project root
    project_root = Path(__file__).resolve().parent
    if project_root.name == "clyro":
        project_root = project_root.parent.parent
        
    os.chdir(project_root)
    
    # 1. Base command, pointing to the CLI entry or main app entry
    cmd = [
        "src/clyro/main.py",
        "--name=Clyro",
        "--noconsole",          # Hide console window
        "--clean",              # Clean cache before build
        "--noconfirm",          # Overwrite output dir
        "--hidden-import=mozjpeg_lossless_optimization",
        "--hidden-import=cffi",
        "--hidden-import=pycparser",
        "--noupx",              # Temporarily turning off UPX here to ensure stable FFmpeg/GS DLLs on first try
    ]
    
    # 2. Add application UI assets
    assets_dir = project_root / "src" / "clyro" / "assets"
    if assets_dir.exists():
        # format is src;dest for Windows
        cmd.append(f"--add-data={assets_dir};clyro/assets")
        
    # 3. Add heavy binaries
    bin_dir = project_root / "bin"
    if bin_dir.exists():
        cmd.append(f"--add-binary={bin_dir};bin")
        
    # 4. Icon
    icon_path = assets_dir / "icons" / "app" / "256.ico"
    if icon_path.exists():
        cmd.append(f"--icon={icon_path}")
        
    # 5. PyQt6 Optimizations (Excluding massive unused modules)
    excludes = [
        "PyQt6.QtSql",
        "PyQt6.QtNetwork",
        "PyQt6.QtQml",
        "PyQt6.QtQuick",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtBluetooth",
        "PyQt6.QtMultimedia",
        "PyQt6.QtMultimediaWidgets",
        "PyQt6.QtSensors",
        "PyQt6.QtSerialPort",
        "PyQt6.QtLocation",
        "PyQt6.QtPositioning",
        "PyQt6.QtTest",
        "PyQt6.QtXml",
        "PyQt6.Qt3DCore",
        "PyQt6.Qt3DInput",
        "PyQt6.Qt3DLogic",
        "PyQt6.Qt3DRender",
        "tkinter",
        "unittest"
    ]
    
    for module in excludes:
        cmd.append(f"--exclude-module={module}")
        
    print("Running PyInstaller with args:")
    for c in cmd:
        print(f"  {c}")
        
    PyInstaller.__main__.run(cmd)

if __name__ == "__main__":
    build()
