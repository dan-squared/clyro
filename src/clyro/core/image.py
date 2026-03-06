import logging
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from clyro.core.types import Result
from clyro.utils.entropy import calculate_shannon_entropy

logger = logging.getLogger(__name__)

_heif_registered = False
_CPU_COUNT = os.cpu_count() or 2

def _ensure_heif():
    global _heif_registered
    if not _heif_registered:
        import pillow_heif
        pillow_heif.register_heif_opener()
        _heif_registered = True

def _mozjpeg_pass(path: Path) -> None:
    """Run a lossless mozjpeg re-compression pass on an existing JPEG on disk."""
    try:
        from mozjpeg_lossless_optimization import optimize as _mozjpeg_optimize
    except ImportError:
        return
    
    if path.suffix.lower() not in ('.jpg', '.jpeg'):
        return
    try:
        data = path.read_bytes()
        optimized = _mozjpeg_optimize(data)
        if len(optimized) < len(data):
            path.write_bytes(optimized)
    except Exception as e:
        logger.warning(f"mozjpeg pass failed (non-fatal): {e}")

# ---------------------------------------------------------------------------
# File identification via magic bytes
# ---------------------------------------------------------------------------

_PNG_HEADER  = b"\x89PNG\r\n\x1a\n"
_JPEG_HEADER = b"\xff\xd8\xff"
_GIF87_HEADER = b"GIF87a"
_GIF89_HEADER = b"GIF89a"
_RIFF_HEADER = b"RIFF"
_WEBP_MARKER = b"WEBP"
_BMP_HEADER  = b"BM"
_TIFF_LE     = b"II\x2a\x00"
_TIFF_BE     = b"MM\x00\x2a"

def _get_real_type(path: Path) -> str:
    """Identify image type by header bytes, falling back to extension."""
    try:
        with open(path, "rb") as f:
            header = f.read(12)
            if header.startswith(_PNG_HEADER):
                return "png"
            if header.startswith(_JPEG_HEADER):
                return "jpeg"
            if header.startswith(_GIF87_HEADER) or header.startswith(_GIF89_HEADER):
                return "gif"
            if header.startswith(_RIFF_HEADER) and header[8:12] == _WEBP_MARKER:
                return "webp"
            if header.startswith(_BMP_HEADER):
                return "bmp"
            if header[:4] in (_TIFF_LE, _TIFF_BE):
                return "tiff"
    except Exception:
        pass
    ext = path.suffix.lower().lstrip(".")
    if ext == "jpg":
        return "jpeg"
    return ext

# ---------------------------------------------------------------------------
# Subprocess helper
# ---------------------------------------------------------------------------

