import shutil
import time
import uuid
from pathlib import Path

from PyQt6.QtCore import QCoreApplication

from clyro.config.schema import Settings
from clyro.core.types import OptimiseCommand, Result
from clyro.job_queue.service import QueueService

APP = QCoreApplication.instance() or QCoreApplication([])


class _SlowDispatcher:
    def __init__(self):
        self.settings = Settings()

    def execute(self, command, signals, job):
        source_size = command.path.stat().st_size
        for _ in range(8):
            if job.is_cancelled:
                return Result(
                    command.path,
                    command.path,
                    source_size,
                    source_size,
                    outcome="unchanged",
                    detail="Cancelled before optimization completed.",
                )
            time.sleep(0.02)

        output_path = command.path.with_suffix(".optimized")
        output_path.write_bytes(b"x" * max(1, source_size - 1))
        return Result(command.path, output_path, source_size, output_path.stat().st_size)


def _wait_for(predicate, timeout_s: float = 2.0):
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        APP.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise TimeoutError("Timed out waiting for queue state")


def test_cancelled_jobs_report_cancelled_state():
    scratch = Path("tests") / f"_tmp_queue_{uuid.uuid4().hex[:8]}"
    scratch.mkdir(parents=True, exist_ok=True)

    try:
        source = scratch / "sample.jpg"
        source.write_bytes(b"sample-data")

        service = QueueService(_SlowDispatcher())
        job_id = service.submit(OptimiseCommand(source, aggressive=False, output_mode="same_folder"))
        service.cancel_job(job_id)

        _wait_for(lambda: service.get_job(job_id).status == "cancelled")
        service.thread_pool.waitForDone(2000)

        job = service.get_job(job_id)
        assert job.status == "cancelled"
        assert job.error_message == "Cancelled by user"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_retry_after_cancel_can_complete():
    scratch = Path("tests") / f"_tmp_retry_{uuid.uuid4().hex[:8]}"
    scratch.mkdir(parents=True, exist_ok=True)

    try:
        source = scratch / "sample.jpg"
        source.write_bytes(b"retry-data")

        service = QueueService(_SlowDispatcher())
        first_job = service.submit(OptimiseCommand(source, aggressive=False, output_mode="same_folder"))
        service.cancel_job(first_job)
        _wait_for(lambda: service.get_job(first_job).status == "cancelled")
        service.thread_pool.waitForDone(2000)

        second_job = service.submit(OptimiseCommand(source, aggressive=False, output_mode="same_folder"))
        _wait_for(lambda: service.get_job(second_job).status == "completed")
        service.thread_pool.waitForDone(2000)

        assert service.get_job(second_job).status == "completed"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
