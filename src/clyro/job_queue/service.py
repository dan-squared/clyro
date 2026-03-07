import uuid
import logging
import hashlib
import json
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from threading import BoundedSemaphore

from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool

from clyro.core.classify import classify
from clyro.job_queue.models import Job, Result
from clyro.job_queue.worker import JobRunner
from clyro.core.types import Command, OptimiseCommand, MediaType
from clyro.core.backup import file_hash
from clyro.errors import QueueFullError

logger = logging.getLogger(__name__)

CacheKey = tuple[str, str, bool, str | None, str | None, str]


def _format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 ** 2:
        return f"{num_bytes / 1024:.0f} KB"
    return f"{num_bytes / (1024 ** 2):.1f} MB"


def _build_concurrency_limits() -> dict[str, int]:
    cpu_count = os.cpu_count() or 2
    image_limit = max(2, min(4, cpu_count if cpu_count <= 2 else cpu_count - 1))
    return {
        "image": image_limit,
        "video": 1,
        "document": 1,
        "generic": 1,
    }


def _settings_signature(settings) -> str:
    if settings is None:
        return "no-settings"

    if is_dataclass(settings):
        payload = asdict(settings)
    else:
        payload = getattr(settings, "__dict__", {})

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _build_cache_key(command: OptimiseCommand, settings, source_hash: str) -> CacheKey:
    output_dir = None
    if command.output_dir is not None:
        output_dir = str(command.output_dir.resolve())

    return (
        source_hash,
        str(command.path.resolve()),
        bool(command.aggressive),
        getattr(command, "output_mode", None),
        output_dir,
        _settings_signature(settings),
    )

