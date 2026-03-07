import shutil
import uuid
from pathlib import Path

from PyQt6.QtCore import QMimeData, QUrl, Qt
from PyQt6.QtWidgets import QApplication

from clyro.config.schema import Settings
from clyro.ui.dropzone import DropzoneWindow

APP = QApplication.instance() or QApplication([])


class _FakeDropEvent:
    def __init__(self, urls, modifiers=Qt.KeyboardModifier.NoModifier):
        self._mime = QMimeData()
        self._mime.setUrls(urls)
        self._modifiers = modifiers

    def mimeData(self):
        return self._mime

    def modifiers(self):
        return self._modifiers


def test_drop_event_routes_direct_files_into_directory_scan():
    scratch = Path("tests") / f"_tmp_drop_mix_{uuid.uuid4().hex[:8]}"
    folder = scratch / "folder"
    direct_file = scratch / "sample.jpg"
    nested = folder / "nested.png"
    scratch.mkdir(parents=True, exist_ok=True)
    folder.mkdir()

    try:
        direct_file.write_bytes(b"jpg")
        nested.write_bytes(b"png")

        window = DropzoneWindow(None, Settings())
        captured = {}

        def _capture(roots, direct_files, intent_mode):
            captured["roots"] = roots
            captured["direct_files"] = direct_files
            captured["intent_mode"] = intent_mode

        window._start_directory_scan = _capture
        window._handle_local_paths = lambda *args, **kwargs: captured.setdefault("handled_local", True)

        event = _FakeDropEvent(
            [
                QUrl.fromLocalFile(str(direct_file.resolve())),
                QUrl.fromLocalFile(str(folder.resolve())),
            ]
        )
        window.dropEvent(event)

        assert captured["roots"] == [folder.resolve()]
        assert captured["direct_files"] == [direct_file.resolve()]
        assert captured["intent_mode"] == "optimize"
        assert "handled_local" not in captured
        window.deleteLater()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_drop_event_rejects_multiple_web_converts():
    window = DropzoneWindow(None, Settings())
    captured = {"downloads": 0, "error": None}

    window._start_download = lambda *args, **kwargs: captured.__setitem__("downloads", captured["downloads"] + 1)
    window._flash_error = lambda message: captured.__setitem__("error", message)

    event = _FakeDropEvent(
        [QUrl("https://example.com/a.png"), QUrl("https://example.com/b.png")],
        modifiers=Qt.KeyboardModifier.AltModifier,
    )
    window.dropEvent(event)

    assert captured["downloads"] == 0
    assert captured["error"] == "Convert only 1 link at a time"
    window.deleteLater()


def test_handle_local_paths_rejects_mixed_convert_types():
    scratch = Path("tests") / f"_tmp_convert_mix_{uuid.uuid4().hex[:8]}"
    scratch.mkdir(parents=True, exist_ok=True)

    try:
        image = scratch / "image.png"
        document = scratch / "document.pdf"
        image.write_bytes(b"png")
        document.write_bytes(b"pdf")

        window = DropzoneWindow(None, Settings())
        captured = {"error": None, "shown": False}
        window._flash_error = lambda message: captured.__setitem__("error", message)
        window._show_convert_pill = lambda *args, **kwargs: captured.__setitem__("shown", True)

        window._handle_local_paths([image, document], "convert")

        assert captured["error"] == "Same type required for batch convert"
        assert captured["shown"] is False
        window.deleteLater()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
