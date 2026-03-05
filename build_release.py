"""
Clyro Release Build Script
===========================
Downloads all external binaries, runs PyInstaller, then Inno Setup.

Usage:
    python build_release.py                    # Full build
    python build_release.py --skip-download    # Skip binary downloads (if bin/ already populated)
    python build_release.py --skip-inno        # Skip Inno Setup step
    python build_release.py --download-only    # Only download binaries, skip build steps
"""

import io
import os
import sys
import ssl
import shutil
import zipfile
import urllib.request
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BIN_DIR      = PROJECT_ROOT / "bin"
DIST_DIR     = PROJECT_ROOT / "dist"
SPEC_FILE    = PROJECT_ROOT / "Clyro.spec"
ISS_FILE     = PROJECT_ROOT / "installer.iss"

# -- Verified Download URLs (all have Windows x64 .exe binaries) ------------
# FFmpeg essentials build (.zip, ~101 MB) — gyan.dev, well-known FFmpeg distributor
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

# pngquant — official Windows build from pngquant.org
PNGQUANT_URL = "https://pngquant.org/pngquant-windows.zip"

# gifsicle 1.95 win64 — Jernej Simoncic's well-known Windows port
GIFSICLE_URL = "https://eternallybored.org/misc/gifsicle/releases/gifsicle-1.95-win64.zip"

# jpegoptim 1.5.6 x64 Windows — official release from tjko on GitHub
JPEGOPTIM_URL = "https://github.com/tjko/jpegoptim/releases/download/v1.5.6/jpegoptim-1.5.6-x64-windows.zip"


def _make_ssl_context():
    """Create a permissive SSL context (some build servers have cert issues)."""
    ctx = ssl.create_default_context()
    # Fall back to unverified if the default context fails (corporate proxies, etc.)
    return ctx


def download_file(url: str, dest: Path, label: str = "") -> bool:
    """Download a file with progress. Returns True on success."""
    label = label or dest.name
    print(f"  -> Downloading {label}...")
    print(f"    URL: {url}")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Clyro-Build/1.0"})
        ctx = _make_ssl_context()
        with urllib.request.urlopen(req, timeout=300, context=ctx) as resp:
            data = resp.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        mb = len(data) / (1024 * 1024)
        print(f"    [OK] Downloaded ({mb:.1f} MB)")
        return True
    except Exception as e:
        print(f"    [FAIL] Download failed: {e}")
        # Try again without SSL verification as fallback
        try:
            print(f"    ... Retrying without SSL verification...")
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=300, context=ctx) as resp:
                data = resp.read()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            mb = len(data) / (1024 * 1024)
            print(f"    [OK] Downloaded on retry ({mb:.1f} MB)")
            return True
        except Exception as e2:
            print(f"    [FAIL] Retry also failed: {e2}")
            print(f"    -> Please download manually from: {url}")
            print(f"    -> Place it at: {dest}")
            return False


def extract_zip(zip_path: Path, extract_to: Path):
    """Extract a zip file."""
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(extract_to)


def _cleanup_tmp():
    """Remove tmp_downloads if it exists."""
    tmp = PROJECT_ROOT / "tmp_downloads"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)


# -- Individual tool downloaders --------------------------------------------

def download_ffmpeg() -> bool:
    """Download and extract ffmpeg + ffprobe to bin/."""
    if (BIN_DIR / "ffmpeg.exe").exists() and (BIN_DIR / "ffprobe.exe").exists():
        print("  [OK] ffmpeg + ffprobe already present")
        return True

    tmp = PROJECT_ROOT / "tmp_downloads"
    tmp.mkdir(exist_ok=True)
    zip_path = tmp / "ffmpeg.zip"

    if not download_file(FFMPEG_URL, zip_path, "FFmpeg (~101 MB, may take a few minutes)"):
        return False

    print("  ... Extracting FFmpeg...")
    try:
        extract_zip(zip_path, tmp)
    except Exception as e:
        print(f"    [FAIL] Extraction failed: {e}")
        return False

    # Find the bin folder inside the extracted directory (e.g., ffmpeg-7.1.1-essentials_build/bin/)
    found = False
    for d in tmp.iterdir():
        if d.is_dir() and d.name.startswith("ffmpeg"):
            ffmpeg_bin = d / "bin"
            if ffmpeg_bin.exists():
                BIN_DIR.mkdir(exist_ok=True)
                for exe_name in ["ffmpeg.exe", "ffprobe.exe"]:
                    src = ffmpeg_bin / exe_name
                    if src.exists():
                        shutil.copy2(src, BIN_DIR / exe_name)
                        print(f"    [OK] {exe_name} -> bin/")
                    else:
                        print(f"    [FAIL] {exe_name} not found in extracted archive")
                found = True
                break

    if not found:
        print("    [FAIL] Could not find ffmpeg binaries in the extracted archive")
        return False

    shutil.rmtree(tmp, ignore_errors=True)
    return (BIN_DIR / "ffmpeg.exe").exists() and (BIN_DIR / "ffprobe.exe").exists()


