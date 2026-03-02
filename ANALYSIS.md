# Clyro — Complete Codebase Analysis

> **Version:** 0.1.0 · **Python:** 3.12+ · **Platform:** Windows (Win32 / 64) · **GUI:** PyQt6

---

## Table of Contents

1. [What Is Clyro?](#1-what-is-clyro)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Application Lifecycle (`main.py` → `app.py`)](#3-application-lifecycle)
4. [Core Engine](#4-core-engine)
   - 4.1 [Media Classification (`classify.py`)](#41-media-classification)
   - 4.2 [Tool Discovery (`tools.py`)](#42-tool-discovery)
   - 4.3 [Command & Type System (`types.py`)](#43-command--type-system)
   - 4.4 [Command Dispatcher (`dispatcher.py`)](#44-command-dispatcher)
   - 4.5 [Optimize Dispatcher (`optimize.py`)](#45-optimize-dispatcher)
   - 4.6 [Convert Dispatcher (`convert.py`)](#46-convert-dispatcher)
   - 4.7 [Output Path Resolution (`output.py`)](#47-output-path-resolution)
   - 4.8 [Backup & Restore (`backup.py`)](#48-backup--restore)
5. [Image Processing (`image.py`)](#5-image-processing)
   - 5.1 [Supported Formats](#51-supported-formats)
   - 5.2 [Optimization Pipeline](#52-optimization-pipeline)
   - 5.3 [Adaptive Format Trial](#53-adaptive-format-trial)
   - 5.4 [Format-Specific Engines](#54-format-specific-engines)
   - 5.5 [Image Conversion Handlers](#55-image-conversion-handlers)
6. [Video Processing (`video.py`)](#6-video-processing)
   - 6.1 [Supported Formats](#61-supported-formats)
   - 6.2 [Hardware Encoder Detection](#62-hardware-encoder-detection)
   - 6.3 [Video Optimization Pipeline](#63-video-optimization-pipeline)
   - 6.4 [Video-to-Video Conversion](#64-video-to-video-conversion)
   - 6.5 [Video-to-GIF Conversion](#65-video-to-gif-conversion)
7. [PDF Processing (`pdf.py`)](#7-pdf-processing)
   - 7.1 [PDF Optimization via Ghostscript](#71-pdf-optimization-via-ghostscript)
   - 7.2 [PDF-to-Image Conversion](#72-pdf-to-image-conversion)
   - 7.3 [PDF-to-Word Conversion](#73-pdf-to-word-conversion)
8. [Job Queue System](#8-job-queue-system)
   - 8.1 [Models (`models.py`)](#81-models)
   - 8.2 [Worker (`worker.py`)](#82-worker)
   - 8.3 [Queue Service (`service.py`)](#83-queue-service)
9. [IPC Server (`ipc/server.py`)](#9-ipc-server)
10. [User Interface](#10-user-interface)
    - 10.1 [Dropzone Window (`dropzone.py`)](#101-dropzone-window)
    - 10.2 [Settings Window (`settings_window.py`)](#102-settings-window)
    - 10.3 [System Tray (`tray.py`)](#103-system-tray)
    - 10.4 [Theme (`theme.py`)](#104-theme)
    - 10.5 [Result Card (`result_card.py`)](#105-result-card)
11. [Settings System](#11-settings-system)
    - 11.1 [Schema (`schema.py`)](#111-schema)
    - 11.2 [Presets (`presets.py`)](#112-presets)
    - 11.3 [Store (`store.py`)](#113-store)
12. [CLI (`cli/commands.py`)](#12-cli)
13. [Utilities](#13-utilities)
    - 13.1 [Download Worker (`utils/download.py`)](#131-download-worker)
    - 13.2 [Entropy Calculator (`utils/entropy.py`)](#132-entropy-calculator)
    - 13.3 [Path Helpers (`utils/paths.py`)](#133-path-helpers)
14. [External Tool Dependencies](#14-external-tool-dependencies)
15. [Error Handling (`errors.py`)](#15-error-handling)
16. [Complete Feature Matrix](#16-complete-feature-matrix)
17. [Data Flow Diagram](#17-data-flow-diagram)

---

## 1. What Is Clyro?

**Clyro** is a Windows-only media optimization and conversion desktop application. It provides a floating **drag-and-drop dropzone** UI that sits at the bottom-right corner of the screen, allowing users to instantly optimize or convert images, videos, and PDFs without opening any full-screen interface.

It is a Python port/migration of the macOS app **Clop**, preserving many of the same algorithmic patterns (adaptive format trials, file-settling wait, hardware encoder detection, etc.) while targeting Windows with PyQt6.

**Key value proposition:** Drop a file, get a smaller or converted file — silently, in the background.

---

## 2. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         clyro.main (entry)                           │
│   Single-instance check → Qt App → AppManager                        │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
  DropzoneWindow           SettingsWindow           TrayIcon
  (PyQt6 Widget)           (PyQt6 Dialog)         (QSystemTrayIcon)
        │                       │
        │ drop / URL            │ save
        ▼                       ▼
  QueueService ◄───────── SettingsStore
  (QThreadPool)
        │
        ▼  (per job, in worker thread)
  CommandDispatcher
        │
   ┌────┴─────────────┐
   ▼                  ▼
OptimizeDispatcher  ConvertDispatcher
   │    │    │          │   │   │   │
   ▼    ▼    ▼          ▼   ▼   ▼   ▼
Image Video PDF    Img→Img Img→PDF Vid→Vid Vid→GIF PDF→Img PDF→Docx
Handler Handler Handler
   │       │       │
   ▼       ▼       ▼
pngquant ffmpeg Ghostscript
jpegoptim ffprobe pymupdf
gifsicle          pdf2docx
mozjpeg
Pillow
```

---

## 3. Application Lifecycle

### Entry Point — [`src/clyro/main.py`](src/clyro/main.py)

1. **`multiprocessing.freeze_support()`** — needed for PyInstaller frozen bundles.
2. **`setup_logging()`** — rotating log file at `%APPDATA%/Clyro/logs/clyro.log` (2 MB × 3 backups) + stdout.
3. **`_install_crash_handler()`** — overrides `sys.excepthook` to write unhandled exceptions to the log; critical for invisible `.exe` errors.
4. **`cleanup_stale_temp()`** — removes partial download files older than 24 hours from the `downloads/` app-data folder.
5. **Single-instance check** — tries `POST http://localhost:12345/show`. If it gets `200`, another Clyro is already running; the new process forwards "show dropzone" and exits immediately.
6. **Qt bootstrapping** — creates `QApplication`, sets `AppUserModelID` on Win32 for correct taskbar icon grouping, loads `.ico`/`.png` icon.
7. Sets `setQuitOnLastWindowClosed(False)` so the app stays alive in the tray.
8. Instantiates **`AppManager`** and enters `app.exec()`.

### App Manager — [`src/clyro/app.py`](src/clyro/app.py)

| Responsibility | Detail |
|---|---|
| Settings loading | `SettingsStore.load()` → `Settings` dataclass |
| Tool discovery | `discover_tools()` → `ToolAvailability` |
| Handler construction | `_build_handlers()` wires image/video/pdf handlers into dispatchers |
| Dropzone positioning | Placed 40 px from bottom-right of primary screen |
| Startup registry | `HKCU\...\Run\Clyro` written/removed based on `start_on_login` setting |
| Temp file cleanup | Timer every 10 min; initial sweep after 5 s; cleans `_clyro_tmp_*`, `_palette_*`, `*.tmp.jpg`, `*.tmp.png` patterns |
| Orphan process kill | `atexit` handler uses `psutil` to kill all child processes on exit |
| Missing tool warning | Shows tray balloon 2 s after startup if FFmpeg or Ghostscript not found |
| Settings reload | Connected to `SettingsWindow.settings_saved` signal; rebuilds all handlers on save |

---

## 4. Core Engine

### 4.1 Media Classification

**File:** [`src/clyro/core/classify.py`](src/clyro/core/classify.py)

Maps file extensions to `MediaType` enum values:

| `MediaType` | Extensions |
|---|---|
| `IMAGE` | `.jpg .jpeg .png .webp .heic .heif .gif .bmp .tiff .avif .ico` |
| `VIDEO` | `.mp4 .mov .mkv .webm .avi .m4v` |
| `DOCUMENT` | `.pdf` |
| `UNSUPPORTED` | everything else |

`classify_format(fmt)` normalises a target format string (e.g. `"pdf"`) to a category string (`"document"`) for conversion routing.

---

### 4.2 Tool Discovery

**File:** [`src/clyro/core/tools.py`](src/clyro/core/tools.py)

`discover_tools()` searches for each external binary in this priority order:

1. **Bundled `bin/` folder** (next to the frozen `.exe` or in the project root for dev mode).
2. **System PATH** (`shutil.which`).
3. **User Python Scripts dir** (`%APPDATA%/Python/Python*/Scripts`).

**Tools discovered:**

| Tool | Purpose | Required? |
|---|---|---|
| `ffmpeg` | Video encode/decode, GIF generation | Yes (video) |
| `ffprobe` | Video metadata extraction | Yes (video) |
| `ghostscript` (`gswin64c` / `gswin32c`) | PDF compression | Yes (PDF) |
| `pngquant` | PNG lossy quantization | Optional (image fallback: Pillow) |
| `jpegoptim` | JPEG quality optimization | Optional (image fallback: Pillow) |
| `gifsicle` | GIF optimization | Optional (image fallback: Pillow basic) |
| `vipsthumbnail` | (reserved, not yet used) | Optional |
| `mozjpeg_lossless_optimization` | Python lib: lossless JPEG re-compression | Optional |

Ghostscript `GS_LIB` / `GS_RESOURCE` env vars are set automatically when running frozen.

---

### 4.3 Command & Type System

**File:** [`src/clyro/core/types.py`](src/clyro/core/types.py)

| Class | Purpose |
|---|---|
| `MediaType` | Enum: `IMAGE`, `VIDEO`, `DOCUMENT`, `UNSUPPORTED` |
| `Command` | Base class; holds `path: Path` |
| `OptimiseCommand` | Optimize a file in-place or to output dir |
| `ConvertCommand` | Convert a file to a different format |
| `MergeCommand` | Merge multiple files into one (images → PDF) |
| `DropIntent` | Transient object encoding what the user dropped: mode + files + optional target format |
| `Result` | Output of any job: source path, output path, original size, optimized size, resolution; computed `reduction_percent` property |
| `JobSnapshot` | Immutable snapshot of a job's state |

**Output modes** (on `OptimiseCommand` / `ConvertCommand`):
- `"same_folder"` — output next to source (appends `_optimized` suffix)
- `"specific_folder"` — user-defined output directory
- `"in_place"` — overwrite the source file

---

### 4.4 Command Dispatcher

**File:** [`src/clyro/core/dispatcher.py`](src/clyro/core/dispatcher.py)

The central router that all worker threads go through.

**`execute(cmd, signals, job)` flow:**

1. **Classify** the source file via `classify()`.
2. **`_wait_for_stable(path)`** — polls `st_mtime` every 0.3 s; waits for 2 consecutive stable readings (up to 10 s). Prevents processing files still being written (e.g. browser downloads).
3. **Pre-flight checks:**
   - File size limits from settings (`image_max_size_mb`, `video_max_size_mb`, `pdf_max_size_mb`).
   - Disk space check: requires ≥ 2× source size free on destination drive.
4. **Route by command type:**
   - `OptimiseCommand` → backup original if `backup_originals` + `in_place` mode → `OptimizeDispatcher.optimize()`
   - `ConvertCommand` → `ConvertDispatcher.convert()`
   - `MergeCommand` → `ConvertDispatcher.merge_to_pdf()`
5. **`_finalize_result()`** — preserves original `atime`/`mtime` on output file if `preserve_dates=True`.

---

### 4.5 Optimize Dispatcher

**File:** [`src/clyro/core/optimize.py`](src/clyro/core/optimize.py)

Simple router: delegates to `ImageHandler`, `VideoHandler`, or `PdfHandler` based on `MediaType`.

---

### 4.6 Convert Dispatcher

**File:** [`src/clyro/core/convert.py`](src/clyro/core/convert.py)

Maintains a routing table:

| Source → Target | Handler |
|---|---|
| image → image | `ImageToImageHandler` |
| image → document (PDF) | `ImageToPdfHandler` |
| video → video | `VideoToVideoHandler` |
| video → image (GIF) | `VideoToImageHandler` |
| document → image | `PdfToImageHandler` |
| document → document (DOCX) | `PdfToWordHandler` |

Also exposes `merge_to_pdf(sources, out_path, ...)` — forwards to `ImageToPdfHandler.merge()`.

---

### 4.7 Output Path Resolution

**File:** [`src/clyro/core/output.py`](src/clyro/core/output.py)

`resolve_output_path(source, settings, is_convert, target_format, override_dir)`:

- **Optimize:** output is `<stem>_optimized.<ext>` (or `source` for `in_place`).
- **Convert:** output is `<stem>.<target_format>`.
- **Folder selection:** `override_dir` > `same_folder` > `specific_folder` > fallback.
- **`_handle_collision(path)`**: if the output file already exists, appends `(1)`, `(2)`, ... to the stem.

---

### 4.8 Backup & Restore

**File:** [`src/clyro/core/backup.py`](src/clyro/core/backup.py)

Before any **in-place** optimization, the dispatcher copies the original to:
```
%APPDATA%\Clyro\backups\<first8hexSHA256>_<filename>
```

- `backup_file(source)` — copies with `shutil.copy2` (preserves metadata).
- `restore_file(backup_path, original_path)` — copies back.
- `file_hash(path)` — full SHA-256 of file content; used as deduplication cache key in `QueueService`.

---

## 5. Image Processing

**File:** [`src/clyro/core/image.py`](src/clyro/core/image.py)

### 5.1 Supported Formats

For **optimization**: JPEG, PNG, WebP, HEIC/HEIF, GIF, BMP, TIFF (last two are internally normalised to JPEG/PNG first).

For **conversion** (Image→Image): JPEG ↔ PNG ↔ WebP ↔ GIF and any Pillow-readable format.

---

### 5.2 Optimization Pipeline

`ImageHandler.optimize(source, out_path, aggressive, signals, job)`:

1. **Detect real type** by reading magic bytes (not extension). Handles PNG, JPEG, GIF, WebP, BMP, TIFF.
2. **HEIF registration** — `pillow_heif.register_heif_opener()` lazily on first HEIF file.
3. **TIFF/BMP normalisation** (`_convert_foreign`): re-detects inner bytes; converts to PNG (if has alpha) or JPEG (if opaque) before proceeding.
4. **Metadata stripping** — if `strip_metadata=True`, copies to a temp file and strips EXIF via Pillow `save()` without `exif=` parameter.
5. **Adaptive format trial** — if `image_adaptive_format=True` and `aggressive=True`, runs two formats in parallel and picks the smaller output (see §5.3).
6. **Single-format optimization** — delegates to `_optimize_jpeg`, `_optimize_png`, or `_optimize_gif` (§5.4).
7. **Pillow fallback** — if all external tools fail, Pillow is used to re-save with reduced quality.
8. **Skip-if-larger guard** — if `skip_if_larger=True` and `opt_size >= orig_size`, discards output and returns original.
9. **`shutil.copystat`** — copies timestamps from source to output.

---

### 5.3 Adaptive Format Trial

`_parallel_trial(img, source, primary_out, real_type, aggressive, signals, job)`:

- Only triggered when `image_adaptive_format=True` and `aggressive=True`.
- **Opaque PNG → also tries JPEG** (if `jpegoptim` available).
- **Low-entropy JPEG → also tries PNG** (if `pngquant` available; entropy < 5.0 bits indicates flat/simple image).
- Both formats are optimized **concurrently** via `ThreadPoolExecutor(max_workers=2)`.
- The smaller file wins. Clop-inspired **100 KB threshold**: the alternate format must be at least 100 KB smaller to be chosen (avoids barely-there format switches).

---

### 5.4 Format-Specific Engines

#### JPEG — `_optimize_jpeg`
- Uses **`jpegoptim`** with `--keep-all --force --max <quality> --overwrite --dest`.
- Quality: `68` (aggressive), `settings.image_jpeg_quality` (normal), default `85`.
- After `jpegoptim` run: optional **`mozjpeg_lossless_optimization`** pass — reads bytes back, applies lossless MozJPEG re-compression, writes only if smaller.
- Retries 3 times.

#### PNG — `_optimize_png`
- Uses **`pngquant`** with `--force --quality <min>-100 --output`.
- Quality range: `0-85` (aggressive), `<settings.image_png_min_quality>-100` (normal).
- Retries 3 times.

#### GIF — `_optimize_gif`
- Uses **`gifsicle`** with `-O2`/`-O3`, `--lossy=20`/`--lossy=80`, `--threads=<CPU count>`.
- Aggressive mode also applies `--colors=256`.
- Retries 3 times.

#### Pillow Fallback — `_pillow_fallback`
- JPEG: saves with `quality=settings.image_jpeg_quality` (or agg. `60`).
- PNG: saves with `optimize=True`.
- WebP: saves with `quality=settings.image_webp_quality` (or agg. `55`), `method=6`.

---

### 5.5 Image Conversion Handlers

**`ImageToImageHandler.convert(source, target_format, out_path, signals, job)`**
- Opens with Pillow (+ HEIF support).
- For JPEG target: converts mode to `RGB` (drops alpha).
- For WEBP: uses `quality=80`, `method=6`.
- For PNG: saves as-is (preserves alpha).
- Preserves EXIF data unless `strip_metadata=True`.

**`ImageToPdfHandler.convert(source, target_format, out_path, signals, job)`**
- Single image → single-page PDF using `pypdf` / `reportlab` via Pillow.
- Also exposes `merge(sources, out_path, signals, job)` — merges a list of images into a multi-page PDF.

---

## 6. Video Processing

**File:** [`src/clyro/core/video.py`](src/clyro/core/video.py)

### 6.1 Supported Formats

**Input:** `.mp4`, `.mov`, `.mkv`, `.webm`, `.avi`, `.m4v`
**Output (optimize):** same format as input
**Output (convert):** MP4, WebM, MKV, MOV, plus GIF (via `VideoToImageHandler`)

---

### 6.2 Hardware Encoder Detection

`_detect_hw_encoder(ffmpeg_path)` — called lazily on first video job, result cached per process:

1. Runs `ffmpeg -encoders` and scans output for `h264_nvenc` (NVIDIA) and `h264_qsv` (Intel).
2. For each found candidate: smoke-tests by encoding 1 black frame at 64×64 to `/dev/null`.
3. Returns the first working encoder or `None` (software fallback).
4. Can be disabled with `video_hw_accel=False` in settings.

---

### 6.3 Video Optimization Pipeline

`VideoHandler.optimize(source, out_path, aggressive, signals, job)`:

1. **`_get_video_info`** — runs `ffprobe -v quiet -print_format json -show_format -show_streams` to get: duration, resolution (W×H), fps, `has_audio`, codec name.
2. **Encoder args** (`_build_encoder_args`):
   - Aggressive: always `libx264 -crf 26 -preset slower`.
   - Normal + HW available + MP4-like: `h264_nvenc -preset p4 -cq 23` or `h264_qsv -global_quality 25`.
   - Normal SW: `libx264 -crf <settings.video_crf> -preset <settings.video_preset>`.
   - MP4/MOV/M4V output: adds `-tag:v avc1` for broad compatibility.
3. **Audio args** (`_build_audio_args`):
   - `video_remove_audio=True` or no audio track: `-an`.
   - `video_convert_audio_to_aac=True`: `-c:a aac -b:a 192k -map 0:v -map 0:a?`.
   - Default: `-c:a copy -map 0:v -map 0:a?`.
4. **Metadata stripping**: adds `-map_metadata -1` if `strip_metadata=True`.
5. **`-movflags +faststart`** for self-contained streaming MP4.
6. **3 command variants** attempted in order (HW → SW full audio → SW simple audio).
7. **Progress streaming** via `-progress pipe:1`; parses `out_time_us=` to emit percentage and `MM:SS / MM:SS` label.
8. Cancellation check in the read loop: kills process and deletes partial output.
9. **Skip-if-larger** guard + `copystat` timestamp preservation.

---

### 6.4 Video-to-Video Conversion

`VideoToVideoHandler.convert(source, target_format, out_path, signals, job)`:

Codec selection by target extension:

| Target | Video codec | Audio codec |
|---|---|---|
| `.mp4` / `.mov` / `.m4v` | `libx264 -crf 18 -preset slow` | copy / `-map 0:a?` |
| `.webm` | `libvpx-vp9 -crf 30 -b:v 0` | `libopus -b:a 128k` |
| `.mkv` | `libx264 -crf 18 -preset slow` | copy / `-map 0:a?` |
| other | `libx264 -crf 20 -preset medium` | copy |

---

### 6.5 Video-to-GIF Conversion

`VideoToImageHandler.convert(source, "gif", out_path, signals, job)`:

- **5-minute limit**: rejects videos > 300 s with a `ToolExecutionError`.
- **FPS cap**: min(`original_fps`, 15) — keeps GIF file size manageable.
- **Width cap**: min(`original_width`, 480 px) — scales with `lanczos` filter.
- **Two-pass palette generation** for high-quality GIF:
  - Pass 1: `ffmpeg ... -vf "fps=X,scale=W:-1:flags=lanczos,palettegen=stats_mode=diff"` → palette PNG.
  - Pass 2: `ffmpeg ... -i source -i palette -filter_complex "fps=X,scale=W:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer"` → output GIF.
- Cleans up the temporary palette file after completion.

---

## 7. PDF Processing

**File:** [`src/clyro/core/pdf.py`](src/clyro/core/pdf.py)

### 7.1 PDF Optimization via Ghostscript

`PdfHandler.optimize(source, out_path, aggressive, signals, job)`:

Ghostscript is invoked with a rich set of parameters grouped into:

| Arg group | Description |
|---|---|
| `GS_COMMON_ARGS` | 150 DPI output, bicubic downsampling, font embedding, compression streams, colour conversion to sRGB, detect duplicate images, etc. |
| `GS_LOSSY_ARGS` | Enabled when `pdf_compression="extreme"` or `aggressive=True`. Downsample colour/gray/mono images, DCT encode all, disable passthrough of existing JPEG. |
| `GS_LOSSLESS_ARGS` | Used for `pdf_compression="recommended"`. No downsampling, passthrough existing JPEG/JPX data. |
| `GS_PRE_ARGS` | PostScript preamble: sets custom distiller params for QFactor 0.76, removes metadata DOCINFO marks. |
| `GS_POST_ARGS` | PostScript postamble: clears producer, modification date, creation date. |

System fonts (Windows Fonts dir) are added via `-sFONTPATH`.

**Progress**: Ghostscript prints `Page N` to stdout; the handler parses this with regex and emits percentage = `current_page / total_pages × 100`.

Page count is obtained via **PyMuPDF** (`fitz.open(source).page_count`).

**Skip-if-larger** guard active.

---

### 7.2 PDF-to-Image Conversion

`PdfToImageHandler.convert(source, "png", out_path, signals, job)`:

- Uses **PyMuPDF** (`fitz`).
- Renders the **first page** only at 150 DPI as a PNG to `out_path`.
- For full multi-page extraction, the code notes this could be extended to save as a zip.

---

### 7.3 PDF-to-Word Conversion

`PdfToWordHandler.convert(source, "docx", out_path, signals, job)`:

- Uses **`pdf2docx`** library.
- A custom `ProgressConverter` subclass intercepts `parse_pages()` and `make_docx()` to emit:
  - 20–70 %: page parsing (per-page increments)
  - 75 %: generating DOCX
  - 95 %: finalizing
- Cancellation is checked between stages.

---

## 8. Job Queue System

### 8.1 Models

**File:** [`src/clyro/job_queue/models.py`](src/clyro/job_queue/models.py)

| Class | Description |
|---|---|
| `WorkerSignals(QObject)` | Qt signals: `started(job_id)`, `progress(job_id, object)`, `completed(job_id, Result)`, `failed(job_id, message, detail)` |
| `Job(QObject)` | Mutable job state: `id`, `command`, `status`, `progress`, `result`, `error_message`, `error_detail`, `is_cancelled`, `backup_path` |

`Job.snapshot()` returns an immutable `JobSnapshot` for UI display.

---

### 8.2 Worker

**File:** [`src/clyro/job_queue/worker.py`](src/clyro/job_queue/worker.py)

`JobRunner(QRunnable)`:
- Checks `is_cancelled` before starting.
- Calls `dispatcher.execute(command, signals, job)`.
- On `ClyroError`: emits `failed` with typed message and detail.
- On any other exception: logs stack trace, emits generic `failed`.
- Runs in `QThreadPool` (max 4 concurrent threads).

---

### 8.3 Queue Service

**File:** [`src/clyro/job_queue/service.py`](src/clyro/job_queue/service.py)

`QueueService(QObject)` — the top-level job manager; exposes Qt signals `job_added` and `job_updated` that the UI listens to.

**Key mechanisms:**

| Mechanism | Description |
|---|---|
| **Deduplication cache** | Before queuing, computes SHA-256 of the source file. If the hash is already in `_optimised_cache`, returns a fake "Cached" completed job instantly — no re-processing. Cache capped at 500 entries. |
| **Auto-eviction** | When `jobs` count hits `max_history` (1000), evicts the oldest 10% of completed/failed jobs. Raises `QueueFullError` only if all 1000 are still active. |
| **Cancellation** | `cancel_job(job_id)` sets `job.is_cancelled = True` and immediately marks status as `failed("Cancelled")`. The worker thread's cancellation flag is checked at strategic points in each handler. |
| **GC hint** | After each job completion/failure, schedules `gc.collect(0)` via 500ms QTimer to avoid stalling the main thread. |

---

## 9. IPC Server

**File:** [`src/clyro/ipc/server.py`](src/clyro/ipc/server.py)

An **aiohttp HTTP server** running on `localhost:12345` in a background daemon thread with its own asyncio event loop.

| Endpoint | Method | Purpose |
|---|---|---|
| `POST /optimize` | JSON `{paths: [...], aggressive: bool}` | Queue file optimization |
| `POST /convert` | JSON `{paths: [...], target_format: str}` | Queue file conversion |
| `POST /show` | — | Bring current instance's dropzone to front |

All UI mutations are dispatched to the Qt main thread via `QMetaObject.invokeMethod(..., QueuedConnection)`.

The `/show` endpoint is also used by `main.py`'s single-instance check — if a second instance detects a `200` on this endpoint, it knows the first is still alive and exits.

---

## 10. User Interface

### 10.1 Dropzone Window

**File:** [`src/clyro/ui/dropzone.py`](src/clyro/ui/dropzone.py)

A borderless, always-on-top, transparent `QWidget` (`Tool | FramelessWindowHint | WindowStaysOnTopHint | WindowDoesNotAcceptFocus`).

**Modes / Pages (QStackedWidget inside the shell):**

| Page | When shown |
|---|---|
| **Idle** | No active jobs; displays drag target with icon |
| **Single** | One active/completed job; shows progress bar and result |
| **Batch** | Multiple jobs; scrollable list of `BatchItem` pills |

**Drag-and-drop behavior:**
- `dragEnterEvent` / `dragMoveEvent`: accepts `text/uri-list` (local files) and `text/plain` (URLs).
- `dropEvent`: parses dropped items, distinguishes files from URLs.
  - URLs → starts `DownloadWorker` to fetch to temp dir, then processes.
- Dropped files are classified and intent resolved based on **modifier keys** held at drop time:
  - No modifier → optimize
  - Modifier (configured, e.g. Alt) → aggressive optimize
  - Drop on format pill → convert to that format

**Convert pill**: a dropdown row of target format buttons (e.g. JPG, PNG, WEBP, MP4, GIF, PDF) that appears below the shell and only shows formats relevant to the dropped file type.

**Name pill**: small floating badge above the shell showing the filename stem + extension badge.

**Action buttons** (outside the shell, to the right):
- **Eye** — preview the file.
- **Undo** — restore from backup (if available).
- **Stop** — cancel in-flight job.
- **Clear** — dismiss result.

**Auto-dismiss timer**: completed single-job results auto-dismiss after a configurable timeout.

**Window dragging**: the user can drag the whole dropzone window by clicking and dragging on the shell area.

---

### 10.2 Settings Window

**File:** [`src/clyro/ui/settings_window.py`](src/clyro/ui/settings_window.py)

A `660×480` `QDialog` with a **sidebar nav** (160 px) and **scrollable content pages**:

| Page | Contents |
|---|---|
| **General** | Output mode (same folder / specific folder / in-place), output folder picker, startup on login, show tray, skip-if-larger, preserve dates, strip metadata, backup originals, auto-copy to clipboard, web download folder, auto-convert settings |
| **Quality** | Quality preset selector (Light / Balanced / Max / Custom), per-format sliders: JPEG quality, WebP quality, PNG min quality, Video CRF, Video preset, PDF compression level, max file size limits |
| **Dropzone** | Dropzone enabled toggle, require-Alt-for-aggressive toggle, keyboard shortcuts for toggle dropzone and cancel job |
| **About** | App version, tool availability status table (FFmpeg, Ghostscript, pngquant, etc.), links |

Footer: **Restore Defaults**, **Cancel**, **Save** buttons. Save calls `save_settings()` on each page then `SettingsStore.save()` and emits `settings_saved` signal.

---

### 10.3 System Tray

**File:** [`src/clyro/ui/tray.py`](src/clyro/ui/tray.py)

`TrayIcon(QSystemTrayIcon)` — shown when `settings.show_tray=True`.

Context menu actions:
- **Show/Hide Dropzone**
- **Settings**
- **Quit**

Double-click toggles the dropzone.

---

### 10.4 Theme

**File:** [`src/clyro/ui/theme.py`](src/clyro/ui/theme.py)

Global `QSS` stylesheet applied to the entire `QApplication`. Dark theme with semi-transparent surfaces, subtle borders, and white typography.

---

### 10.5 Result Card

**File:** [`src/clyro/ui/result_card.py`](src/clyro/ui/result_card.py)

`ResultCard` — displayed inside the dropzone after a job completes.

Shows:
- Filename
- Original size → Optimized size
- **Size reduction percentage** (e.g. `−34 %`)
- Resolution (e.g. `1920×1080`)
- Progress bar (animated during processing)
- Status: queued / processing / completed / failed / cancelled

---

## 11. Settings System

### 11.1 Schema

**File:** [`src/clyro/config/schema.py`](src/clyro/config/schema.py)

All settings in a single `@dataclass Settings` with default values:

**General settings:**
| Field | Default | Description |
|---|---|---|
| `output_mode` | `"same_folder"` | Where to write output files |
| `output_folder` | `None` | Path for `"specific_folder"` mode |
| `skip_if_larger` | `True` | Discard output if not smaller |
| `preserve_dates` | `True` | Copy mtime/atime to output |
| `strip_metadata` | `False` | Remove EXIF/GPS |
| `backup_originals` | `True` | Backup before in-place optimize |
| `start_on_login` | `False` | Windows startup registry |
| `show_tray` | `True` | Show system tray icon |
| `auto_copy_to_clipboard` | `False` | Auto-copy optimized file path |

**Image settings:**
| Field | Default |
|---|---|
| `image_max_size_mb` | `150` (0=disable limit) |
| `image_jpeg_quality` | `80` |
| `image_webp_quality` | `75` |
| `image_png_min_quality` | `65` |
| `image_adaptive_format` | `True` |

**Video settings:**
| Field | Default |
|---|---|
| `video_max_size_mb` | `1000` |
| `video_crf` | `23` |
| `video_preset` | `"medium"` |
| `video_remove_audio` | `False` |
| `video_hw_accel` | `True` |
| `video_convert_audio_to_aac` | `False` |

**PDF settings:**
| Field | Default |
|---|---|
| `pdf_max_size_mb` | `500` |
| `pdf_compression` | `"recommended"` |

**Auto-Convert:**
| Field | Default |
|---|---|
| `auto_convert_enabled` | `False` |
| `auto_convert_from` | `"png"` |
| `auto_convert_to` | `"webp"` |
| `auto_convert_replace` | `False` |

**Dropzone / shortcuts:**
| Field | Default |
|---|---|
| `dropzone_enabled` | `True` |
| `dropzone_require_alt` | `False` |
| `shortcut_toggle_dropzone` | `"Ctrl+Alt+D"` |
| `shortcut_cancel_job` | `"Ctrl+Alt+X"` |

---

### 11.2 Presets

**File:** [`src/clyro/config/presets.py`](src/clyro/config/presets.py)

Three named quality presets that override the per-format quality fields:

| Preset | JPEG | WebP | PNG min | Video CRF | Preset | PDF |
|---|---|---|---|---|---|---|
| **Light** | 90 | 85 | 80 | 20 | fast | recommended |
| **Balanced** | 80 | 75 | 65 | 23 | medium | recommended |
| **Max** | 60 | 55 | 40 | 28 | slow | extreme |

---

### 11.3 Store

**File:** [`src/clyro/config/store.py`](src/clyro/config/store.py)

Persists `Settings` as **JSON** at `%APPDATA%\Clyro\config.json`.

- **`load()`**: reads JSON → `_migrate(data)` → `_coerce_settings(s)` → `Settings`.
- **`save(settings)`**: `dataclasses.asdict(settings)` → `json.dump` with `indent=4`.
- **`_migrate(data)`**: upgrades old config schemas (< v8) — maps legacy field names; resets unknown fields to defaults.
- **`_coerce_settings(s)`**: clamps numeric fields to valid ranges (e.g. JPEG quality 1–100, video CRF 0–51).

Schema version: **10** (current). Unknown keys are silently dropped via field filtering.

---

## 12. CLI

**File:** [`src/clyro/cli/commands.py`](src/clyro/cli/commands.py)

Entry point: `clyro-cli` (registered in `pyproject.toml`).

Built with **Typer**. Requires the Clyro GUI to be running (communicates via IPC).

```
clyro-cli optimize [FILES...]         --aggressive / -a
clyro-cli convert  [FILES...] --format / -f <fmt>
```

Both commands POST to `localhost:12345/{optimize|convert}` with absolute paths.

---

## 13. Utilities

### 13.1 Download Worker

**File:** [`src/clyro/utils/download.py`](src/clyro/utils/download.py)

`DownloadWorker(QThread)` — downloads a URL to a temp file.

- Parses filename from URL path (strips `@variant`, `?query` suffixes).
- Generates UUID-prefixed unique filename.
- 64 KB chunk streaming with per-chunk progress signal.
- `cancel()` method sets flag; checked each chunk iteration; deletes partial file.
- Emits `download_completed(temp_path, url)` or `download_failed(error, url)`.

---

### 13.2 Entropy Calculator

**File:** [`src/clyro/utils/entropy.py`](src/clyro/utils/entropy.py)

`calculate_shannon_entropy(img)` — computes Shannon entropy across all R, G, B channels from Pillow's 256-bin histogram.

- **High entropy** (> 5.0 bits) → complex image → JPEG is likely better.
- **Low entropy** (< 5.0 bits) → flat/simple image → PNG is likely better.

Used by `ImageHandler` to decide whether to trial PNG↔JPEG format switch in adaptive mode.

`large_area_entropy(img, threshold=1_000_000)` — only returns entropy for images larger than 1 MP; small images produce unreliable entropy values.

---

### 13.3 Path Helpers

**File:** [`src/clyro/utils/paths.py`](src/clyro/utils/paths.py)

- `get_app_data_dir()` → `%APPDATA%\Clyro\` (creates if needed).
- `resource_path(relative)` → resolves assets relative to `sys._MEIPASS` (frozen) or package source directory (dev).
- `get_bundle_dir()` → root of bundled executable or project root.

---

## 14. External Tool Dependencies

| Tool | Bundled in `bin/` | System fallback | Used for |
|---|---|---|---|
| `ffmpeg.exe` | ✅ | ✅ (`shutil.which`) | Video encode/decode, GIF generation |
| `ffprobe.exe` | ✅ | ✅ | Video metadata |
| `gswin64c.exe` + `gsdll64.dll` + `gs_lib/` | ✅ | ✅ | PDF compression |
| `pngquant.exe` | ✅ | ✅ | PNG quantization |
| `jpegoptim.exe` | ✅ | ✅ | JPEG quality optimization |
| `gifsicle.exe` | ✅ | ✅ | GIF optimization |
| `mozjpeg_lossless_optimization` (Python) | — | pip install | Lossless MozJPEG JPEG pass |
| `Pillow` | — | pip install | Image I/O, fallback optimization |
| `pillow-heif` | — | pip install | HEIC/HEIF support |
| `pymupdf` (`fitz`) | — | pip install | PDF page count, PDF→Image |
| `pdf2docx` | — | pip install | PDF→DOCX |
| `pypdf` | — | pip install | PDF merge/manipulation |

---

## 15. Error Handling

**File:** [`src/clyro/errors.py`](src/clyro/errors.py)

All errors inherit from `ClyroError(Exception)` which carries two strings:
- `message` — user-facing short message.
- `detail` — optional longer technical detail.

| Error class | Triggered when |
|---|---|
| `FileNotSupportedError` | Dropped file extension not in any supported set |
| `ConversionNotPossibleError` | Source→target conversion has no handler (e.g. MP4 → DOCX) |
| `ToolNotFoundError` | Required external binary is missing |
| `ToolExecutionError` | Binary ran but returned non-zero / produced no output |
| `OutputPermissionError` | Cannot write the output path |
| `FileTooLargeError` | Output larger than input and `skip_if_larger` is enabled |
| `EncryptedPdfError` | PDF is password-protected |
| `DownloadError` | URL download failed |
| `QueueFullError` | `max_history` active jobs reached (no more evictable jobs) |

Unhandled `ClyroError` bubbles up through `JobRunner` → `job_failed` signal → shown in result card. Generic Python exceptions are caught separately and shown as "Something went wrong."

---

## 16. Complete Feature Matrix

| Feature | Mode | Requires |
|---|---|---|
| JPEG optimization | Optimize | `jpegoptim` (Pillow fallback) |
| PNG optimization | Optimize | `pngquant` (Pillow fallback) |
| GIF optimization | Optimize | `gifsicle` (Pillow fallback) |
| WebP optimization | Optimize | Pillow |
| HEIC/HEIF optimization | Optimize | Pillow + pillow-heif |
| TIFF/BMP optimization | Optimize | Pillow (auto-converts internally) |
| Lossless MozJPEG pass | Optimize | `mozjpeg_lossless_optimization` |
| Adaptive format trial (PNG↔JPEG) | Aggressive | pngquant + jpegoptim |
| Video optimization (H.264) | Optimize | FFmpeg |
| GPU video encode (NVENC/QSV) | Optimize | FFmpeg + supported GPU |
| Audio strip | Optimize | FFmpeg |
| Audio to AAC | Optimize | FFmpeg |
| PDF optimization (recommended) | Optimize | Ghostscript |
| PDF optimization (extreme) | Aggressive | Ghostscript |
| EXIF/metadata strip | Optimize/Convert | Pillow / FFmpeg |
| Original backup | Optimize (in-place) | Disk space |
| Image → Image format convert | Convert | Pillow |
| Image → PDF convert | Convert | Pillow / pypdf |
| Multi-image → PDF merge | Merge | Pillow / pypdf |
| Video → Video format convert | Convert | FFmpeg |
| Video → GIF convert | Convert | FFmpeg (≤ 5 min video) |
| PDF → Image (PNG) convert | Convert | PyMuPDF |
| PDF → Word (DOCX) convert | Convert | pdf2docx |
| Web URL drag-and-drop | — | aiohttp / urllib |
| CLI optimize | CLI | Running Clyro GUI |
| CLI convert | CLI | Running Clyro GUI |
| System tray | — | PyQt6 |
| Single-instance enforcement | — | IPC HTTP server |
| Start on Windows login | — | Windows Registry |
| Duplicate file deduplication | — | SHA-256 cache |
| File-settling wait | — | mtime polling |
| Disk space pre-flight check | — | — |
| File size limit bypass | — | Settings |
| Job cancellation | — | — |
| Progress reporting (per-page/frame) | — | per handler |
| Timestamp preservation | — | `shutil.copystat` |
| Auto temp file cleanup | — | Background QTimer |
| Settings schema migration | — | `SettingsStore._migrate` |

---

## 17. Data Flow Diagram

```
User drops file(s) on DropzoneWindow
         │
         ▼
DropzoneWindow.dropEvent()
  ├─ Local file(s)  ──────────────────────────────────────────────┐
  └─ URL(s) → DownloadWorker (QThread) → temp file ──────────────┘
                                                                   │
                                                                   ▼
                                                    DropzoneWindow._submit(intent: DropIntent)
                                                                   │
                                      ┌────────────────────────────┤
                                      │                            │
                              intent.mode="optimize"     intent.mode="convert"
                              intent.mode="aggressive"   intent.mode="merge"
                                      │                            │
                                      ▼                            ▼
                               OptimiseCommand              ConvertCommand
                               or MergeCommand
                                      │
                                      ▼
                              QueueService.submit(command)
                                      │
                            ┌─────────┴─────────────┐
                            │ Dedup hash check       │
                            │ History eviction       │
                            └─────────┬─────────────┘
                                      │
                                job_added.emit(job)
                                      │
                                      ▼
                            QThreadPool.start(JobRunner)
                                      │
                            [worker thread]
                                      ▼
                            CommandDispatcher.execute(cmd)
                              ├─ classify(path)
                              ├─ _wait_for_stable(path)
                              ├─ pre-flight checks
                              ├─ backup_file() [if in-place]
                              ├─ resolve_output_path()
                              │
                              ├─ OptimizeDispatcher.optimize()
                              │    ├─ ImageHandler.optimize()
                              │    │    ├─ _get_real_type()
                              │    │    ├─ _parallel_trial() or _optimize_single()
                              │    │    │    ├─ jpegoptim / pngquant / gifsicle
                              │    │    │    └─ Pillow fallback
                              │    │    └─ mozjpeg pass
                              │    ├─ VideoHandler.optimize()
                              │    │    ├─ ffprobe (metadata)
                              │    │    ├─ _detect_hw_encoder (lazy)
                              │    │    └─ ffmpeg (encode variants)
                              │    └─ PdfHandler.optimize()
                              │         └─ Ghostscript
                              │
                              └─ ConvertDispatcher.convert() / merge_to_pdf()
                                   ├─ ImageToImageHandler (Pillow)
                                   ├─ ImageToPdfHandler (Pillow+pypdf)
                                   ├─ VideoToVideoHandler (FFmpeg)
                                   ├─ VideoToImageHandler (FFmpeg 2-pass GIF)
                                   ├─ PdfToImageHandler (PyMuPDF)
                                   └─ PdfToWordHandler (pdf2docx)
                                      │
                                      ▼
                              signals.completed.emit(job_id, Result)
                                      │
                            [main thread via Qt signal]
                                      ▼
                            QueueService._on_job_completed()
                              └─ job_updated.emit(job)
                                      │
                                      ▼
                            DropzoneWindow updates UI (ResultCard / BatchItem)
```

---

*Generated by analysis of all source modules in `src/clyro/`. Last updated: 2026-02-27.*
