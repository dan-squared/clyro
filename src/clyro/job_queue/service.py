import uuid
import logging
import gc
from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool, QTimer

from clyro.job_queue.models import Job, Result
from clyro.job_queue.worker import JobRunner
from clyro.core.types import Command, OptimiseCommand
from clyro.core.backup import file_hash
from clyro.errors import QueueFullError

logger = logging.getLogger(__name__)

class QueueService(QObject):
    job_added = pyqtSignal(Job)
    job_updated = pyqtSignal(Job)
    
    def __init__(self, dispatcher, max_history=1000):
        super().__init__()
        self.dispatcher = dispatcher
        self.thread_pool = QThreadPool.globalInstance()
        # Increased to allow parallel processing of batch items
        self.thread_pool.setMaxThreadCount(4) 
        
        self.jobs: dict[str, Job] = {}
        self.history: list[str] = []
        self.max_history = max_history
        self._optimised_cache: dict[str, Result] = {}  # file_hash → Result

    def submit(self, command: Command) -> str:
        # ---- Duplicate optimization guard (Clop hash cache pattern) ----
        if isinstance(command, OptimiseCommand) and command.path.exists():
            try:
                fhash = file_hash(command.path)
                if fhash in self._optimised_cache:
                    cached = self._optimised_cache[fhash]
                    logger.info(f"Cache hit for {command.path.name} — skipping re-optimization")
                    # Create a fake completed job marked as cached
                    job_id = str(uuid.uuid4())
                    job = Job(job_id, command)
                    job.status = "cached"
                    job.result = cached
                    job.progress = (100.0, "Already optimized")
                    self.jobs[job_id] = job
                    self.history.append(job_id)
                    self.job_added.emit(job)
                    self.job_updated.emit(job)
                    return job_id
            except Exception:
                pass  # hash failed — proceed normally

        # Auto-evict oldest completed/failed jobs when approaching the limit
        if len(self.jobs) >= self.max_history:
            evict_count = max(1, self.max_history // 10)  # evict 10% at a time
            evictable = [
                jid for jid in self.history
                if self.jobs.get(jid) and self.jobs[jid].status in ("completed", "failed")
            ]
            for jid in evictable[:evict_count]:
                self.jobs.pop(jid, None)
                self.history.remove(jid)
            # If still full (all jobs active), raise
            if len(self.jobs) >= self.max_history:
                raise QueueFullError("Too many active jobs in history. Please wait or clear them.")
            
        job_id = str(uuid.uuid4())
        job = Job(job_id, command)
        
        self.jobs[job_id] = job
        self.history.append(job_id)
        
        runner = JobRunner(job, self.dispatcher)
        runner.signals.started.connect(self._on_job_started)
        runner.signals.progress.connect(self._on_job_progress)
        runner.signals.completed.connect(self._on_job_completed)
        runner.signals.failed.connect(self._on_job_failed)
        
        self.job_added.emit(job)
        self.thread_pool.start(runner)
        
        return job_id
        
    def _on_job_started(self, job_id: str):
        if job := self.jobs.get(job_id):
            logger.info(f"Job started: {job_id}")
            self.job_updated.emit(job)

    def _on_job_progress(self, job_id: str, progress: float):
        if job := self.jobs.get(job_id):
            job.progress = progress
            self.job_updated.emit(job)

    def _on_job_completed(self, job_id: str, result: Result):
        if job := self.jobs.get(job_id):
            job.status = "completed"
            job.result = result
            job.progress = (100.0, "Done")
            logger.info(f"Job completed: {job_id}")
            self.job_updated.emit(job)

            # Cache the result by file hash for duplicate guard
            if isinstance(job.command, OptimiseCommand) and job.command.path.exists():
                try:
                    fhash = file_hash(job.command.path)
                    self._optimised_cache[fhash] = result
                    # Cap cache at 500 entries
                    if len(self._optimised_cache) > 500:
                        oldest = next(iter(self._optimised_cache))
                        self._optimised_cache.pop(oldest, None)
                except Exception:
                    pass

        # Defer gc to avoid stalling the main thread mid-signal-callback
        QTimer.singleShot(500, lambda: gc.collect(0))


    def _on_job_failed(self, job_id: str, message: str, detail: str):
        if job := self.jobs.get(job_id):
            job.status = "failed"
            job.error_message = message
            job.error_detail = detail
            logger.error(f"Job failed: {job_id} - {message} ({detail})")
            self.job_updated.emit(job)
        QTimer.singleShot(500, lambda: gc.collect(0))
            
    def get_job(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def cancel_job(self, job_id: str):
        if job := self.jobs.get(job_id):
            job.is_cancelled = True
            if job.status in ("queued", "processing"):
                job.status = "failed"
                job.error_message = "Cancelled"
                self.job_updated.emit(job)

    def clear_history(self):
        for job in self.jobs.values():
            if job.status in ("queued", "processing"):
                job.is_cancelled = True
        self.thread_pool.clear() # Remove pending runnables that haven't started
        self.jobs.clear()
        self.history.clear()
