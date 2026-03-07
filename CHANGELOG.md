# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.6] - 2026-03-07

### Fixed
- Fixed a `NameError` in `image.py` where `PIL.Image` was used in type hints before being imported.
- Restored corrupted sections of `image.py` from a botched edit.
- Pushed missing local changes that were excluded from the previous release.
- Refreshed pinned SHA-256 checksums in `build_release.py` for FFmpeg, pngquant, and gifsicle after upstream archives changed at the same URLs.

## [0.1.4] - 2026-03-07

### Added
- Shared IPC constants so the GUI, single-instance path, and CLI use the same local endpoint.
- Queue telemetry and regression coverage for cache behavior, cancel/retry flows, mixed drop inputs, updater dialogs, and folder scanning.
- A dedicated settings/about status surface for access mode, missing features, and update state.
- An automatic update setting, enabled by default, plus "update ready" and "install on close" flows.

### Changed
- Moved folder recursion off the UI thread and exposed indexing as a visible cancellable batch state.
- Reworked the settings and updater dialogs into a cleaner white minimalist UI.
- Strengthened the updater flow to download first, then prompt for install now vs install on close.
- Centralized versioning around `clyro.__version__` and aligned installer/build metadata with it.

### Fixed
- Fixed the image-to-PDF merge crash caused by a missing Pillow import.
- Fixed image module import-time typing failures on Python 3.12+ by deferring annotation evaluation.
- Removed the undeclared `requests` dependency from the CLI by switching to stdlib HTTP.
- Fixed cache reuse so optimization results are keyed by relevant settings and output context instead of source hash alone.
- Fixed stale batch auto-clear behavior that could hide active jobs when several files were dropped quickly.
- Fixed queue cancellation/result-state drift and added clearer completed, skipped, cached, cancelled, and failed outcomes.
- Fixed web-download handling and mixed drag/drop routing for folders, direct files, and URLs.
- Fixed settings drift around metadata preservation, dropzone access, and update controls.
- Fixed updater trust gaps by recognizing published installer checksums and verifying downloaded installers when available.
- Fixed release-build binary fetching by pinning external download URLs and verifying SHA-256 checksums.

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
