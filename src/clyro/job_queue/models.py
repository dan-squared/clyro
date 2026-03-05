from PyQt6.QtCore import QObject, pyqtSignal
from clyro.core.types import JobSnapshot, Command, Result

class WorkerSignals(QObject):
    started = pyqtSignal(str)              # job_id
    progress = pyqtSignal(str, object)     # job_id, arbitrary progress object (float or dict/tuple)
    completed = pyqtSignal(str, Result)    # job_id, result
    failed = pyqtSignal(str, str, str)     # job_id, message, detail

class Job(QObject):
    def __init__(self, job_id: str, command: Command):
        super().__init__()
        self.id = job_id
        self.command = command
        self.status = "queued"
        self.progress: object = 0.0
        self.result: Result | None = None
        self.error_message: str | None = None
        self.error_detail: str | None = None
        self.is_cancelled: bool = False
        self.backup_path: 'Path | None' = None  # Set by dispatcher for restore

    def snapshot(self) -> JobSnapshot:
        return JobSnapshot(
            id=self.id,
            status=self.status,
            progress=self.progress,
            command=self.command,
            result=self.result,
            error_message=self.error_message
        )