def _run_tool(cmd: list[str], *, check: bool = True, tries: int = 1) -> subprocess.CompletedProcess | None:
    """Run an external tool with retries.  Returns None on all-fail when check=False."""
    last_err = None
    for attempt in range(tries):
        try:
            return subprocess.run(
                cmd,
                check=check,
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.CalledProcessError as e:
            last_err = e
            if attempt < tries - 1:
                logger.debug(f"Retrying ({attempt+1}/{tries}): {' '.join(cmd)}")
        except FileNotFoundError:
            return None
    if check and last_err:
        raise last_err
    return None

# =========================================================================
# ImageHandler — main optimisation engine
# =========================================================================

class ImageHandler:
    def __init__(self, settings, tools):
        self.settings = settings
        self.tools = tools

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def optimize(self, source: Path, out_path: Path, aggressive: bool, signals, job: 'Job') -> Result:
        signals.progress.emit(job.id, (5, "Analyzing image…"))
        orig_size = source.stat().st_size
        _ensure_heif()

        real_type = _get_real_type(source)
        from PIL import Image
        logger.debug(f"Optimizing {source.name} (detected type: {real_type})")

        resolution = "Unknown"
        try:
            with Image.open(source) as img:
                resolution = f"{img.width}×{img.height}"
                has_alpha = img.mode in ('RGBA', 'P', 'LA')
                entropy = calculate_shannon_entropy(img)

                # ---- Convert unoptimized formats (TIFF/BMP) to standard workflow formats ----
                if real_type in ("tiff", "bmp"):
                    signals.progress.emit(job.id, (10, f"Converting {real_type.upper()} to optimizable format…"))
                    real_type, source = self._convert_foreign(img, source, real_type, has_alpha)

                if job.is_cancelled:
                    return Result(source, source, orig_size, orig_size, resolution=resolution)

                # ---- Format Evaluation: Determine if a secondary format should be trialed in parallel ----
                adaptive = getattr(self.settings, "image_adaptive_format", True) if self.settings else True
                target_type = real_type
                run_trial = False  # should we also trial an alternate format?

                if adaptive and aggressive:
                    if real_type == "png" and not has_alpha and self.tools.jpegoptim:
                        # Opaque PNG → also trial JPEG
                        run_trial = True
                        target_type = "png"  # primary stays png
                    elif real_type == "jpeg" and entropy < 5.0 and self.tools.pngquant:
                        # Low-entropy JPEG → also trial PNG
                        run_trial = True
                        target_type = "jpeg"

                # Resolve actual out_path (handle format change extension)
                actual_out_path = self._resolve_ext(out_path, target_type, real_type)

                signals.progress.emit(job.id, (20, f"Optimizing as {target_type.upper()}…"))

                # Prepare a work file if we need to strip metadata first
                work_file = source
                strip = getattr(self.settings, 'strip_metadata', False) if self.settings else False
                
                if strip:
                    dest_dir = actual_out_path.parent
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    tmp_name = f"_clyro_tmp_meta_{int(time.time())}_{source.name}"
                    work_file = dest_dir / tmp_name
                    shutil.copy2(source, work_file)
                    
                    signals.progress.emit(job.id, (20, "Stripping metadata…"))
                    self._strip_metadata(work_file)
                    
                    # Reload img from stripped file to ensure correct data is passed down
                    img.close()
                    img = Image.open(work_file)

                # ---- Execute the optimization pipeline (optionally spawning a parallel format trial) ----
                if run_trial:
                    actual_out_path = self._parallel_trial(
                        img, work_file, actual_out_path, real_type, aggressive, signals, job,
                    )
                else:
                    success = self._optimize_single(
                        img, work_file, actual_out_path, target_type, real_type, aggressive, job,
                    )
                    if not success:
                        signals.progress.emit(job.id, (80, "Applying Pillow fallback…"))
                        self._pillow_fallback(img, actual_out_path, target_type, aggressive)
                        
                if work_file != source and work_file.exists():
                    work_file.unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Image optimization failed: {e}")
            raise

        if not actual_out_path.exists():
            # Safety: return original unchanged
            return Result(source, source, orig_size, orig_size, resolution=resolution)

        opt_size = actual_out_path.stat().st_size

        # Skip-if-larger guard
        skip_larger = self.settings.skip_if_larger if self.settings else True
        if opt_size >= orig_size and skip_larger and actual_out_path != source:
            actual_out_path.unlink(missing_ok=True)
            return Result(source, source, orig_size, orig_size, resolution=resolution)

        # Copystat to preserve timestamps
        if actual_out_path.exists():
            try:
                shutil.copystat(source, actual_out_path)
            except Exception as e:
                logger.debug(f"copystat failed: {e}")

        signals.progress.emit(job.id, (100, "Done"))
        return Result(source, actual_out_path, orig_size, opt_size, resolution=resolution)

    # ------------------------------------------------------------------
    # Parallel dual-format trial
    # ------------------------------------------------------------------

    def _parallel_trial(
        self, img: Image.Image, source: Path, primary_out: Path,
        real_type: str, aggressive: bool, signals, job: 'Job',
    ) -> Path:
        """Run primary + alternate format optimization concurrently, keep the smaller."""

        alt_type = "jpeg" if real_type == "png" else "png"
        alt_out = primary_out.with_suffix(".jpg" if alt_type == "jpeg" else ".png")

        # Ensure alt_out doesn't collide with primary_out
        if alt_out == primary_out:
            alt_out = primary_out.with_name(f"{primary_out.stem}_trial{alt_out.suffix}")

        # Make temporary work files for the alternate format if we need conversion
        alt_work = None
        if alt_type == "jpeg" and real_type != "jpeg":
            alt_work = alt_out.with_suffix(".tmp.jpg")
            img.convert("RGB").save(alt_work, "JPEG", quality=95)
        elif alt_type == "png" and real_type != "png":
            alt_work = alt_out.with_suffix(".tmp.png")
            img.save(alt_work, "PNG")

        results: dict[str, Path | None] = {}

        def _run_primary():
            ok = self._optimize_single(img, source, primary_out, real_type, real_type, aggressive, job)
            if not ok:
                self._pillow_fallback(img, primary_out, real_type, aggressive)
            return primary_out if primary_out.exists() else None

        def _run_alt():
            work = alt_work or source
            ok = self._optimize_single(img, work, alt_out, alt_type, alt_type, aggressive, job)
            if not ok:
                self._pillow_fallback(img, alt_out, alt_type, aggressive)
            # Clean up temp work file
            if alt_work and alt_work.exists() and alt_work != alt_out:
                alt_work.unlink(missing_ok=True)
            return alt_out if alt_out.exists() else None

        signals.progress.emit(job.id, (30, f"Trial: {real_type.upper()} vs {alt_type.upper()}…"))

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_primary = pool.submit(_run_primary)
            fut_alt = pool.submit(_run_alt)

            for fut in as_completed([fut_primary, fut_alt]):
                try:
                    path = fut.result()
                    if path:
                        results[str(path)] = path
                except Exception as e:
                    logger.debug(f"Trial failed (non-fatal): {e}")

        p_out = fut_primary.result() if not fut_primary.exception() else None
        a_out = fut_alt.result() if not fut_alt.exception() else None

        # Adaptive Result Selection: Return the smallest output file
        if p_out and a_out:
            p_size = p_out.stat().st_size
            a_size = a_out.stat().st_size
            # Format switching threshold: require at least 100KB of savings to justify changing the underlying file extension
            if p_size - a_size > 100_000:
                logger.info(f"Adaptive: {alt_type} wins ({a_size:,} vs {p_size:,} bytes)")
                p_out.unlink(missing_ok=True)
                # Handle collision for the new extension in the output directory
                from clyro.core.output import _handle_collision
                final = _handle_collision(a_out)
                if final != a_out:
                    a_out.rename(final)
                    a_out = final
                return a_out
            else:
                a_out.unlink(missing_ok=True)
                return p_out
        elif a_out:
            return a_out
        elif p_out:
            return p_out

        # Both failed — return source unchanged
        return primary_out

    # ------------------------------------------------------------------
    # Single-format optimisation dispatcher
    # ------------------------------------------------------------------

    def _optimize_single(
        self, img: Image.Image, source: Path, out_path: Path,
        target_type: str, real_type: str, aggressive: bool, job: 'Job',
    ) -> bool:
        """Optimise using the best available external tool.  Returns True on success."""

        if target_type == "jpeg":
            work_file = source
            if real_type != "jpeg":
                work_file = out_path.with_suffix(".tmp.jpg")
                img.convert("RGB").save(work_file, "JPEG", quality=95)
            ok = self._optimize_jpeg(work_file, out_path, aggressive, job)
            if work_file != source and work_file.exists():
                work_file.unlink(missing_ok=True)
            if not ok:
                logger.info(f"jpegoptim not available — falling back to Pillow for {source.name}")
            return ok

        elif target_type == "png":
            work_file = source
            if real_type != "png":
                work_file = out_path.with_suffix(".tmp.png")
                img.save(work_file, "PNG")
            ok = self._optimize_png(work_file, out_path, aggressive, job)
            if work_file != source and work_file.exists():
                work_file.unlink(missing_ok=True)
            if not ok:
                logger.info(f"pngquant not available — falling back to Pillow for {source.name}")
            return ok

        elif target_type == "gif":
            ok = self._optimize_gif(source, out_path, aggressive, job)
            if not ok:
                logger.info(f"gifsicle not available — falling back to Pillow for {source.name}")
            return ok

        return False

    # ------------------------------------------------------------------
    # Format-specific optimizers
    # ------------------------------------------------------------------

    def _optimize_jpeg(self, source: Path, out_path: Path, aggressive: bool, job: 'Job') -> bool:
        from PIL import Image
        if not self.tools.jpegoptim:
            return False

        # Use quality from settings when available, otherwise sensible defaults
        if aggressive:
            quality = "68"
        elif self.settings and hasattr(self.settings, 'image_jpeg_quality'):
            quality = str(self.settings.image_jpeg_quality)
        else:
            quality = "85"

        logger.info(f"Using jpegoptim ({self.tools.jpegoptim}) quality={quality} for {source.name}")

        dest_dir = out_path.parent
        tmp_name = f"_clyro_tmp_{int(time.time())}_{source.name}"
        tmp_path = dest_dir / tmp_name

        shutil.copy2(source, tmp_path)

        cmd = [
            str(self.tools.jpegoptim),
            "--keep-all", "--force",
            "--max", quality,
            "--overwrite",
            "--dest", str(dest_dir),
            str(tmp_path),
        ]

        result = _run_tool(cmd, check=False, tries=3)
        if result is None or result.returncode != 0:
            logger.warning(f"jpegoptim failed (returncode={result.returncode if result else 'None'}): {result.stderr.decode() if result and result.stderr else 'no output'}")
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            return False

        if tmp_path.exists():
            if out_path.exists() and out_path != tmp_path:
                out_path.unlink()
            tmp_path.rename(out_path)

        _mozjpeg_pass(out_path)
        return out_path.exists()

    def _optimize_png(self, source: Path, out_path: Path, aggressive: bool, job: 'Job') -> bool:
        from PIL import Image
        if not self.tools.pngquant:
            return False

        # Use quality from settings when available
        if aggressive:
            quality = "0-85"
        elif self.settings and hasattr(self.settings, 'image_png_min_quality'):
            min_q = self.settings.image_png_min_quality
            quality = f"{min_q}-100"
        else:
            quality = "0-100"

        logger.info(f"Using pngquant ({self.tools.pngquant}) quality={quality} for {source.name}")

        cmd = [
            str(self.tools.pngquant),
            "--force",
            "--quality", quality,
            "--output", str(out_path),
            str(source),
        ]

        result = _run_tool(cmd, check=False, tries=3)
        if not (out_path.exists() and out_path.stat().st_size > 0):
            logger.warning(f"pngquant failed: {result.stderr.decode() if result and result.stderr else 'no output'}")
            return False
        return True

    def _optimize_gif(self, source: Path, out_path: Path, aggressive: bool, job: 'Job') -> bool:
        from PIL import Image
        if not self.tools.gifsicle:
            return False

        level = "3" if aggressive else "2"
        lossy = "80" if aggressive else "20"
        logger.info(f"Using gifsicle ({self.tools.gifsicle}) -O{level} --lossy={lossy} for {source.name}")

        cmd = [
            str(self.tools.gifsicle),
            f"-O{level}",
            f"--lossy={lossy}",
            f"--threads={_CPU_COUNT}",
        ]
        if aggressive:
            cmd.append("--colors=256")
        cmd += ["--output", str(out_path), str(source)]

        result = _run_tool(cmd, check=False, tries=3)
        if not (out_path.exists() and out_path.stat().st_size > 0):
            logger.warning(f"gifsicle failed: {result.stderr.decode() if result and result.stderr else 'no output'}")
            return False
        return True

    # ------------------------------------------------------------------
    # TIFF / BMP conversion
    # ------------------------------------------------------------------

    def _convert_foreign(
        self, img: Image.Image, source: Path, real_type: str, has_alpha: bool,
    ) -> tuple[str, Path]:
        """Convert TIFF/BMP to PNG or JPEG before optimizing."""

        # If the image file secretly contains PNG/JPEG data, detect by re-reading header
        try:
            raw = source.read_bytes()[:12]
            if raw.startswith(_PNG_HEADER):
                new_path = source.with_suffix(".png")
                shutil.copy2(source, new_path)
                return "png", new_path
            if raw.startswith(_JPEG_HEADER):
                new_path = source.with_suffix(".jpeg")
                shutil.copy2(source, new_path)
                return "jpeg", new_path
            if raw.startswith(_GIF87_HEADER) or raw.startswith(_GIF89_HEADER):
                new_path = source.with_suffix(".gif")
                shutil.copy2(source, new_path)
                return "gif", new_path
        except Exception:
            pass

        # Regular conversion: use PNG if has alpha, JPEG otherwise
        if has_alpha:
            new_path = source.with_suffix(".png")
            img.save(new_path, "PNG")
            return "png", new_path
        else:
            new_path = source.with_suffix(".jpg")
            img.convert("RGB").save(new_path, "JPEG", quality=95)
            return "jpeg", new_path

    # ------------------------------------------------------------------
    # Pillow fallback
    # ------------------------------------------------------------------

    def _pillow_fallback(self, img: Image.Image, out_path: Path, target_type: str, aggressive: bool):
        """Fallback to Pillow's native optimization if external C-binaries fail or are absent."""
        quality = 75 if aggressive else (self.settings.image_jpeg_quality if self.settings else 80)
        exif = img.info.get("exif")
        kwargs = {"exif": exif} if exif else {}
        if target_type == "webp":
            img.save(out_path, quality=quality, method=6, **kwargs)
        elif target_type == "jpeg":
            rgb = img.convert("RGB") if img.mode != "RGB" else img
            rgb.save(out_path, "JPEG", optimize=True, quality=quality, **kwargs)
        elif target_type == "png":
            img.save(out_path, "PNG", optimize=True, **kwargs)
        else:
            img.save(out_path, optimize=True, quality=quality, **kwargs)

    @staticmethod
    def _strip_metadata(path: Path):
        """Strip non-essential EXIF/GPS metadata to save bytes before optimization."""
        from PIL import Image
        try:
            with Image.open(path) as img:
                data = list(img.getdata())
                clean = Image.new(img.mode, img.size)
                clean.putdata(data)
                ext = path.suffix.lower()
                if ext in (".jpg", ".jpeg"):
                    clean.save(path, "JPEG", quality=95, optimize=True)
                elif ext == ".png":
                    clean.save(path, "PNG", optimize=True)
                elif ext == ".webp":
                    clean.save(path, "WEBP", quality=90, method=6)
                else:
                    clean.save(path)
        except Exception as e:
            logger.debug(f"Metadata strip failed (non-fatal): {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_ext(out_path: Path, target_type: str, real_type: str) -> Path:
        """Switch the output extension if the target format differs from the source."""
        if target_type == real_type:
            return out_path
        ext_map = {"jpeg": ".jpg", "png": ".png", "gif": ".gif", "webp": ".webp"}
        new_ext = ext_map.get(target_type)
        if new_ext and out_path.suffix.lower() != new_ext:
            candidate = out_path.with_suffix(new_ext)
            if candidate.exists():
                from clyro.core.output import _handle_collision
                candidate = _handle_collision(candidate)
            return candidate
        return out_path

# =========================================================================
# ImageToImageHandler — format conversion
# =========================================================================

class ImageToImageHandler:
    def __init__(self, tools):
        self.tools = tools

    def convert(self, source: Path, target_format: str, out_path: Path, signals, job: 'Job') -> Result:
        signals.progress.emit(job.id, (10, "Opening image…"))
        from PIL import Image
        orig_size = source.stat().st_size
        _ensure_heif()

        res = None
        target_format = target_format.lower()

        try:
            with Image.open(source) as img:
                res = f"{img.width}×{img.height}"

                if target_format in ('jpg', 'jpeg') and img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')

                if job.is_cancelled:
                    out_path.unlink(missing_ok=True)
                    return None

                signals.progress.emit(job.id, (50, f"Saving as {target_format.upper()}…"))

                quality = 90
                if target_format == 'webp':
                    quality = 80
                elif target_format in ('jpg', 'jpeg'):
                    quality = 85

                exif = img.info.get("exif")
                kwargs = {"exif": exif} if exif else {}
                img.save(out_path, quality=quality, optimize=True, **kwargs)

            # Post-conversion optimization pass
            if not job.is_cancelled:
                signals.progress.emit(job.id, (80, "Compressing…"))
                handler = ImageHandler(None, self.tools)
                if target_format in ('jpg', 'jpeg'):
                    handler._optimize_jpeg(out_path, out_path, aggressive=False, job=job)
                elif target_format == 'png':
                    handler._optimize_png(out_path, out_path, aggressive=False, job=job)
                elif target_format == 'gif':
                    handler._optimize_gif(out_path, out_path, aggressive=False, job=job)
            else:
                out_path.unlink(missing_ok=True)
                return None

        except Exception as e:
            logger.error(f"Image conversion failed: {e}")
            raise

        # Copystat to preserve timestamps
        if out_path.exists():
            try:
                shutil.copystat(source, out_path)
            except Exception as e:
                logger.debug(f"copystat failed: {e}")

        signals.progress.emit(job.id, (100, "Done"))
        return Result(source, out_path, orig_size, out_path.stat().st_size, resolution=res)

# =========================================================================
# ImageToPdfHandler — image → PDF conversion & merging
# =========================================================================

class ImageToPdfHandler:
    def __init__(self, tools):
        self.tools = tools

    def convert(self, source: Path, target_format: str, out_path: Path, signals, job: 'Job') -> Result:
        signals.progress.emit(job.id, (10, "Opening image…"))
        orig_size = source.stat().st_size
        _ensure_heif()
        from PIL import Image

        res = None
        with Image.open(source) as img:
            res = f"{img.width}×{img.height}"
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            if job.is_cancelled:
                out_path.unlink(missing_ok=True)
                return None
            signals.progress.emit(job.id, (50, "Saving to PDF…"))
            img.save(out_path, "PDF", resolution=100.0)

        signals.progress.emit(job.id, (100, "Done"))
        return Result(source, out_path, orig_size, out_path.stat().st_size, resolution=res)

    def merge(self, sources: list[Path], out_path: Path, signals, job: 'Job') -> Result:
        signals.progress.emit(job.id, (0, "Starting merge…"))

        if not sources:
            raise ValueError("No sources provided for merge")

        orig_size = sum(p.stat().st_size for p in sources)
        res = None
        _ensure_heif()

        first_img = None
        append_images = []
        try:
            first_img = Image.open(sources[0])
            res = f"{first_img.width}×{first_img.height} (Multipage)"
            if first_img.mode in ('RGBA', 'P'):
                first_img = first_img.convert('RGB')

            for i, src in enumerate(sources[1:], start=1):
                if job.is_cancelled:
                    out_path.unlink(missing_ok=True)
                    return None
                pct = min(90.0, (i / len(sources)) * 90.0)
                signals.progress.emit(job.id, (pct, f"Processing {i+1} / {len(sources)}"))
                extra_img = Image.open(src)
                if extra_img.mode in ('RGBA', 'P'):
                    extra_img = extra_img.convert('RGB')
                append_images.append(extra_img)

            if job.is_cancelled:
                out_path.unlink(missing_ok=True)
                return None

            signals.progress.emit(job.id, (92, "Saving PDF…"))
            first_img.save(
                out_path,
                "PDF",
                resolution=100.0,
                save_all=True,
                append_images=append_images,
            )
        finally:
            if first_img:
                first_img.close()
            for im in append_images:
                im.close()
            del append_images

        signals.progress.emit(job.id, (100, "Done"))
        return Result(sources[0], out_path, orig_size, out_path.stat().st_size, resolution=res)
