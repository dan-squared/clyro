# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
