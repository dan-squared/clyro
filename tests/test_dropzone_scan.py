import shutil
import uuid
from pathlib import Path

from clyro.ui.dropzone import _collect_supported_paths


def test_collect_supported_paths_filters_and_recurses():
    scratch = Path("tests") / f"_tmp_scan_{uuid.uuid4().hex[:8]}"
    supported_root = scratch / "image.jpg"
    supported_nested = scratch / "nested" / "document.pdf"
    unsupported = scratch / "nested" / "notes.txt.bak"

    scratch.mkdir(parents=True, exist_ok=True)
    try:
        supported_root.write_bytes(b"img")
        supported_nested.parent.mkdir(parents=True, exist_ok=True)
        supported_nested.write_bytes(b"pdf")
        unsupported.write_bytes(b"skip")

        paths = _collect_supported_paths([scratch])

        assert supported_root in paths
        assert supported_nested in paths
        assert unsupported not in paths
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
