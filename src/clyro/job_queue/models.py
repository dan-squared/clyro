import logging
import time
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from clyro.core.types import JobSnapshot, Command, Result

logger = logging.getLogger(__name__)

class Job(QObject):
    started = pyqtSignal(str)              # job_id
    progress = pyqtSignal(str, object)     # job_id, arbitrary progress object (float or dict/tuple)
    completed = pyqtSignal(str, Result)    # job_id, result
    failed = pyqtSignal(str, str, str)     # job_id, message, detail

    def __init__(self, job_id: str, command: Command):
        super().__init__()
        self.id = job_id
        self.command = command
        self.status = "queued"
        self.progress_state: object = 0.0
        self.result: Result | None = None
        self.error_message: str | None = None
        self.error_detail: str | None = None
        self.is_cancelled: bool = False
        self.backup_path: Path | None = None  # Set by dispatcher for restore
        self.resource_kind: str = "generic"
        self.created_at = time.monotonic()
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.queue_wait_seconds: float | None = None
        self.runtime_seconds: float | None = None
        self._temp_paths: set[Path] = set()

    def mark_started(self):
        if self.started_at is None:
            self.started_at = time.monotonic()
            self.queue_wait_seconds = max(0.0, self.started_at - self.created_at)

    def mark_finished(self):
        if self.finished_at is None:
            self.finished_at = time.monotonic()
            baseline = self.started_at if self.started_at is not None else self.created_at
            self.runtime_seconds = max(0.0, self.finished_at - baseline)

    def register_temp_path(self, path: Path | None):
        if path is None:
            return
        try:
            tracked = path.resolve()
        except OSError:
            tracked = path
        self._temp_paths.add(tracked)

    def cleanup_temp_paths(self) -> int:
        keep_paths = {self.command.path}
        if self.result is not None:
            keep_paths.add(self.result.output_path)

        removed = 0
        for path in list(self._temp_paths):
            self._temp_paths.discard(path)
            if path in keep_paths:
                continue
            try:
                if path.exists() and path.is_file():
                    path.unlink(missing_ok=True)
                    removed += 1
            except OSError as exc:
                logger.debug("Deferred temp cleanup failed for %s: %s", path, exc)
        return removed

    def snapshot(self) -> JobSnapshot:
        return JobSnapshot(
            id=self.id,
            status=self.status,
            progress=self.progress_state,
            command=self.command,
            result=self.result,
            error_message=self.error_message
        )
