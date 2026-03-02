"""Backup & restore system for original files.

Before in-place optimization, the original is copied to
%APPDATA%/Clyro/backups/<hash_prefix>_<filename>.  Restore copies it back.
"""

import hashlib
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

_BACKUP_DIR: Path | None = None

def _get_backup_dir() -> Path:
    global _BACKUP_DIR
    if _BACKUP_DIR is None:
        from clyro.utils.paths import get_app_data_dir
        _BACKUP_DIR = get_app_data_dir() / "backups"
        _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return _BACKUP_DIR

def _short_hash(path: Path) -> str:
    """First 8 hex chars of SHA-256 of the file content."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:8]

def backup_file(source: Path) -> Path | None:
    """Copy *source* into the backup directory.  Returns the backup path."""
    try:
        bdir = _get_backup_dir()
        short = _short_hash(source)
        backup_path = bdir / f"{short}_{source.name}"
        shutil.copy2(source, backup_path)
        logger.debug(f"Backed up {source.name} → {backup_path}")
        return backup_path
    except Exception as e:
        logger.warning(f"Backup failed for {source}: {e}")
        return None

def restore_file(backup_path: Path, original_path: Path) -> bool:
    """Restore a previously backed-up file to its original location."""
    try:
        if not backup_path.exists():
            logger.warning(f"Backup not found: {backup_path}")
            return False
        shutil.copy2(backup_path, original_path)
        logger.info(f"Restored {original_path.name} from backup")
        return True
    except Exception as e:
        logger.warning(f"Restore failed: {e}")
        return False

def file_hash(path: Path) -> str:
    """Fast partial hash for dedup cache: first 64KB + last 64KB + file size.

    This is much faster than full SHA-256 on large files while still
    reliably detecting different files.
    """
    h = hashlib.sha256()
    size = path.stat().st_size
    h.update(size.to_bytes(8, 'big'))
    chunk_size = 65536
    with open(path, "rb") as f:
        # Read first 64KB
        h.update(f.read(chunk_size))
        # Read last 64KB (skip if file is small enough that we already read it)
        if size > chunk_size:
            f.seek(max(0, size - chunk_size))
            h.update(f.read(chunk_size))
    return h.hexdigest()
