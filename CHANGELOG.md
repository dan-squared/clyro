# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2026-03-07

### Added
- Comprehensive audit of the core engine to prevent accidental crashes and resource leaks.

### Fixed
- **Critical**: Resolved `WorkerSignals` RuntimeError by moving signals directly onto the `Job` object, preventing premature garbage collection.
- **Deadlock Fix**: Replaced blocking `readline()` with non-blocking threaded queue readers for FFmpeg and Ghostscript, allowing jobs to be cancelled mid-run.
- **Disk Space**: Corrected pre-flight disk space validation to check the destination drive instead of the source drive, preventing crashes during cross-drive processing.
- **Cancellable Settling**: Made "File Settling" loops interruptible by cancellation signals.
- **Improved Cancellation**: Added robust subprocess termination for `pngquant`, `gifsicle`, and `jpegoptim` optimization tools.

## [0.1.2] - 2026-03-06

### Fixed
- Fixed missing `mozjpeg` dependency on target machines.
- Improved `Clyro.spec` to correctly bundle Ghostscript resource directories.

## [0.1.1] - 2026-03-06

### Fixed
- Fixed missing Ghostscript dependency in GitHub Actions build.
- Removed hardcoded absolute paths from PyInstaller spec file.
- Unified Inno Setup installer scripts.

## [0.1.0] - Initial Release

### Added
- Core image optimization with Pillow and mozjpeg.
- Video optimization using FFmpeg.
- PDF downsampling with Ghostscript.
- File conversion features (Image to PDF, Video to GIF, PDF to Image, PDF to Word).
- PyQt6-based dropzone UI with async job processing.
- Multi-threaded processing architecture.