class QueueService(QObject):
    job_added = pyqtSignal(Job)
    job_updated = pyqtSignal(Job)
    
    def __init__(self, dispatcher, max_history=1000):
        super().__init__()
        self.dispatcher = dispatcher
        self.thread_pool = QThreadPool()
        self._resource_limits = _build_concurrency_limits()
        self._resource_gates = {
            name: BoundedSemaphore(limit) for name, limit in self._resource_limits.items()
        }
        self.thread_pool.setMaxThreadCount(sum(self._resource_limits.values()) + 4)
        
        self.jobs: dict[str, Job] = {}
        self.history: list[str] = []
        self.max_history = max_history
        self._optimised_cache: dict[CacheKey, Result] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._scan_count = 0

    def _resource_kind_for_command(self, command: Command) -> str:
        media_type = classify(command.path)
        if media_type == MediaType.IMAGE:
            return "image"
        if media_type == MediaType.VIDEO:
            return "video"
        if media_type == MediaType.DOCUMENT:
            return "document"
        return "generic"

    def submit(self, command: Command) -> str:
        # Fast path: If file hash matches a recently completed job, return cached result immediately
        if isinstance(command, OptimiseCommand) and command.path.exists():
            try:
                fhash = file_hash(command.path)
                cache_key = _build_cache_key(command, getattr(self.dispatcher, "settings", None), fhash)
                cached = self._optimised_cache.get(cache_key)
                if cached and cached.output_path.exists():
                    self._cache_hits += 1
                    logger.info(f"Cache hit for {command.path.name} — skipping re-optimization")
                    # Create a fake completed job marked as cached
                    job_id = str(uuid.uuid4())
                    job = Job(job_id, command)
                    job.status = "cached"
                    job.resource_kind = self._resource_kind_for_command(command)
                    job.mark_started()
                    job.mark_finished()
                    job.result = cached
                    job.progress_state = (100.0, "Already optimized")
                    self.jobs[job_id] = job
                    self.history.append(job_id)
                    self.job_added.emit(job)
                    self.job_updated.emit(job)
                    return job_id
                if cached and not cached.output_path.exists():
                    self._optimised_cache.pop(cache_key, None)
            except Exception:
                pass  # hash failed — proceed normally
            else:
                self._cache_misses += 1

        # Auto-evict oldest completed/failed jobs when approaching the limit
        if len(self.jobs) >= self.max_history:
            evict_count = max(1, self.max_history // 10)  # evict 10% at a time
            evictable_set = set()
            for jid in self.history:
                if self.jobs.get(jid) and self.jobs[jid].status in ("completed", "failed", "cancelled", "cached"):
                    evictable_set.add(jid)
                    if len(evictable_set) >= evict_count:
                        break
            
            for jid in evictable_set:
                self.jobs.pop(jid, None)
            
            # Rebuild history without the evicted jobs
            if evictable_set:
                self.history = [j for j in self.history if j not in evictable_set]
            
            # If still full (all jobs active), raise
            if len(self.jobs) >= self.max_history:
                raise QueueFullError("Too many active jobs in history. Please wait or clear them.")
            
        job_id = str(uuid.uuid4())
        job = Job(job_id, command)
        job.resource_kind = self._resource_kind_for_command(command)
        
        self.jobs[job_id] = job
        self.history.append(job_id)
        
        runner = JobRunner(
            job,
            self.dispatcher,
            concurrency_gate=self._resource_gates.get(job.resource_kind, self._resource_gates["generic"]),
            resource_kind=job.resource_kind,
        )
        job.started.connect(self._on_job_started)
        job.progress.connect(self._on_job_progress)
        job.completed.connect(self._on_job_completed)
        job.failed.connect(self._on_job_failed)
        
        logger.debug(
            "Queued %s job %s for %s (active=%s, history=%s)",
            job.resource_kind,
            job_id,
            command.path,
            self.thread_pool.activeThreadCount(),
            len(self.history),
        )
        self.job_added.emit(job)
        self.thread_pool.start(runner)
        
        return job_id
        
    def _on_job_started(self, job_id: str):
        if job := self.jobs.get(job_id):
            wait_s = job.queue_wait_seconds or 0.0
            logger.info(
                "Job started: %s kind=%s wait=%.2fs path=%s",
                job_id,
                job.resource_kind,
                wait_s,
                job.command.path,
            )
            self.job_updated.emit(job)

    def _on_job_progress(self, job_id: str, progress: float):
        if job := self.jobs.get(job_id):
            job.progress_state = progress
            self.job_updated.emit(job)

    def _on_job_completed(self, job_id: str, result: Result):
        if job := self.jobs.get(job_id):
            job.status = "completed"
            job.result = result
            job.progress_state = (100.0, "Done")
            runtime_s = job.runtime_seconds or 0.0
            reduction = result.reduction_percent
            logger.info(
                "Job completed: %s kind=%s runtime=%.2fs reduction=%.1f%% size=%s -> %s output=%s cache=%s/%s",
                job_id,
                job.resource_kind,
                runtime_s,
                reduction,
                _format_bytes(result.original_size),
                _format_bytes(result.optimized_size),
                result.output_path,
                self._cache_hits,
                self._cache_misses,
            )
            self.job_updated.emit(job)

            # Store success results by file hash to prevent redundant re-optimizations on identical files
            if isinstance(job.command, OptimiseCommand) and job.command.path.exists():
                try:
                    fhash = file_hash(job.command.path)
                    cache_key = _build_cache_key(job.command, getattr(self.dispatcher, "settings", None), fhash)
                    if result.output_path.exists() and (
                        result.optimized_size < result.original_size
                        or result.output_path != result.source_path
                    ):
                        self._optimised_cache[cache_key] = result
                    # Cap cache at 500 entries
                    if len(self._optimised_cache) > 500:
                        oldest = next(iter(self._optimised_cache))
                        self._optimised_cache.pop(oldest, None)
                except Exception:
                    pass

    def _on_job_failed(self, job_id: str, message: str, detail: str):
        if job := self.jobs.get(job_id):
            job.status = "failed"
            job.error_message = message
            job.error_detail = detail
            logger.error(
                "Job failed: %s kind=%s wait=%s runtime=%s message=%s detail=%s",
                job_id,
                job.resource_kind,
                f"{job.queue_wait_seconds:.2f}s" if job.queue_wait_seconds is not None else "n/a",
                f"{job.runtime_seconds:.2f}s" if job.runtime_seconds is not None else "n/a",
                message,
                detail,
            )
            self.job_updated.emit(job)
            
    def get_job(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def cancel_job(self, job_id: str):
        if job := self.jobs.get(job_id):
            job.is_cancelled = True
            if job.status in ("queued", "processing"):
                job.status = "cancelled"
                job.error_message = "Cancelled by user"
                job.error_detail = "The job was cancelled before completion."
                self.job_updated.emit(job)

    def invalidate_cache_for_path(self, path: Path):
        resolved = str(path.resolve())
        stale_keys = [key for key in self._optimised_cache if key[1] == resolved]
        for key in stale_keys:
            self._optimised_cache.pop(key, None)
        if stale_keys:
            logger.debug("Invalidated %s cache entrie(s) for %s", len(stale_keys), resolved)

    def record_directory_scan(self, roots: list[Path], discovered_count: int, duration_s: float):
        self._scan_count += 1
        root_label = ", ".join(str(root) for root in roots[:2])
        if len(roots) > 2:
            root_label += f" (+{len(roots) - 2} more)"
        logger.info(
            "Directory scan %s completed in %.2fs; discovered=%s roots=%s",
            self._scan_count,
            duration_s,
            discovered_count,
            root_label,
        )

    def clear_history(self):
        for job in self.jobs.values():
            if job.status in ("queued", "processing"):
                job.is_cancelled = True
        self.thread_pool.clear() # Remove pending runnables that haven't started
        self.jobs.clear()
        self.history.clear()
        self._optimised_cache.clear()
