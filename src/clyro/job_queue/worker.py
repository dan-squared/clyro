import logging
from PyQt6.QtCore import QRunnable
from clyro.job_queue.models import Job, WorkerSignals
from clyro.errors import ClyroError

logger = logging.getLogger(__name__)

class JobRunner(QRunnable):
    def __init__(self, job: Job, dispatcher):
        super().__init__()
        self.job = job
        self.dispatcher = dispatcher
        self.signals = WorkerSignals()
        
    def run(self):
        if self.job.is_cancelled:
            return

        self.job.status = "processing"
        self.signals.started.emit(self.job.id)
        
        try:
            if self.job.is_cancelled:
                return

            # Delegate to dispatcher, pass job reference so it can check self.job.is_cancelled
            result = self.dispatcher.execute(self.job.command, self.signals, self.job)
            
            if self.job.is_cancelled:
                return
            
            self.job.status = "completed"
            self.job.result = result
            self.signals.completed.emit(self.job.id, result)
            
        except ClyroError as e:
            self.job.status = "failed"
            self.job.error_message = e.message
            self.job.error_detail = e.detail
            self.signals.failed.emit(self.job.id, e.message, e.detail)
            
        except Exception as e:
            logger.exception(f"Unexpected error processing {self.job.id}")
            self.job.status = "failed"
            self.job.error_message = "Something went wrong. Check logs for details."
            self.job.error_detail = str(e)
            self.signals.failed.emit(self.job.id, self.job.error_message, self.job.error_detail)
