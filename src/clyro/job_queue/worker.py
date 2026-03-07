import logging
from PyQt6.QtCore import QRunnable
from clyro.job_queue.models import Job
from clyro.errors import ClyroError

logger = logging.getLogger(__name__)

class JobRunner(QRunnable):
    def __init__(self, job: Job, dispatcher, concurrency_gate=None, resource_kind: str = "generic"):
        super().__init__()
        self.job = job
        self.dispatcher = dispatcher
        self.concurrency_gate = concurrency_gate
        self.resource_kind = resource_kind
        
    def run(self):
        if self.job.is_cancelled:
            return

        acquired = False
        try:
            while self.concurrency_gate is not None and not self.job.is_cancelled:
                acquired = self.concurrency_gate.acquire(timeout=0.1)
                if acquired:
                    break

            if self.job.is_cancelled:
                return

            self.job.resource_kind = self.resource_kind
            self.job.status = "processing"
            self.job.mark_started()
            self.job.started.emit(self.job.id)

            # Delegate to dispatcher, pass job reference so it can check self.job.is_cancelled
            result = self.dispatcher.execute(self.job.command, self.job, self.job)
            
            if self.job.is_cancelled:
                return
            
            self.job.status = "completed"
            self.job.result = result
            self.job.completed.emit(self.job.id, result)
            
        except ClyroError as e:
            self.job.status = "failed"
            self.job.error_message = e.message
            self.job.error_detail = e.detail
            self.job.failed.emit(self.job.id, e.message, e.detail)
            
        except Exception as e:
            logger.exception(f"Unexpected error processing {self.job.id}")
            self.job.status = "failed"
            self.job.error_message = "Something went wrong. Check logs for details."
            self.job.error_detail = str(e)
            self.job.failed.emit(self.job.id, self.job.error_message, self.job.error_detail)
        finally:
            if self.job.started_at is not None:
                self.job.mark_finished()

            cleaned = self.job.cleanup_temp_paths()
            if cleaned:
                logger.debug("Cleaned %s temp artifact(s) for job %s", cleaned, self.job.id)

            if acquired and self.concurrency_gate is not None:
                self.concurrency_gate.release()
