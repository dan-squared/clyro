import argparse
import shutil
import time
import uuid
from pathlib import Path

from PyQt6.QtCore import QCoreApplication

from clyro.config.schema import Settings
from clyro.core.classify import classify
from clyro.core.types import MediaType, OptimiseCommand, Result
from clyro.job_queue.service import QueueService

TERMINAL_STATUSES = {"completed", "failed", "cached"}
APP = QCoreApplication.instance() or QCoreApplication([])


class FakeDispatcher:
    def __init__(self):
        self.settings = Settings()

    def execute(self, command, signals, job):
        media_type = classify(command.path)
        duration_by_type = {
            MediaType.IMAGE: 0.18,
            MediaType.VIDEO: 0.42,
            MediaType.DOCUMENT: 0.25,
        }
        duration = duration_by_type.get(media_type, 0.2)
        source_size = command.path.stat().st_size
        output_path = command.path.with_suffix(f"{command.path.suffix}.optimized")

        for step in range(4):
            if job.is_cancelled:
                return Result(command.path, command.path, source_size, source_size)
            time.sleep(duration / 4)
            signals.progress.emit(job.id, (15 + ((step + 1) * 20), f"step {step + 1}/4"))

        reduced_size = max(1, source_size - 128)
        output_path.write_bytes(b"x" * reduced_size)
        return Result(command.path, output_path, source_size, reduced_size)


def _wait_for_jobs(service: QueueService, job_ids: list[str], timeout_s: float) -> None:
    deadline = time.perf_counter() + timeout_s

    while time.perf_counter() < deadline:
        APP.processEvents()
        if all(
            (job := service.get_job(job_id)) is not None and job.status in TERMINAL_STATUSES
            for job_id in job_ids
        ):
            service.thread_pool.waitForDone(2000)
            return
        time.sleep(0.01)

    service.thread_pool.waitForDone(2000)
    raise TimeoutError(f"Timed out waiting for queue scenario after {timeout_s:.1f}s")


def _write_fixture(path: Path, size: int = 4096):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"a" * size)


def run_scenario(name: str, specs: list[tuple[str, int]], timeout_s: float) -> float:
    tmp_path = Path("benchmarks") / f"_tmp_{name}_{uuid.uuid4().hex[:8]}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        service = QueueService(FakeDispatcher())

        commands = []
        for index, (suffix, size) in enumerate(specs, start=1):
            path = tmp_path / f"{name}_{index}{suffix}"
            _write_fixture(path, size=size)
            commands.append(OptimiseCommand(path, aggressive=False, output_mode="same_folder"))

        started = time.perf_counter()
        job_ids = [service.submit(command) for command in commands]
        _wait_for_jobs(service, job_ids, timeout_s)
        elapsed = time.perf_counter() - started

        for job_id in job_ids:
            job = service.get_job(job_id)
            if job is None or job.status != "completed":
                raise RuntimeError(f"Scenario {name} did not complete cleanly: {job_id}")

        service.thread_pool.waitForDone(2000)
        return elapsed
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Queue concurrency regression checks.")
    parser.add_argument("--check", action="store_true", help="Fail if timings regress past loose thresholds.")
    args = parser.parse_args()

    scenarios = [
        (
            "image_batch",
            [(".jpg", 6144) for _ in range(12)],
            8.0,
            2.5,
        ),
        (
            "mixed_media",
            [(".jpg", 6144) for _ in range(6)]
            + [(".mp4", 8192) for _ in range(3)]
            + [(".pdf", 4096) for _ in range(2)],
            10.0,
            3.0,
        ),
    ]

    failures = []
    for name, specs, timeout_s, threshold_s in scenarios:
        elapsed = run_scenario(name, specs, timeout_s)
        print(f"{name}: {elapsed:.2f}s (threshold {threshold_s:.2f}s)")
        if args.check and elapsed > threshold_s:
            failures.append(f"{name} exceeded {threshold_s:.2f}s (got {elapsed:.2f}s)")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