def download_pngquant() -> bool:
    """Download pngquant to bin/."""
    if (BIN_DIR / "pngquant.exe").exists():
        print("  [OK] pngquant already present")
        return True

    tmp = PROJECT_ROOT / "tmp_downloads"
    tmp.mkdir(exist_ok=True)
    zip_path = tmp / "pngquant.zip"

    if not download_file(PNGQUANT_URL, zip_path, "pngquant"):
        return False

    print("  ... Extracting pngquant...")
    extract_zip(zip_path, tmp)

    BIN_DIR.mkdir(exist_ok=True)
    for exe in tmp.rglob("pngquant.exe"):
        shutil.copy2(exe, BIN_DIR / "pngquant.exe")
        print("    [OK] pngquant.exe -> bin/")
        break

    shutil.rmtree(tmp, ignore_errors=True)
    return (BIN_DIR / "pngquant.exe").exists()


def download_gifsicle() -> bool:
    """Download gifsicle to bin/."""
    if (BIN_DIR / "gifsicle.exe").exists():
        print("  [OK] gifsicle already present")
        return True

    tmp = PROJECT_ROOT / "tmp_downloads"
    tmp.mkdir(exist_ok=True)
    zip_path = tmp / "gifsicle.zip"

    if not download_file(GIFSICLE_URL, zip_path, "gifsicle"):
        return False

    print("  ... Extracting gifsicle...")
    extract_zip(zip_path, tmp)

    BIN_DIR.mkdir(exist_ok=True)
    for exe in tmp.rglob("gifsicle.exe"):
        shutil.copy2(exe, BIN_DIR / "gifsicle.exe")
        print("    [OK] gifsicle.exe -> bin/")
        break

    shutil.rmtree(tmp, ignore_errors=True)
    return (BIN_DIR / "gifsicle.exe").exists()


def download_jpegoptim() -> bool:
    """Download jpegoptim to bin/."""
    if (BIN_DIR / "jpegoptim.exe").exists():
        print("  [OK] jpegoptim already present")
        return True

    tmp = PROJECT_ROOT / "tmp_downloads"
    tmp.mkdir(exist_ok=True)
    zip_path = tmp / "jpegoptim.zip"

    if not download_file(JPEGOPTIM_URL, zip_path, "jpegoptim"):
        return False

    print("  ... Extracting jpegoptim...")
    extract_zip(zip_path, tmp)

    BIN_DIR.mkdir(exist_ok=True)
    # jpegoptim release zips may contain the exe at root or in a subfolder
    for exe in tmp.rglob("jpegoptim.exe"):
        shutil.copy2(exe, BIN_DIR / "jpegoptim.exe")
        print("    [OK] jpegoptim.exe -> bin/")
        break
    else:
        # If no .exe found, list what was extracted so the user can investigate
        print("    [FAIL] jpegoptim.exe not found in archive. Contents:")
        for f in tmp.rglob("*"):
            if f.is_file():
                print(f"      {f.relative_to(tmp)}")
        shutil.rmtree(tmp, ignore_errors=True)
        return False

    # Also copy any DLLs that jpegoptim may depend on (e.g., libjpeg)
    for dll in tmp.rglob("*.dll"):
        shutil.copy2(dll, BIN_DIR / dll.name)
        print(f"    [OK] {dll.name} -> bin/ (jpegoptim dependency)")

    shutil.rmtree(tmp, ignore_errors=True)
    return (BIN_DIR / "jpegoptim.exe").exists()


