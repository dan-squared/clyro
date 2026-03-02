from pathlib import Path
from clyro.core.types import MediaType

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif",
    ".gif", ".bmp", ".tiff", ".avif", ".ico"
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"
}

DOCUMENT_EXTENSIONS = {
    ".pdf"
}

def classify(path: Path) -> MediaType:
    """Classifies a file path into a MediaType based on its extension."""
    ext = path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return MediaType.IMAGE
    elif ext in VIDEO_EXTENSIONS:
        return MediaType.VIDEO
    elif ext in DOCUMENT_EXTENSIONS:
        return MediaType.DOCUMENT
    else:
        return MediaType.UNSUPPORTED

def classify_format(fmt: str) -> str:
    """Normalizes the string format (e.g. 'pdf' -> 'document')."""
    fmt = fmt.lower().strip(".")
    if f".{fmt}" in IMAGE_EXTENSIONS:
        return "image"
    if f".{fmt}" in VIDEO_EXTENSIONS:
        return "video"
    if f".{fmt}" in DOCUMENT_EXTENSIONS:
        return "document"
    return "unsupported"
