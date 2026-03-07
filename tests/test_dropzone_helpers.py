import shutil
import uuid
from pathlib import Path

from PyQt6.QtCore import QUrl, Qt

from clyro.config.schema import Settings
from clyro.ui.dropzone import (
    _intent_mode_from_modifiers,
    _partition_drop_urls,
    _resolve_web_download_command_mode,
)


def test_intent_mode_from_modifiers():
    assert _intent_mode_from_modifiers(Qt.KeyboardModifier.NoModifier) == "optimize"
    assert _intent_mode_from_modifiers(Qt.KeyboardModifier.ShiftModifier) == "aggressive"
    assert _intent_mode_from_modifiers(Qt.KeyboardModifier.AltModifier) == "convert"


def test_partition_drop_urls_splits_files_directories_and_web_urls():
    scratch = Path("tests") / f"_tmp_partition_{uuid.uuid4().hex[:8]}"
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        file_path = scratch / "image.jpg"
        dir_path = scratch / "folder"
        ignored = scratch / "notes.txt"
        file_path.write_bytes(b"img")
        dir_path.mkdir()
        ignored.write_bytes(b"ignore")

        local_files, directories, web_urls = _partition_drop_urls(
            [
                QUrl.fromLocalFile(str(file_path.resolve())),
                QUrl.fromLocalFile(str(dir_path.resolve())),
                QUrl.fromLocalFile(str(ignored.resolve())),
                QUrl("https://example.com/sample.png"),
            ]
        )

        assert local_files == [file_path.resolve()]
        assert directories == [dir_path.resolve()]
        assert web_urls == ["https://example.com/sample.png"]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_resolve_web_download_command_mode_uses_explicit_folder_rule():
    settings = Settings(output_mode="same_folder", web_download_folder=str(Path("downloads").resolve()), keep_web_originals=True)
    path = Path(settings.web_download_folder) / "image.png"

    mode, output_dir = _resolve_web_download_command_mode(path, settings)

    assert mode == "specific_folder"
    assert output_dir == Path(settings.web_download_folder).resolve()


def test_resolve_web_download_command_mode_falls_back_for_non_download_files():
    settings = Settings(output_mode="same_folder", web_download_folder=str(Path("downloads").resolve()), keep_web_originals=False)
    path = Path("other") / "image.png"

    mode, output_dir = _resolve_web_download_command_mode(path, settings)

    assert mode == "same_folder"
    assert output_dir is None