def setup_ghostscript() -> bool:
    """Find and copy Ghostscript from an existing system installation to bin/."""
    gs_exe = BIN_DIR / "gswin64c.exe"
    gs_dll = BIN_DIR / "gsdll64.dll"
    gs_lib = BIN_DIR / "gs_lib"
    gs_res = BIN_DIR / "gs_resource"

    if gs_exe.exists() and gs_dll.exists() and gs_lib.exists() and gs_res.exists():
        print("  [OK] Ghostscript already present")
        return True

    # Try to find an existing Ghostscript installation
    gs_install_dirs = [
        Path("C:/Program Files/gs"),
        Path("C:/Program Files (x86)/gs"),
    ]

    for gs_root in gs_install_dirs:
        if not gs_root.exists():
            continue
        for version_dir in sorted(gs_root.iterdir(), reverse=True):
            gs_bin_dir = version_dir / "bin"
            gs_lib_dir = version_dir / "lib"
            gs_res_dir = version_dir / "Resource"

            if (gs_bin_dir / "gswin64c.exe").exists():
                print(f"  [OK] Found Ghostscript at: {version_dir}")
                BIN_DIR.mkdir(exist_ok=True)

                if not gs_exe.exists():
                    shutil.copy2(gs_bin_dir / "gswin64c.exe", gs_exe)
                    print("    [OK] gswin64c.exe -> bin/")
                if not gs_dll.exists() and (gs_bin_dir / "gsdll64.dll").exists():
                    shutil.copy2(gs_bin_dir / "gsdll64.dll", gs_dll)
                    print("    [OK] gsdll64.dll -> bin/")
                if not gs_lib.exists() and gs_lib_dir.exists():
                    shutil.copytree(gs_lib_dir, gs_lib)
                    print("    [OK] gs_lib/ copied")
                if not gs_res.exists() and gs_res_dir.exists():
                    shutil.copytree(gs_res_dir, gs_res)
                    print("    [OK] gs_resource/ copied")

                return gs_exe.exists() and gs_dll.exists()

    print("  [WARN]  Ghostscript not found on this system.")
    print("     To enable PDF optimization, install Ghostscript:")
    print("       https://ghostscript.com/releases/gsdnld.html")
    print("     Then re-run this script.")
    return False


def download_all_binaries() -> bool:
    """Download all external tools to bin/. Returns True only if ALL succeeded."""
    print("\n--------------------------------------------------")
    print("  Step 1: Downloading External Binaries")
    print("--------------------------------------------------\n")

    BIN_DIR.mkdir(exist_ok=True)

    results = {}
    results["FFmpeg"]      = download_ffmpeg()
    print()
    results["pngquant"]    = download_pngquant()
    print()
    results["gifsicle"]    = download_gifsicle()
    print()
    results["jpegoptim"]   = download_jpegoptim()
    print()
    results["Ghostscript"] = setup_ghostscript()

    # Summary
    print("\n-- Binary Status --")
    all_ok = True
    for name, ok in results.items():
        status = "[OK]" if ok else "[FAIL] MISSING"
        print(f"  {status}  {name}")
        if not ok:
            all_ok = False

    # Detailed file check
    print("\n-- File Check --")
    required_files = [
        "ffmpeg.exe", "ffprobe.exe",
        "pngquant.exe", "gifsicle.exe", "jpegoptim.exe",
        "gswin64c.exe", "gsdll64.dll",
    ]
    required_dirs = ["gs_lib", "gs_resource"]

    for name in required_files:
        path = BIN_DIR / name
        status = "[OK]" if path.exists() else "[FAIL]"
        print(f"  {status}  {name}")

    for name in required_dirs:
        path = BIN_DIR / name
        status = "[OK]" if path.exists() else "[FAIL]"
        print(f"  {status}  {name}/")

    if not all_ok:
        print("\n  [WARN]  Some binaries are missing!")
        print("     The build will NOT proceed until all binaries are present.")
        print("     Please download the missing ones manually and place them in:")
        print(f"     {BIN_DIR}")

    return all_ok


