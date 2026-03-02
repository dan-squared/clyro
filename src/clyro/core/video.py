import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from clyro.core.types import Result
from clyro.errors import ToolExecutionError

logger = logging.getLogger(__name__)

_CPU_COUNT = os.cpu_count() or 2

# ---------------------------------------------------------------------------
# Hardware encoder detection
# ---------------------------------------------------------------------------

_HW_ENCODER_CACHE: dict[str, str | None] = {}

def _detect_hw_encoder(ffmpeg_path) -> str | None:
    """Auto-detect the best available H.264 hardware encoder.

    Priority: NVENC (NVIDIA) > QSV (Intel) > None (software fallback).
    Result is cached for the process lifetime.
    """
    key = str(ffmpeg_path)
    if key in _HW_ENCODER_CACHE:
        return _HW_ENCODER_CACHE[key]

    candidates = ["h264_nvenc", "h264_qsv"]
    try:
        res = subprocess.run(
            [str(ffmpeg_path), "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        output = res.stdout + res.stderr
        for enc in candidates:
            if enc in output:
                # Quick smoke test: try encoding 1 frame
                test = subprocess.run(
                    [
                        str(ffmpeg_path), "-y", "-f", "lavfi", "-i",
                        "color=black:s=64x64:d=0.1", "-c:v", enc,
                        "-frames:v", "1", "-f", "null", "-",
                    ],
                    capture_output=True, timeout=10,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if test.returncode == 0:
                    logger.info(f"Hardware encoder detected: {enc}")
                    _HW_ENCODER_CACHE[key] = enc
                    return enc
    except Exception as e:
        logger.debug(f"HW encoder detection failed: {e}")

    logger.info("No hardware encoder available — using software libx264")
    _HW_ENCODER_CACHE[key] = None
    return None

# ---------------------------------------------------------------------------
# Video metadata
# ---------------------------------------------------------------------------

def _get_video_info(ffprobe_path, source: Path) -> dict:
    """Get comprehensive video metadata: duration, resolution, fps, has_audio, codec.

    Returns a dict with keys: duration, resolution, width, height, fps, has_audio, codec.
    """
    info = {
        "duration": 0.0,
        "resolution": None,
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "has_audio": False,
        "codec": None,
    }
    if not ffprobe_path:
        return info

    cmd = [
        str(ffprobe_path), "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(source),
    ]
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        data = json.loads(res.stdout)

        # Duration from format container
        info["duration"] = float(data.get("format", {}).get("duration", 0.0))

        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type")
            if codec_type == "video" and info["width"] == 0:
                w = stream.get("width", 0)
                h = stream.get("height", 0)
                if w and h:
                    info["width"] = w
                    info["height"] = h
                    info["resolution"] = f"{w}×{h}"
                info["codec"] = stream.get("codec_name")

                # Parse FPS from r_frame_rate (e.g. "30000/1001")
                rfr = stream.get("r_frame_rate", "0/1")
                try:
                    num, den = rfr.split("/")
                    if int(den) > 0:
                        info["fps"] = round(int(num) / int(den), 2)
                except (ValueError, ZeroDivisionError):
                    pass

            elif codec_type == "audio":
                info["has_audio"] = True

    except Exception as e:
        logger.debug(f"ffprobe failed for {source}: {e}")

    return info

# ---------------------------------------------------------------------------
# FFmpeg subprocess helper with retry
# ---------------------------------------------------------------------------

def _run_ffmpeg(
    ffmpeg_path, cmd_variants: list[list[str]], *,
    signals=None, job=None, total_duration: float = 0.0, out_path: Path | None = None,
    tries_per_variant: int = 1,
) -> subprocess.CompletedProcess | None:
    """Run FFmpeg with retry and fallback to simpler arg variants.

    ``cmd_variants`` is a list of command lists to try in order.
    Each variant is tried ``tries_per_variant`` times before moving to the next.
    Progress is parsed from ``-progress pipe:2`` output.
    """
    time_regex = re.compile(r"out_time_us=(\d+)")
    duration_us = int(total_duration * 1_000_000) if total_duration > 0 else 0

    for variant_idx, cmd in enumerate(cmd_variants):
        for attempt in range(tries_per_variant):
            process = None
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    bufsize=1,
                    universal_newlines=True,
                )

                while True:
                    if job and job.is_cancelled:
                        process.kill()
                        process.wait()
                        if out_path:
                            out_path.unlink(missing_ok=True)
                        return None

                    line = process.stdout.readline()
                    if not line:
                        if process.poll() is not None:
                            break
                        time.sleep(0.01)
                        continue

                    # Parse progress
                    if signals and job and duration_us > 0:
                        m = time_regex.search(line)
                        if m:
                            current_us = int(m.group(1))
                            pct = min(95.0, (current_us / duration_us) * 100.0)

                            cur_s = current_us / 1_000_000
                            tot_s = duration_us / 1_000_000
                            cur_fmt = _fmt_time(cur_s)
                            tot_fmt = _fmt_time(tot_s)
                            signals.progress.emit(job.id, (pct, f"{cur_fmt} / {tot_fmt}"))

                if job and job.is_cancelled:
                    return None

                if process.returncode == 0:
                    return subprocess.CompletedProcess(cmd, 0)

                logger.debug(
                    f"FFmpeg variant {variant_idx} attempt {attempt+1} failed "
                    f"(rc={process.returncode})"
                )

            except Exception as e:
                logger.debug(f"FFmpeg variant {variant_idx} attempt {attempt+1} error: {e}")
                if process:
                    try:
                        process.kill()
                        process.wait()
                    except Exception:
                        pass

    return None

def _fmt_time(seconds: float) -> str:
    """Format seconds into MM:SS or HH:MM:SS."""
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

# =========================================================================
# VideoHandler — main optimization engine
# =========================================================================

class VideoHandler:
    def __init__(self, settings, tools):
        self.settings = settings
        self.tools = tools
        self._hw_encoder = None
        self._hw_checked = False

    @property
    def hw_encoder(self) -> str | None:
        """Lazily detect HW encoder on first use."""
        if not self._hw_checked:
            self._hw_checked = True
            use_hw = getattr(self.settings, "video_hw_accel", True) if self.settings else True
            if use_hw and self.tools.ffmpeg:
                self._hw_encoder = _detect_hw_encoder(self.tools.ffmpeg)
        return self._hw_encoder

    def optimize(self, source: Path, out_path: Path, aggressive: bool, signals, job: 'Job') -> Result:
        signals.progress.emit(job.id, (0, "Analyzing video…"))
        orig_size = source.stat().st_size

        # Get metadata
        meta = _get_video_info(self.tools.ffprobe, source)
        resolution = meta["resolution"]
        total_duration = meta["duration"]

        if job.is_cancelled:
            return Result(source, source, orig_size, orig_size, resolution=resolution)

        # ---- Build encoder args ----
        encoder_args = self._build_encoder_args(aggressive, out_path)
        encoder_args_sw = self._build_encoder_args(aggressive, out_path, force_software=True)

        # ---- Audio args ----
        audio_args = self._build_audio_args(meta["has_audio"])

        # ---- Build full command variants (with fallbacks) ----
        base_args = [str(self.tools.ffmpeg), "-y", "-i", str(source)]

        # Strip metadata if configured
        strip = getattr(self.settings, 'strip_metadata', False) if self.settings else False
        if strip:
            base_args += ["-map_metadata", "-1"]

        progress_args = ["-progress", "pipe:1", "-nostats", "-hide_banner", "-stats_period", "0.1"]
        faststart = ["-movflags", "+faststart"]
        output_args = faststart + progress_args + [str(out_path)]

        # Variant 1: HW encoder (or SW) + full audio mapping
        cmd1 = base_args + encoder_args + audio_args + output_args
        # Variant 2: SW encoder + full audio mapping (fallback if HW fails)
        cmd2 = base_args + encoder_args_sw + audio_args + output_args
        # Variant 3: SW encoder + simplified audio (no -map, just copy)
        simple_audio = ["-an"] if self.settings and self.settings.video_remove_audio else ["-c:a", "copy"]
        cmd3 = base_args + encoder_args_sw + simple_audio + output_args

        # De-duplicate variants
        variants = []
        seen = set()
        for v in [cmd1, cmd2, cmd3]:
            key = tuple(v)
            if key not in seen:
                seen.add(key)
                variants.append(v)

        signals.progress.emit(job.id, (5, "Compressing video…"))

        result = _run_ffmpeg(
            self.tools.ffmpeg, variants,
            signals=signals, job=job,
            total_duration=total_duration,
            out_path=out_path,
            tries_per_variant=2,
        )

        if job and job.is_cancelled:
            out_path.unlink(missing_ok=True)
            return Result(source, source, orig_size, orig_size, resolution=resolution)

        if result is None or not out_path.exists():
            raise ToolExecutionError("FFmpeg completed but output file was not created.")

        opt_size = out_path.stat().st_size

        # Skip-if-larger guard
        skip_larger = self.settings.skip_if_larger if self.settings else True
        if opt_size >= orig_size and skip_larger and out_path != source:
            out_path.unlink(missing_ok=True)
            return Result(source, source, orig_size, orig_size, resolution=resolution)

        # Copystat to preserve timestamps
        if out_path.exists():
            try:
                shutil.copystat(source, out_path)
            except Exception as e:
                logger.debug(f"copystat failed: {e}")

        signals.progress.emit(job.id, (100, "Done"))
        return Result(source, out_path, orig_size, opt_size, resolution=resolution)

    def _build_encoder_args(self, aggressive: bool, out_path: Path, force_software: bool = False) -> list[str]:
        """Build video encoder arguments.

        Aggressive mode always uses software encoder with CRF 26 / preset slower.
        Normal mode tries HW encoder first, falls back to SW.
        """
        ext = out_path.suffix.lower()
        is_mp4_like = ext in (".mp4", ".mov", ".m4v")

        if aggressive:
            # Always software for aggressive — mirrors The slower/CRF 26
            return ["-c:v", "libx264", "-crf", "26", "-preset", "slower"]

        if not force_software and self.hw_encoder and is_mp4_like:
            # HW encoder with quality parameter
            enc = self.hw_encoder
            if "nvenc" in enc:
                return ["-c:v", enc, "-preset", "p4", "-cq", "23", "-tag:v", "avc1"]
            elif "qsv" in enc:
                return ["-c:v", enc, "-global_quality", "25", "-tag:v", "avc1"]

        # Software encoder
        crf = self.settings.video_crf if self.settings else 23
        preset = self.settings.video_preset if self.settings else "medium"
        args = ["-c:v", "libx264", "-crf", str(crf), "-preset", preset]
        if is_mp4_like:
            args += ["-tag:v", "avc1"]
        return args

    def _build_audio_args(self, has_audio: bool) -> list[str]:
        """Build audio arguments."""
        remove_audio = self.settings.video_remove_audio if self.settings else False
        convert_to_aac = getattr(self.settings, "video_convert_audio_to_aac", False) if self.settings else False

        if remove_audio:
            return ["-an"]
        if not has_audio:
            return ["-an"]
        if convert_to_aac:
            return ["-c:a", "aac", "-b:a", "192k", "-map", "0:v", "-map", "0:a?"]
        return ["-c:a", "copy", "-map", "0:v", "-map", "0:a?"]

# =========================================================================
# VideoToVideoHandler — format conversion with progress
# =========================================================================

class VideoToVideoHandler:
    def __init__(self, tools):
        self.tools = tools

    def convert(self, source: Path, target_format: str, out_path: Path, signals, job: 'Job') -> Result:
        signals.progress.emit(job.id, (0, "Analyzing video…"))
        orig_size = source.stat().st_size

        meta = _get_video_info(self.tools.ffprobe, source)
        resolution = meta["resolution"]
        total_duration = meta["duration"]

        if job.is_cancelled:
            out_path.unlink(missing_ok=True)
            return None

        # Determine codec based on target format
        ext = out_path.suffix.lower()
        if ext in (".mp4", ".mov", ".m4v"):
            encoder_args = ["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-tag:v", "avc1"]
            extra = ["-movflags", "+faststart"]
        elif ext == ".webm":
            encoder_args = ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0"]
            extra = []
        elif ext == ".mkv":
            encoder_args = ["-c:v", "libx264", "-crf", "18", "-preset", "slow"]
            extra = []
        else:
            encoder_args = ["-c:v", "libx264", "-crf", "20", "-preset", "medium"]
            extra = []

        # Audio: copy if possible, re-encode for webm
        if ext == ".webm":
            audio_args = ["-c:a", "libopus", "-b:a", "128k"]
        else:
            audio_args = ["-c:a", "copy", "-map", "0:v", "-map", "0:a?"]
        audio_args_simple = ["-c:a", "copy"] if ext != ".webm" else ["-c:a", "libopus", "-b:a", "128k"]

        base = [str(self.tools.ffmpeg), "-y", "-i", str(source)]
        progress_args = ["-progress", "pipe:1", "-nostats", "-hide_banner", "-stats_period", "0.1"]
        output_args = extra + progress_args + [str(out_path)]

        cmd1 = base + encoder_args + audio_args + output_args
        cmd2 = base + encoder_args + audio_args_simple + output_args

        variants = [cmd1]
        if cmd1 != cmd2:
            variants.append(cmd2)

        signals.progress.emit(job.id, (5, f"Converting to {target_format.upper()}…"))

        result = _run_ffmpeg(
            self.tools.ffmpeg, variants,
            signals=signals, job=job,
            total_duration=total_duration,
            out_path=out_path,
            tries_per_variant=2,
        )

        if job and job.is_cancelled:
            out_path.unlink(missing_ok=True)
            return None

        if result is None or not out_path.exists():
            raise ToolExecutionError("FFmpeg format conversion failed.")

        # Copystat to preserve timestamps
        if out_path.exists():
            try:
                shutil.copystat(source, out_path)
            except Exception as e:
                logger.debug(f"copystat failed: {e}")

        signals.progress.emit(job.id, (100, "Done"))
        return Result(source, out_path, orig_size, out_path.stat().st_size, resolution=resolution)

# =========================================================================
# VideoToImageHandler — video → GIF with palette generation
# =========================================================================

class VideoToImageHandler:
    def __init__(self, tools):
        self.tools = tools

    def convert(self, source: Path, target_format: str, out_path: Path, signals, job: 'Job') -> Result:
        signals.progress.emit(job.id, (0, "Analyzing video…"))
        orig_size = source.stat().st_size

        meta = _get_video_info(self.tools.ffprobe, source)
        resolution = meta["resolution"]
        total_duration = meta["duration"]

        if total_duration > 300:
            raise ToolExecutionError(
                "Video too long for GIF conversion.",
                detail="Video to GIF conversion is limited to videos under 5 minutes.",
            )

        if job.is_cancelled:
            out_path.unlink(missing_ok=True)
            return None

        # Two-pass palette-based GIF for higher quality (The app uses gifski;
        # we use ffmpeg's palettegen/paletteuse which is cross-platform)
        palette_path = out_path.with_name(f"_palette_{out_path.stem}.png")

        # FPS and scale filters
        fps = min(meta["fps"] or 10, 15)  # Cap GIF FPS at 15
        scale_w = min(meta["width"] or 480, 480)  # Cap width at 480px
        vf_base = f"fps={fps},scale={scale_w}:-1:flags=lanczos"

        signals.progress.emit(job.id, (10, "Generating palette…"))

        # Pass 1: Generate palette
        palette_cmd = [
            str(self.tools.ffmpeg), "-y", "-i", str(source),
            "-vf", f"{vf_base},palettegen=stats_mode=diff",
            "-hide_banner", str(palette_path),
        ]

        try:
            p1 = subprocess.run(
                palette_cmd, capture_output=True, timeout=120,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if p1.returncode != 0 or not palette_path.exists():
                # Fallback: single-pass GIF (less quality but works)
                logger.warning("Palette generation failed, falling back to single-pass GIF")
                return self._single_pass_gif(source, out_path, vf_base, signals, job, orig_size, resolution, total_duration)
        except subprocess.TimeoutExpired:
            return self._single_pass_gif(source, out_path, vf_base, signals, job, orig_size, resolution, total_duration)

        if job.is_cancelled:
            palette_path.unlink(missing_ok=True)
            out_path.unlink(missing_ok=True)
            return None

        signals.progress.emit(job.id, (40, "Converting to GIF…"))

        # Pass 2: Generate GIF using the palette
        gif_cmd = [
            str(self.tools.ffmpeg), "-y",
            "-i", str(source),
            "-i", str(palette_path),
            "-lavfi", f"{vf_base} [x]; [x][1:v] paletteuse=dither=floyd_steinberg",
            "-progress", "pipe:1", "-nostats", "-hide_banner", "-stats_period", "0.1",
            str(out_path),
        ]

        result = _run_ffmpeg(
            self.tools.ffmpeg, [gif_cmd],
            signals=signals, job=job,
            total_duration=total_duration,
            out_path=out_path,
            tries_per_variant=2,
        )

        # Clean up palette
        palette_path.unlink(missing_ok=True)

        if job and job.is_cancelled:
            out_path.unlink(missing_ok=True)
            return None

        if result is None or not out_path.exists():
            raise ToolExecutionError("FFmpeg GIF conversion failed.")

        # Copystat to preserve timestamps
        if out_path.exists():
            try:
                shutil.copystat(source, out_path)
            except Exception as e:
                logger.debug(f"copystat failed: {e}")

        signals.progress.emit(job.id, (100, "Done"))
        return Result(source, out_path, orig_size, out_path.stat().st_size, resolution=resolution)

    def _single_pass_gif(
        self, source: Path, out_path: Path, vf_base: str,
        signals, job, orig_size: int, resolution: str | None, total_duration: float,
    ) -> Result:
        """Fallback: simple single-pass GIF conversion."""
        cmd = [
            str(self.tools.ffmpeg), "-y", "-i", str(source),
            "-vf", vf_base,
            "-progress", "pipe:1", "-nostats", "-hide_banner", "-stats_period", "0.1",
            str(out_path),
        ]

        result = _run_ffmpeg(
            self.tools.ffmpeg, [cmd],
            signals=signals, job=job,
            total_duration=total_duration,
            out_path=out_path,
            tries_per_variant=2,
        )

        if job and job.is_cancelled:
            out_path.unlink(missing_ok=True)
            return None

        if result is None or not out_path.exists():
            raise ToolExecutionError("FFmpeg GIF conversion failed.")

        # Copystat to preserve timestamps
        if out_path.exists():
            try:
                shutil.copystat(source, out_path)
            except Exception as e:
                logger.debug(f"copystat failed: {e}")

        signals.progress.emit(job.id, (100, "Done"))
        return Result(source, out_path, orig_size, out_path.stat().st_size, resolution=resolution)
