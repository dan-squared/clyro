# -*- mode: python ; coding: utf-8 -*-
import os

project_root = os.path.abspath(os.path.dirname(os.getcwd()))
# If running from project root, os.getcwd() is the project root.
# build_release.py runs PyInstaller from PROJECT_ROOT.
project_root = os.getcwd()

a = Analysis(
    ['src/clyro/main.py'],
    pathex=[],
    binaries=[
        (os.path.join(project_root, 'bin', 'ffmpeg.exe'),   'bin'),
        (os.path.join(project_root, 'bin', 'ffprobe.exe'),  'bin'),
        (os.path.join(project_root, 'bin', 'gswin64c.exe'), 'bin'),
        (os.path.join(project_root, 'bin', 'gsdll64.dll'),  'bin'),
        (os.path.join(project_root, 'bin', 'pngquant.exe'), 'bin'),
        (os.path.join(project_root, 'bin', 'gifsicle.exe'), 'bin'),
        (os.path.join(project_root, 'bin', 'jpegoptim.exe'), 'bin'),
        (os.path.join(project_root, 'bin', 'gs_lib'),      'bin/gs_lib'),
        (os.path.join(project_root, 'bin', 'gs_resource'),  'bin/gs_resource'),
    ],
    datas=[(os.path.join(project_root, 'src/clyro/assets'), 'clyro/assets')],
    hiddenimports=['mozjpeg_lossless_optimization', 'cffi', 'pycparser', 'pdf2docx', 'pdf2docx.converter', 'docx', 'fitz'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # PyQt6 modules not used
        'PyQt6.QtSql', 'PyQt6.QtNetwork', 'PyQt6.QtQml', 'PyQt6.QtQuick',
        'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtBluetooth', 'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtSensors', 'PyQt6.QtSerialPort', 'PyQt6.QtLocation',
        'PyQt6.QtPositioning', 'PyQt6.QtTest', 'PyQt6.QtXml',
        'PyQt6.Qt3DCore', 'PyQt6.Qt3DInput', 'PyQt6.Qt3DLogic', 'PyQt6.Qt3DRender',
        # Dev / test tools (safe to exclude)
        'tkinter', 'unittest', 'test',
        # Heavy scientific libs (not used by Clyro)
        'matplotlib', 'scipy', 'pandas', 'IPython',
        # Unused stdlib modules (keeping only core safe ones)
        'turtle', 'curses', 'readline',
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Clyro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'python3*.dll', 'Qt6*.dll', 'gsdll64.dll'],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join(project_root, 'src/clyro/assets/icons/app/256.ico')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'python3*.dll', 'Qt6*.dll', 'gsdll64.dll'],
    name='Clyro',
)

