# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\clyro\\main.py'],
    pathex=[],
    binaries=[
        # Root bin: ffmpeg, ffprobe, gswin64c, gsdll64, pngquant
        ('C:\\Users\\hp\\Downloads\\Projects\\Clyro\\bin\\ffmpeg.exe',   'bin'),
        ('C:\\Users\\hp\\Downloads\\Projects\\Clyro\\bin\\ffprobe.exe',  'bin'),
        ('C:\\Users\\hp\\Downloads\\Projects\\Clyro\\bin\\gswin64c.exe', 'bin'),
        ('C:\\Users\\hp\\Downloads\\Projects\\Clyro\\bin\\gsdll64.dll',  'bin'),
        ('C:\\Users\\hp\\Downloads\\Projects\\Clyro\\bin\\pngquant.exe', 'bin'),
        ('C:\\Users\\hp\\Downloads\\Projects\\Clyro\\bin\\gifsicle.exe', 'bin'),
        ('C:\\Users\\hp\\Downloads\\Projects\\Clyro\\bin\\jpegoptim.exe', 'bin'),
        # Ghostscript runtime resources (must be addressable via GS_LIB)
        ('C:\\Users\\hp\\Downloads\\Projects\\Clyro\\bin\\gs_lib',      'bin\\gs_lib'),
        ('C:\\Users\\hp\\Downloads\\Projects\\Clyro\\bin\\gs_resource',  'bin\\gs_resource'),
    ],
    datas=[('C:\\Users\\hp\\Downloads\\Projects\\Clyro\\src\\clyro\\assets', 'clyro/assets')],
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
    optimize=2,   # strip docstrings + asserts → smaller .pyc, faster imports
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
    icon=['C:\\Users\\hp\\Downloads\\Projects\\Clyro\\src\\clyro\\assets\\icons\\app\\256.ico'],
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
