# Performance Boosting Review

## Status
- Date: 2026-03-07
- Scope: current bottlenecks, implemented mitigations, and follow-up coverage

## Improvements Landed In This Pass
- Removed unnecessary third-party HTTP overhead in the CLI by using stdlib networking.
- Hardened cache keys so redundant optimization skips are safer and no longer reuse obviously stale results.
- Reduced incorrect UI churn by fixing stale batch-state detection.
- Stopped silent update downloads, which removes a startup-time bandwidth and disk spike.
- Moved folder recursion off the UI thread and added directory-scan progress plumbing.
- Added tool-aware queue throttling so image, video, and document work no longer compete as one flat pool.
- Gated adaptive image format trials behind file-size, pixel-count, and entropy thresholds.
- Added queue wait/runtime/cache telemetry and directory-scan timing logs.
- Switched temp-file cleanup from broad timer-only behavior to per-job tracked cleanup, with fallback cleanup still retained.

## Highest-Value Opportunities Completed

### 1. Background directory indexing
- Implemented: directory drops now scan in a worker thread and feed deduplicated supported files back into the normal drop pipeline.

### 2. Tool-aware concurrency
- Implemented: image jobs now run with a higher cap, while video and document jobs are serialized behind their own gates.

### 3. Smarter image trial strategy
- Implemented: adaptive dual-format trials now run only when the source characteristics justify the extra work.

### 4. Output-path and cache telemetry
- Implemented: queue start/completion logs now include wait time, runtime, output path, size reduction, cache counters, and directory-scan timings.

### 5. Smarter temp-file cleanup
- Implemented: jobs now track owned temp artifacts and clean them deterministically after completion, failure, or cancellation.

## Infrastructure Performance Follow-Ups
1. Added queue regression benchmarks for large image batches and mixed-media queues in `benchmarks/queue_regression.py`.
2. Added CI coverage for cache behavior, IPC latency assumptions, merge flows, and folder scanning.
3. Replaced build-time binary downloads with pinned artifact URLs and SHA-256 verification.
4. Centralized package and installer versioning around `clyro.__version__`.
