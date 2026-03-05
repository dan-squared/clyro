import shutil
from pathlib import Path
from dataclasses import dataclass
from clyro.core.types import MediaType

@dataclass
class ToolAvailability:
    ffmpeg: Path | None
    ffprobe: Path | None
    ghostscript: Path | None
    pngquant: Path | None
    jpegoptim: Path | None
    gifsicle: Path | None
    vipsthumbnail: Path | None
    mozjpeg: bool  # Python library, not a binary

    def check_can_optimize(self, media_type: MediaType) -> str | None:
        if media_type == MediaType.VIDEO and not self.ffmpeg:
            return "FFmpeg is required for video optimization. Install it and restart."
        if media_type == MediaType.DOCUMENT and not self.ghostscript:
            return "Ghostscript is required for PDF optimization. Install it and restart."
        if media_type == MediaType.IMAGE:
            missing = []
            if not self.jpegoptim: missing.append("jpegoptim")
            if not self.pngquant: missing.append("pngquant")
            if not self.gifsicle: missing.append("gifsicle")
            if missing:
                import logging
                logging.getLogger(__name__).warning(
                    f"Some image optimizers are missing ({', '.join(missing)}). Optimization will use basic Pillow logic instead."
                )
        return None

    def check_can_convert(self, src: MediaType, target_fmt: str) -> str | None:
        if src == MediaType.VIDEO and not self.ffmpeg:
            return "FFmpeg is required for video conversion."
        # Could add checks for pdf2docx etc.
        return None

def discover_tools() -> ToolAvailability:
    import sys
    import os
    from clyro.utils.paths import get_bundle_dir

    bundle_dir = get_bundle_dir()

    # Configure Ghostscript runtime paths when running from a frozen bundle.
    # GS needs its lib/ and Resource/ folders to load fonts and PostScript procedures.
    if getattr(sys, 'frozen', False):
        gs_lib = bundle_dir / "bin" / "gs_lib"
        gs_res = bundle_dir / "bin" / "gs_resource"
        if gs_lib.exists():
            os.environ.setdefault("GS_LIB", str(gs_lib))
        if gs_res.exists():
            os.environ.setdefault("GS_RESOURCE", str(gs_res))

    def find(name: str) -> Path | None:
        exe_name = name + (".exe" if sys.platform == "win32" else "")
        
        # 1. Try bundled bin folder first (frozen: _MEIPASS/bin, dev: src/bin)
        bundle_bin = bundle_dir / "bin" / exe_name
        if bundle_bin.exists():
            return bundle_bin

        # 1b. Dev mode: also check project root bin/ (one level above src/)
        if not getattr(sys, 'frozen', False):
            project_root_bin = bundle_dir.parent / "bin" / exe_name
            if project_root_bin.exists():
                return project_root_bin
            
        # 2. Try system PATH
        path = shutil.which(name)
        if path:
            return Path(path)
            
        # 3. Also check user Python Scripts directory (pip --user installs here)
        scripts_dirs = []
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA", "")
            import glob
            for d in glob.glob(os.path.join(appdata, "Python", "Python*", "Scripts")):
                scripts_dirs.append(d)
        for d in scripts_dirs:
            candidate = Path(d) / exe_name
            if candidate.exists():
                return candidate
        return None

    # On Windows, Ghostscript might be gswin64c or gswin32c
    gs = find("gswin64c") or find("gswin32c") or find("gs")

    try:
        import mozjpeg_lossless_optimization
        mozjpeg_available = True
    except ImportError:
        mozjpeg_available = False

    tools = ToolAvailability(
        ffmpeg=find("ffmpeg"),
        ffprobe=find("ffprobe"),
        ghostscript=gs,
        pngquant=find("pngquant"),
        jpegoptim=find("jpegoptim"),
        gifsicle=find("gifsicle"),
        vipsthumbnail=find("vipsthumbnail"),
        mozjpeg=mozjpeg_available,
    )

    import logging
    _log = logging.getLogger(__name__)
    _log.info(
        f"Tool discovery complete: "
        f"ffmpeg={'✓ ' + str(tools.ffmpeg) if tools.ffmpeg else '✗'}, "
        f"pngquant={'✓ ' + str(tools.pngquant) if tools.pngquant else '✗'}, "
        f"jpegoptim={'✓ ' + str(tools.jpegoptim) if tools.jpegoptim else '✗'}, "
        f"gifsicle={'✓ ' + str(tools.gifsicle) if tools.gifsicle else '✗'}, "
        f"ghostscript={'✓ ' + str(tools.ghostscript) if tools.ghostscript else '✗'}, "
        f"mozjpeg={'✓' if tools.mozjpeg else '✗'}"
    )
    return tools
