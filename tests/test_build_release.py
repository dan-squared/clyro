import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace

import build as build_script
import build_release


def test_download_all_binaries_fails_when_required_tools_are_missing(monkeypatch):
    scratch = Path("tests") / f"_tmp_build_release_{uuid.uuid4().hex[:8]}"
    bin_dir = scratch / "bin"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(build_release, "BIN_DIR", bin_dir)
    monkeypatch.setattr(build_release, "_cleanup_tmp", lambda: None)
    monkeypatch.setattr(build_release, "download_ffmpeg", lambda: True)
    monkeypatch.setattr(build_release, "download_pngquant", lambda: False)
    monkeypatch.setattr(build_release, "download_gifsicle", lambda: False)
    monkeypatch.setattr(build_release, "download_jpegoptim", lambda: False)
    monkeypatch.setattr(build_release, "setup_ghostscript", lambda: False)

    try:
        assert build_release.download_all_binaries() is False
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_download_pngquant_falls_back_to_cargo_build(monkeypatch):
    scratch = Path("tests") / f"_tmp_download_pngquant_{uuid.uuid4().hex[:8]}"
    calls = []
    scratch.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(build_release, "BIN_DIR", scratch / "bin")
    monkeypatch.setattr(build_release, "_download_archive", lambda _tool: None)
    monkeypatch.setattr(build_release, "build_pngquant", lambda: calls.append("cargo") or True)

    try:
        assert build_release.download_pngquant() is True
        assert calls == ["cargo"]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_build_pngquant_copies_built_binary(monkeypatch):
    scratch = Path("tests") / f"_tmp_build_pngquant_{uuid.uuid4().hex[:8]}"
    bin_dir = scratch / "bin"
    build_root = scratch / "build_root"
    target_exe = build_root / "target" / "release" / "pngquant.exe"

    monkeypatch.setattr(build_release, "PROJECT_ROOT", scratch)
    monkeypatch.setattr(build_release, "BIN_DIR", bin_dir)
    monkeypatch.setattr(build_release.shutil, "which", lambda name: f"C:/tools/{name}.exe")
    monkeypatch.setattr(
        build_release.tempfile,
        "mkdtemp",
        lambda prefix, dir: str(build_root),
    )

    def _fake_run(cmd, *, cwd=None, env=None):
        target_exe.parent.mkdir(parents=True, exist_ok=True)
        target_exe.write_bytes(b"pngquant")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(build_release, "_run_command", _fake_run)

    try:
        assert build_release.build_pngquant() is True
        assert (bin_dir / "pngquant.exe").exists()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_pyinstaller_env_uses_workspace_local_cache(monkeypatch):
    monkeypatch.setattr(build_release, "PYINSTALLER_CACHE_DIR", Path("C:/tmp/clyro-pyinstaller-cache"))

    env = build_release._pyinstaller_env()

    assert env["PYINSTALLER_CONFIG_DIR"] == "C:\\tmp\\clyro-pyinstaller-cache"


def test_build_script_reports_missing_required_inputs():
    scratch = Path("tests") / f"_tmp_build_inputs_{uuid.uuid4().hex[:8]}"
    try:
        (scratch / "bin").mkdir(parents=True, exist_ok=True)
        missing = build_script._missing_build_inputs(scratch)
        assert "pngquant.exe" in missing
        assert "gs_lib/" in missing
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