def run_pyinstaller() -> bool:
    """Run PyInstaller using Clyro.spec."""
    print("\n--------------------------------------------------")
    print("  Step 2: Building with PyInstaller")
    print("--------------------------------------------------\n")

    if not SPEC_FILE.exists():
        print(f"  [FAIL] Spec file not found: {SPEC_FILE}")
        return False

    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(SPEC_FILE)]
    print(f"  Running: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print("\n  [FAIL] PyInstaller build failed!")
        return False

    exe_path = DIST_DIR / "Clyro" / "Clyro.exe"
    if exe_path.exists():
        mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n  [OK] Build successful: {exe_path} ({mb:.1f} MB)")
        # Show total dist size
        total = sum(f.stat().st_size for f in (DIST_DIR / "Clyro").rglob("*") if f.is_file())
        print(f"  [OK] Total dist/Clyro/ size: {total / (1024*1024):.0f} MB")
        return True
    else:
        print(f"\n  [FAIL] Expected output not found: {exe_path}")
        return False


def run_inno_setup() -> bool:
    """Compile the Inno Setup script to produce ClyroSetup.exe."""
    print("\n--------------------------------------------------")
    print("  Step 3: Creating Installer with Inno Setup")
    print("--------------------------------------------------\n")

    if not ISS_FILE.exists():
        print(f"  [FAIL] ISS file not found: {ISS_FILE}")
        return False

    # Find Inno Setup compiler
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    iscc_paths = [
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files (x86)/Inno Setup 5/ISCC.exe"),
        Path(local_app_data) / "Programs/Inno Setup 6/ISCC.exe",
    ]

    iscc = None
    for p in iscc_paths:
        if p.exists():
            iscc = p
            break

    if iscc is None:
        iscc_which = shutil.which("ISCC")
        if iscc_which:
            iscc = Path(iscc_which)

    if iscc is None:
        print("  [FAIL] Inno Setup compiler (ISCC.exe) not found!")
        print("    Install Inno Setup 6 from: https://jrsoftware.org/isinfo.php")
        print("    Or add ISCC.exe to your PATH.")
        return False

    print(f"  Using: {iscc}")
    cmd = [str(iscc), str(ISS_FILE)]
    print(f"  Running: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print("\n  [FAIL] Inno Setup compilation failed!")
        return False

    setup_path = DIST_DIR / "ClyroSetup.exe"
    if setup_path.exists():
        mb = setup_path.stat().st_size / (1024 * 1024)
        print(f"\n  [OK] Installer created: {setup_path} ({mb:.1f} MB)")
        return True
    else:
        print(f"\n  [FAIL] Expected output not found: {setup_path}")
        return False


def main():
    print("==================================================")
    print("  Clyro Release Build Script")
    print("==================================================")

    skip_download  = "--skip-download" in sys.argv
    skip_inno      = "--skip-inno" in sys.argv
    download_only  = "--download-only" in sys.argv

    # Step 1: Download binaries
    if not skip_download:
        all_present = download_all_binaries()
        if not all_present and not download_only:
            print("\n  [FAIL] Cannot proceed with build — missing binaries.")
            print("    Fix the missing downloads above, then re-run.")
            sys.exit(1)
    else:
        print("\n  ... Skipping binary downloads (--skip-download)")

    if download_only:
        print("\n  Done (--download-only). Run again without that flag to build.")
        sys.exit(0)

    # Step 2: PyInstaller
    if not run_pyinstaller():
        print("\n  [FAIL] Build failed at PyInstaller step. Fix errors and retry.")
        sys.exit(1)

    # Step 3: Inno Setup
    if not skip_inno:
        if not run_inno_setup():
            print("\n  [WARN]  Installer creation failed, but dist/Clyro/ is still usable.")
            sys.exit(1)
    else:
        print("\n  ... Skipping Inno Setup (--skip-inno)")

    print("\n==================================================")
    print("  BUILD COMPLETE")
    print("==================================================")
    print("  Portable app:  dist/Clyro/Clyro.exe")
    if not skip_inno:
        print("  Installer:     dist/ClyroSetup.exe")
    print()


if __name__ == "__main__":
    main()
