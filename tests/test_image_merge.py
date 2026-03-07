import shutil
import uuid
from pathlib import Path

from PIL import Image

from clyro.core.image import ImageToPdfHandler


class _DummyProgress:
    def emit(self, *args, **kwargs):
        return None


class _DummySignals:
    progress = _DummyProgress()


class _DummyJob:
    id = "job-merge"
    is_cancelled = False


def test_image_to_pdf_merge_creates_output():
    scratch = Path("tests") / f"_tmp_merge_{uuid.uuid4().hex[:8]}"
    scratch.mkdir(parents=True, exist_ok=True)

    try:
        first = scratch / "first.png"
        second = scratch / "second.png"
        output = scratch / "merged.pdf"

        Image.new("RGB", (32, 32), "red").save(first)
        Image.new("RGB", (32, 32), "blue").save(second)

        handler = ImageToPdfHandler(None)
        result = handler.merge([first, second], output, _DummySignals(), _DummyJob())

        assert output.exists()
        assert result.output_path == output
        assert result.optimized_size > 0
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
