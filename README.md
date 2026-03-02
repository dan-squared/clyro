# 🛸 Clyro

Clyro is Windows local file optimizer and converter for images, videos, and PDFs with a clean, distraction-free interface. It processes all files entirely on-device, ensuring you own your data while utilizing high-performance compression engines.

## Features

### Image Optimization & Conversion
- **Lossless & Lossy Compression**: Employs Pillow and an optional lossless `mozjpeg` pass to radically reduce file sizes without sacrificing quality.
- **Format Support**: Handles JPEGs, PNGs, WEBPs, and HEIF files effortlessly.
- **Conversion Kit**:
  - Image to Image (Format shifting).
  - Image to PDF (Convert single images or merge multiple images into a multipage PDF).
- **Metadata Management**: Optionally preserve or strip EXIF data based on settings.

### Video Optimization & Conversion
- **Smart Re-encoding**: Leverages FFmpeg (H.264) with configurable CRF values and optimization presets.
- **Audio Stripping**: Option to remove audio tracks to maximize space savings.
- **Conversion Kit**:
  - Video to Video (Optimize MP4s).
  - Video to GIF (Convert to GIF, limited to videos under 5 minutes).

### PDF Optimization & Conversion
- **Deep Compression**: Uses Ghostscript for intelligent downsampling of embedded images and fonts, offering different presets (Recommended, Extreme).
- **Conversion Kit**:
  - PDF to Image (Extract pages to image format via PyMuPDF).
  - PDF to Word (Convert documents to editable `.docx` files using `pdf2docx`).

### 💻 User Experience
- **Dropzone UI**: A floating, always-on-top dropzone window for instant drag-and-drop actions.
- **System Tray Integration**: Runs quietly in the background minimizing desktop clutter.
- **Job Queue**: Processes multiple media files asynchronously.
- **Bundled CLI**: Includes `clyro-cli` for terminal power users.

---

## Tech Stack & Architecture

Clyro is built entirely in Python, using robust libraries to handle heavy-lifting media processing.

- **Language**: Python 3.12+
- **GUI Framework**: PyQt6 (provides the system tray and dropzone interface)
- **Image Processing**: `Pillow`, `pillow-heif`, `mozjpeg-lossless-optimization`
- **Video Processing**: `FFmpeg` / `FFprobe` (System dependencies)
- **PDF Processing**: `pymupdf` (fitz), `pdf2docx`, `pypdf`, and `Ghostscript` (System dependency)
- **CLI Framework**: `typer`
- **Network / Async**: `aiohttp`


## 📂 Folder Structure

```text
Clyro/
├── bin/                  # Place your heavy third-party .exe files here! (See note below)
├── src/
│   └── clyro/
│       ├── app.py        # Main PyQt window and application lifecycle manager
│       ├── main.py       # Entry point, single-instance checking, and IPC initialization
│       ├── core/         # The optimization engines (Image, Video, PDF handlers)
│       ├── ui/           # Front-end PyQt6 components (Dropzone, Settings, Result Cards)
│       ├── config/       # Settings schemas, default presets, and config loading
│       ├── job_queue/    # Async worker threads and queue management for background processing
│       ├── ipc/          # Inter-process communication to pass arguments to the running instance
│       └── utils/        # Helper functions (downloaders, entropy calculators, paths)
└── README.md             # You are here
```

### 💡 The `bin/` Directory
You do not need to install system-wide dependencies if you don't want to! You can simply place the following standalone executables inside the `bin/` folder, and Clyro will automatically detect and use them:
- `ffmpeg.exe` and `ffprobe.exe` (for Video)
- `pngquant.exe` and `jpegoptim.exe` (for Images)
- `gifsicle.exe` (for GIFs)
- `gswin64c.exe` and `gsdll64.dll` (for PDFs)

## 📦 Developer Setup 

### 1. Prerequisites
- **Python 3.12** or higher.
- Drop required binaries into `bin/` (or install them to your system `PATH`).

### 2. Install Dependencies
It is highly recommended to use a virtual environment.
```bash
git clone https://github.com/your-username/clyro.git
cd clyro
python -m venv venv
venv\Scripts\activate
# Install in editable mode
pip install -e .
```

### 3. Running the Application
Launch the graphical interface:
```bash
python -m clyro.main
```
