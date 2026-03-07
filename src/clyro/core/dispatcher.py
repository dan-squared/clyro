import logging
import shutil
import time
from pathlib import Path
from clyro.core.types import Command, OptimiseCommand, ConvertCommand, MergeCommand, Result, MediaType
from clyro.core.classify import classify, classify_format
from clyro.core.output import resolve_output_path
from clyro.core.backup import backup_file
from clyro.errors import FileNotSupportedError, ClyroError

logger = logging.getLogger(__name__)

def _wait_for_stable(path: Path, job: 'Job' = None, timeout: float = 10.0, interval: float = 0.3) -> None:
    """Wait until file's mtime stops changing (The waitForModificationDateToSettle).

    Prevents processing files that are still being written (e.g. browser downloads).
    """
    try:
        last_mtime = path.stat().st_mtime
    except OSError:
        return

    stable_count = 0
    elapsed = 0.0
    while elapsed < timeout:
        if job and job.is_cancelled:
            return

        time.sleep(interval)
        elapsed += interval
        try:
            current_mtime = path.stat().st_mtime
        except OSError:
            return
        if current_mtime == last_mtime:
            stable_count += 1
            if stable_count >= 2:
                return  # Stable for 2 consecutive checks
        else:
            stable_count = 0
            last_mtime = current_mtime

    logger.debug(f"File settling timeout for {path.name} — proceeding anyway")

class CommandDispatcher:
    """Routes Job commands to explicit engine routines."""
    def __init__(self, settings, tools, optimize_dispatcher, convert_dispatcher):
        self.settings = settings
        self.tools = tools
        self.opt_dispatch = optimize_dispatcher
        self.conv_dispatch = convert_dispatcher
        
    def _finalize_result(self, src_path: Path, result: Result) -> Result:
        if not getattr(self.settings, 'preserve_dates', True):
            return result
        if not result or not result.output_path or not result.output_path.exists():
            return result
        try:
            import os
            st = src_path.stat()
            os.utime(result.output_path, (st.st_atime, st.st_mtime))
        except Exception as e:
            logger.debug(f"Failed to preserve dates for {result.output_path}: {e}")
        return result

    def execute(self, cmd: Command, signals, job: 'Job') -> Result:
        media_type = classify(cmd.path)
        if media_type == MediaType.UNSUPPORTED:
            raise FileNotSupportedError(f"Unsupported file type: {cmd.path.suffix}")

        # Wait for file to finish being written
        _wait_for_stable(cmd.path, job)

        # Resolve output path early for accurate disk space checks
        if isinstance(cmd, OptimiseCommand):
            out_path = resolve_output_path(cmd.path, self.settings, is_convert=False, override_dir=cmd.output_dir)
        elif isinstance(cmd, ConvertCommand):
            out_path = resolve_output_path(cmd.path, self.settings, is_convert=True, target_format=cmd.target_format, override_dir=cmd.output_dir)
        elif isinstance(cmd, MergeCommand):
            out_path = resolve_output_path(cmd.path, self.settings, is_convert=True, target_format=cmd.target_format, override_dir=cmd.output_dir)
            merged_stem = f"{cmd.path.stem}_merged"
            base_merged_name = merged_stem + out_path.suffix
            final_out_path = out_path.with_name(base_merged_name)
            
            # Ensure unique name if "_merged" already exists
            counter = 1
            while final_out_path.exists():
                final_out_path = final_out_path.with_name(f"{merged_stem}_{counter}{out_path.suffix}")
                counter += 1
            out_path = final_out_path
        else:
            raise ClyroError("Unknown command type.")

        # Pre-flight: ensure at least 2× source size of free disk space on the output drive
        try:
            src_size = cmd.path.stat().st_size
            
            if self.settings:
                if media_type == MediaType.IMAGE:
                    img_max = getattr(self.settings, 'image_max_size_mb', 0)
                    if img_max > 0 and src_size > img_max * 1024 * 1024:
                        raise ClyroError(f"Image too large (> {img_max} MB). Skipped.")
                elif media_type == MediaType.VIDEO:
                    vid_max = getattr(self.settings, 'video_max_size_mb', 0)
                    if vid_max > 0 and src_size > vid_max * 1024 * 1024:
                        raise ClyroError(f"Video too large (> {vid_max} MB). Skipped.")
                elif media_type == MediaType.DOCUMENT:
                    pdf_max = getattr(self.settings, 'pdf_max_size_mb', 0)
                    if pdf_max > 0 and src_size > pdf_max * 1024 * 1024:
                        raise ClyroError(f"PDF too large (> {pdf_max} MB). Skipped.")

            # Note: We check out_path.parent to ensure we check the *destination* drive.
            check_dir = out_path.parent
            if not check_dir.exists():
                # fallback if it's not created yet, though usually it exists or we can check its ancestors
                check_dir = check_dir.parent
                
            free = shutil.disk_usage(check_dir).free
            if free < src_size * 2:
                raise ClyroError(
                    f"Not enough disk space on output drive. Need ~{src_size*2 // (1024*1024)} MB free, "
                    f"but only {free // (1024*1024)} MB available."
                )
        except ClyroError:
            raise
        except Exception:
            pass  # stat() or disk_usage() could fail on network drives — don't block processing

        if isinstance(cmd, OptimiseCommand):
            err = self.tools.check_can_optimize(media_type)
            if err:
                raise ClyroError(err)

            # Backup original before in-place optimization
            if self.settings and getattr(self.settings, 'backup_originals', True):
                if getattr(self.settings, 'output_mode', '') == 'in_place':
                    backup_path = backup_file(cmd.path)
                    if backup_path:
                        job.backup_path = backup_path
                
            result = self.opt_dispatch.optimize(cmd.path, out_path, media_type, cmd.aggressive, signals, job)
            return self._finalize_result(cmd.path, result)
            
        elif isinstance(cmd, ConvertCommand):
            err = self.tools.check_can_convert(media_type, cmd.target_format)
            if err:
                raise ClyroError(err)
                
            target_type = classify_format(cmd.target_format)
            result = self.conv_dispatch.convert(cmd.path, cmd.target_format, out_path, media_type, target_type, signals, job)
            return self._finalize_result(cmd.path, result)
            
        elif isinstance(cmd, MergeCommand):
            err = self.tools.check_can_convert(media_type, cmd.target_format)
            if err:
                raise ClyroError(err)
            
            # Sort files before merging based on sort_order setting
            files = list(cmd.files_to_merge)
            order = getattr(cmd, 'sort_order', 'none')
            if order == "name_asc":
                files.sort(key=lambda p: p.name.lower())
            elif order == "name_desc":
                files.sort(key=lambda p: p.name.lower(), reverse=True)
            elif order == "date_asc":
                files.sort(key=lambda p: p.stat().st_mtime)
            elif order == "date_desc":
                files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            # "none" = keep original drop order

            target_type = classify_format(cmd.target_format)
            result = self.conv_dispatch.merge_to_pdf(files, out_path, media_type, signals, job)
            return self._finalize_result(cmd.path, result)            
        else:
            raise ClyroError("Unknown command type.")

