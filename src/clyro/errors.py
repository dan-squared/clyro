class ClyroError(Exception):
    """Base for all app errors. Always has a user-facing message."""
    def __init__(self, message: str, detail: str = ""):
        self.message = message
        self.detail = detail
        super().__init__(message)

class FileNotSupportedError(ClyroError):
    """Dropped file type is not supported."""

class ConversionNotPossibleError(ClyroError):
    """Requested conversion path doesn't exist (e.g., MP4 → DOCX)."""

class ToolNotFoundError(ClyroError):
    """Required external tool (ffmpeg, ghostscript, etc.) is missing."""

class ToolExecutionError(ClyroError):
    """External tool ran but returned an error."""

class OutputPermissionError(ClyroError):
    """Cannot write to the output destination."""

class FileTooLargeError(ClyroError):
    """Output is larger than input and skip_if_larger is enabled."""

class EncryptedPdfError(ClyroError):
    """PDF is encrypted and cannot be processed."""

class DownloadError(ClyroError):
    """Web URL download failed."""

class QueueFullError(ClyroError):
    """Queue history limit reached."""
