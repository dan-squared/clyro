"""
Clyro Release Build Script
==========================
Downloads verified external binaries, runs PyInstaller, then Inno Setup.

Usage:
    python build_release.py                    # Full build
    python build_release.py --skip-download    # Skip binary downloads (if bin/ already populated)
    python build_release.py --skip-inno        # Skip Inno Setup step
    python build_release.py --download-only    # Only download binaries, skip build steps
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BIN_DIR = PROJECT_ROOT / "bin"
DIST_DIR = PROJECT_ROOT / "dist"
SPEC_FILE = PROJECT_ROOT / "Clyro.spec"
ISS_FILE = PROJECT_ROOT / "installer.iss"
VERSION_FILE = PROJECT_ROOT / "src" / "clyro" / "__init__.py"
PYINSTALLER_CACHE_DIR = PROJECT_ROOT / ".pyinstaller_local"
PNGQUANT_GIT_URL = "https://github.com/kornelski/pngquant.git"
PNGQUANT_GIT_BRANCH = "msvc"

TOOL_DOWNLOADS = {
    "ffmpeg": {
        "label": "FFmpeg (~101 MB, may take a few minutes)",
        "url": "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.0.1-essentials_build.zip",
        "sha256": "e2aaeaa0fdbc397d4794828086424d4aaa2102cef1fb6874f6ffd29c0b88b673",
        "archive_name": "ffmpeg.zip",
    },
    "pngquant": {
        "label": "pngquant",
        "url": "https://pngquant.org/pngquant-windows.zip",
        "sha256": "bd0257aeeccfe446a4cd764927e26f8af6051796f28abed104307284107b120d",
        "archive_name": "pngquant.zip",
    },
    "gifsicle": {
        "label": "gifsicle",
        "url": "https://eternallybored.org/misc/gifsicle/releases/gifsicle-1.95-win64.zip",
        "sha256": "7e47dd0bfd5ee47f911464c57faeed89a8709a7625dd1c449b16579889539ee8",
        "archive_name": "gifsicle.zip",
    },
    "jpegoptim": {
        "label": "jpegoptim",
        "url": "https://github.com/tjko/jpegoptim/releases/download/v1.5.6/jpegoptim-1.5.6-x64-windows.zip",
        "sha256": "db2d8caee88f2665b772c4591cba223b8b729500b88266dc06d4bf79d28fe11a",
        "archive_name": "jpegoptim.zip",
    },
}


def get_project_version() -> str:
    match = re.search(r'__version__\s*=\s*"([^"]+)"', VERSION_FILE.read_text(encoding="utf-8"))
    if not match:
        raise RuntimeError(f"Could not determine project version from {VERSION_FILE}")
    return match.group(1)


def _sha256_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, dest: Path, *, label: str, expected_sha256: str) -> bool:
    """Download a file and verify its SHA-256 checksum."""
    print(f"  -> Downloading {label}...")
    print(f"    URL: {url}")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Clyro-Build/1.0"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = resp.read()
    except Exception as exc:
        print(f"    [FAIL] Download failed: {exc}")
        print(f"    -> Please download manually from: {url}")
        print(f"    -> Place it at: {dest}")
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)

    actual_sha256 = _sha256_for_file(dest)
    if actual_sha256.lower() != expected_sha256.lower():
        print("    [FAIL] Checksum mismatch!")
        print(f"    Expected: {expected_sha256}")
        print(f"    Actual:   {actual_sha256}")
        dest.unlink(missing_ok=True)
        return False

    mb = len(data) / (1024 * 1024)
    print(f"    [OK] Downloaded and verified ({mb:.1f} MB)")
    return True


def extract_zip(zip_path: Path, extract_to: Path):
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)


def _cleanup_tmp():
    tmp = PROJECT_ROOT / "tmp_downloads"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)


def _download_archive(tool_name: str) -> Path | None:
    manifest = TOOL_DOWNLOADS[tool_name]
    tmp = PROJECT_ROOT / "tmp_downloads"
    tmp.mkdir(exist_ok=True)
    archive_path = tmp / manifest["archive_name"]

    if not download_file(
        manifest["url"],
        archive_path,
        label=manifest["label"],
        expected_sha256=manifest["sha256"],
    ):
        return None
    return archive_path


def _run_command(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def download_ffmpeg() -> bool:
    if (BIN_DIR / "ffmpeg.exe").exists() and (BIN_DIR / "ffprobe.exe").exists():
        print("  [OK] ffmpeg + ffprobe already present")
        return True

    archive_path = _download_archive("ffmpeg")
    if archive_path is None:
        return False

    tmp = PROJECT_ROOT / "tmp_downloads"
    print("  ... Extracting FFmpeg...")
    try:
        extract_zip(archive_path, tmp)
    except Exception as exc:
        print(f"    [FAIL] Extraction failed: {exc}")
        return False

    found = False
    for extracted_dir in tmp.iterdir():
        if extracted_dir.is_dir() and extracted_dir.name.startswith("ffmpeg"):
            ffmpeg_bin = extracted_dir / "bin"
            if not ffmpeg_bin.exists():
                continue

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

    _cleanup_tmp()
    return (BIN_DIR / "ffmpeg.exe").exists() and (BIN_DIR / "ffprobe.exe").exists()


def download_pngquant() -> bool:
    if (BIN_DIR / "pngquant.exe").exists():
        print("  [OK] pngquant already present")
        return True

    archive_path = _download_archive("pngquant")
    if archive_path is not None:
        tmp = PROJECT_ROOT / "tmp_downloads"
        print("  ... Extracting pngquant...")
        try:
            extract_zip(archive_path, tmp)
        except Exception as exc:
            print(f"    [FAIL] Extraction failed: {exc}")
        else:
            BIN_DIR.mkdir(exist_ok=True)
            for exe in tmp.rglob("pngquant.exe"):
                shutil.copy2(exe, BIN_DIR / "pngquant.exe")
                print("    [OK] pngquant.exe -> bin/")
                _cleanup_tmp()
                return True
            print("    [FAIL] pngquant.exe not found in archive")

    print("  ... Falling back to Cargo build for pngquant (official Windows path)...")
    return build_pngquant()


def build_pngquant() -> bool:
    cargo = shutil.which("cargo")
    git = shutil.which("git")
    if not cargo:
        print("    [FAIL] Cargo is not installed or not on PATH.")
        return False
    if not git:
        print("    [FAIL] Git is not installed or not on PATH.")
        return False

    build_root = Path(tempfile.mkdtemp(prefix="clyro_pngquant_", dir=str(PROJECT_ROOT)))
    repo_dir = build_root / "pngquant"
    target_dir = build_root / "target"
    env = os.environ.copy()
    env["CARGO_TARGET_DIR"] = str(target_dir)

    try:
        clone_cmd = [
            git,
            "clone",
            "--depth",
            "1",
            "--branch",
            PNGQUANT_GIT_BRANCH,
            PNGQUANT_GIT_URL,
            str(repo_dir),
        ]
        clone_result = _run_command(clone_cmd, cwd=PROJECT_ROOT, env=env)
        if clone_result.returncode != 0:
            print("    [FAIL] Git clone failed for pngquant.")
            if clone_result.stdout.strip():
                print(clone_result.stdout.strip())
            if clone_result.stderr.strip():
                print(clone_result.stderr.strip())
            return False

        build_cmd = [cargo, "build", "--release", "--locked"]
        build_result = _run_command(build_cmd, cwd=repo_dir, env=env)
        if build_result.returncode != 0:
            print("    [FAIL] Cargo build failed for pngquant.")
            if build_result.stdout.strip():
                print(build_result.stdout.strip())
            if build_result.stderr.strip():
                print(build_result.stderr.strip())
            return False

        built_exe = target_dir / "release" / "pngquant.exe"
        if not built_exe.exists():
            print(f"    [FAIL] Expected built pngquant binary not found: {built_exe}")
            return False

        BIN_DIR.mkdir(exist_ok=True)
        shutil.copy2(built_exe, BIN_DIR / "pngquant.exe")
        print("    [OK] pngquant.exe built with Cargo -> bin/")
        return True
    finally:
        shutil.rmtree(build_root, ignore_errors=True)


def download_gifsicle() -> bool:
    if (BIN_DIR / "gifsicle.exe").exists():
        print("  [OK] gifsicle already present")
        return True

    archive_path = _download_archive("gifsicle")
    if archive_path is None:
        return False

    tmp = PROJECT_ROOT / "tmp_downloads"
    print("  ... Extracting gifsicle...")
    try:
        extract_zip(archive_path, tmp)
    except Exception as exc:
        print(f"    [FAIL] Extraction failed: {exc}")
        return False

    BIN_DIR.mkdir(exist_ok=True)
    for exe in tmp.rglob("gifsicle.exe"):
        shutil.copy2(exe, BIN_DIR / "gifsicle.exe")
        print("    [OK] gifsicle.exe -> bin/")
        _cleanup_tmp()
        return True

    print("    [FAIL] gifsicle.exe not found in archive")
    return False


def download_jpegoptim() -> bool:
    if (BIN_DIR / "jpegoptim.exe").exists():
        print("  [OK] jpegoptim already present")
        return True

    archive_path = _download_archive("jpegoptim")
    if archive_path is None:
        return False

    tmp = PROJECT_ROOT / "tmp_downloads"
    print("  ... Extracting jpegoptim...")
    try:
        extract_zip(archive_path, tmp)
    except Exception as exc:
        print(f"    [FAIL] Extraction failed: {exc}")
        return False

    BIN_DIR.mkdir(exist_ok=True)
    for exe in tmp.rglob("jpegoptim.exe"):
        shutil.copy2(exe, BIN_DIR / "jpegoptim.exe")
        print("    [OK] jpegoptim.exe -> bin/")
        for dll in tmp.rglob("*.dll"):
            shutil.copy2(dll, BIN_DIR / dll.name)
            print(f"    [OK] {dll.name} -> bin/ (jpegoptim dependency)")
        _cleanup_tmp()
        return True

    print("    [FAIL] jpegoptim.exe not found in archive. Contents:")
    for file_path in tmp.rglob("*"):
        if file_path.is_file():
            print(f"      {file_path.relative_to(tmp)}")
    return False


def setup_ghostscript() -> bool:
    gs_exe = BIN_DIR / "gswin64c.exe"
    gs_dll = BIN_DIR / "gsdll64.dll"
    gs_lib = BIN_DIR / "gs_lib"
    gs_res = BIN_DIR / "gs_resource"

    if gs_exe.exists() and gs_dll.exists() and gs_lib.exists() and gs_res.exists():
        print("  [OK] Ghostscript already present")
        return True

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
    print("\n--------------------------------------------------")
    print("  Step 1: Downloading External Binaries")
    print("--------------------------------------------------\n")

    BIN_DIR.mkdir(exist_ok=True)
    _cleanup_tmp()

    results = {}
    results["FFmpeg"] = download_ffmpeg()
    print()
    results["pngquant"] = download_pngquant()
    print()
    results["gifsicle"] = download_gifsicle()
    print()
    results["jpegoptim"] = download_jpegoptim()
    print()
    results["Ghostscript"] = setup_ghostscript()

    print("\n-- Binary Status --")
    all_ok = True
    for name, ok in results.items():
        status = "[OK]" if ok else "[FAIL] MISSING"
        print(f"  {status}  {name}")
        if not ok:
            all_ok = False

    print("\n-- Bundle Inputs --")
    expected_files = [
        "ffmpeg.exe", "ffprobe.exe",
        "pngquant.exe", "gifsicle.exe", "jpegoptim.exe",
        "gswin64c.exe", "gsdll64.dll",
    ]
    expected_dirs = ["gs_lib", "gs_resource"]

    for name in expected_files:
        path = BIN_DIR / name
        status = "[OK]" if path.exists() else "[MISSING]"
        print(f"  {status}  {name}")

    for name in expected_dirs:
        path = BIN_DIR / name
        status = "[OK]" if path.exists() else "[MISSING]"
        print(f"  {status}  {name}/")

    if not all_ok:
        print("\n  [WARN]  Some binaries are missing!")
        print("     The build will NOT proceed until all binaries are present.")
        print("     Please download or build the missing ones and place them in:")
        print(f"     {BIN_DIR}")

    _cleanup_tmp()
    return all_ok


def _pyinstaller_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYINSTALLER_CONFIG_DIR", str(PYINSTALLER_CACHE_DIR))
    return env


def run_pyinstaller(version: str) -> bool:
    print("\n--------------------------------------------------")
    print(f"  Step 2: Building with PyInstaller (v{version})")
    print("--------------------------------------------------\n")

    if not SPEC_FILE.exists():
        print(f"  [FAIL] Spec file not found: {SPEC_FILE}")
        return False

    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(SPEC_FILE)]
    env = _pyinstaller_env()
    print(f"  Running: {' '.join(cmd)}\n")
    print(f"  PyInstaller cache: {env['PYINSTALLER_CONFIG_DIR']}\n")

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env)
    if result.returncode != 0:
        print("\n  [FAIL] PyInstaller build failed!")
        return False

    exe_path = DIST_DIR / "Clyro" / "Clyro.exe"
    if exe_path.exists():
        mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n  [OK] Build successful: {exe_path} ({mb:.1f} MB)")
        total = sum(f.stat().st_size for f in (DIST_DIR / "Clyro").rglob("*") if f.is_file())
        print(f"  [OK] Total dist/Clyro/ size: {total / (1024 * 1024):.0f} MB")
        return True

    print(f"\n  [FAIL] Expected output not found: {exe_path}")
    return False


def run_inno_setup(version: str) -> bool:
    print("\n--------------------------------------------------")
    print(f"  Step 3: Creating Installer with Inno Setup (v{version})")
    print("--------------------------------------------------\n")

    if not ISS_FILE.exists():
        print(f"  [FAIL] ISS file not found: {ISS_FILE}")
        return False

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    iscc_paths = [
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files (x86)/Inno Setup 5/ISCC.exe"),
        Path(local_app_data) / "Programs/Inno Setup 6/ISCC.exe",
    ]

    iscc = None
    for path in iscc_paths:
        if path.exists():
            iscc = path
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
    cmd = [str(iscc), f"/DMyAppVersion={version}", str(ISS_FILE)]
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

    print(f"\n  [FAIL] Expected output not found: {setup_path}")
    return False


def main():
    version = get_project_version()

    print("==================================================")
    print(f"  Clyro Release Build Script (v{version})")
    print("==================================================")

    skip_download = "--skip-download" in sys.argv
    skip_inno = "--skip-inno" in sys.argv
    download_only = "--download-only" in sys.argv

    if not skip_download:
        all_present = download_all_binaries()
        if not all_present and not download_only:
            print("\n  [FAIL] Cannot proceed with build — missing binaries.")
            print("    Fix the missing downloads/builds above, then re-run.")
            sys.exit(1)
    else:
        print("\n  ... Skipping binary downloads (--skip-download)")

    if download_only:
        print("\n  Done (--download-only). Run again without that flag to build.")
        sys.exit(0)

    if not run_pyinstaller(version):
        print("\n  [FAIL] Build failed at PyInstaller step. Fix errors and retry.")
        sys.exit(1)

    if not skip_inno:
        if not run_inno_setup(version):
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
