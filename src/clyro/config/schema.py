from dataclasses import dataclass, field
from typing import Literal

@dataclass
class Settings:
    # General
    output_mode: Literal["same_folder", "specific_folder", "in_place"] = "same_folder"
    output_folder: str | None = None
    web_download_folder: str | None = None
    keep_web_originals: bool = True
    skip_if_larger: bool = True
    preserve_dates: bool = True         # Preserve original file creation & modification dates
    auto_copy_to_clipboard: bool = False # Auto copy optimized files to clipboard
    strip_metadata: bool = False        # Remove EXIF/GPS data from images & videos
    backup_originals: bool = True       # Keep original in %APPDATA%/Clyro/backups
    start_on_login: bool = False
    show_tray: bool = True
    allow_screenshots: bool = False

    # Quality
    quality_preset: Literal["balanced", "max", "custom"] = "balanced"
    # Image
    image_max_size_mb: int = 150        # Skip optimization if larger (0 to disable)
    image_jpeg_quality: int = 80
    image_webp_quality: int = 75
    image_png_min_quality: int = 65
    image_preserve_metadata: bool = True
    image_use_pngquant: bool = True
    image_use_jpegoptim: bool = True
    image_preferred_format: str = "keep"
    image_adaptive_format: bool = True  # Try alternate format and pick smaller
    # Video
    video_max_size_mb: int = 1000       # Skip optimization if larger (0 to disable)
    video_crf: int = 23
    video_preset: str = "medium"
    video_remove_audio: bool = False
    video_max_width: int | None = None
    video_max_height: int | None = None
    video_hw_accel: bool = True           # Try GPU encoding (NVENC/QSV) first
    video_convert_audio_to_aac: bool = False  # Re-encode audio to AAC
    # PDF
    pdf_max_size_mb: int = 500          # Skip optimization if larger (0 to disable)
    pdf_compression: Literal["recommended", "extreme"] = "recommended"
    pdf_merge_sort_order: Literal["none", "name_asc", "name_desc", "date_asc", "date_desc"] = "none"

    # Auto Convert
    auto_convert_enabled: bool = False
    auto_convert_from: str = "png"
    auto_convert_to: str = "webp"
    auto_convert_replace: bool = False   # False = keep copy, True = replace original

    # Dropzone
    dropzone_enabled: bool = True
    dropzone_require_alt: bool = False

    # Shortcuts
    shortcut_toggle_dropzone: str = "Ctrl+Alt+D"
    shortcut_cancel_job: str = "Ctrl+Alt+X"

    schema_version: int = 10
