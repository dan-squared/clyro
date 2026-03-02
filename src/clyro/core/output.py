import os
import logging
from pathlib import Path
from clyro.config.schema import Settings

logger = logging.getLogger(__name__)

def resolve_output_path(source: Path, settings: Settings, is_convert: bool, target_format: str | None = None, override_dir: Path | None = None) -> Path:
    """Determine where to write the output file based on settings."""
    
    stem = source.stem
    if is_convert and target_format:
        ext = f".{target_format.lower()}"
        name = f"{stem}{ext}"
    else:
        ext = source.suffix
        if settings.output_mode == "in_place":
            return source  # overwrite original directly
            
        name = f"{stem}_optimized{ext}"
        
    if override_dir:
        override_dir.mkdir(parents=True, exist_ok=True)
        base_path = override_dir / name
    elif settings.output_mode == "same_folder":
        base_path = source.parent / name
    elif settings.output_mode == "specific_folder":
        folder = Path(settings.output_folder) if settings.output_folder else source.parent
        folder.mkdir(parents=True, exist_ok=True)
        base_path = folder / name
    else:
        # Fallback to same_folder for in_place if something was malconfigured but safe
        base_path = source.parent / name
        
    resolved = _handle_collision(base_path)
    logger.debug(f"Resolved output path: {resolved} (mode={settings.output_mode}, override_dir={override_dir})")
    return resolved

def _handle_collision(path: Path) -> Path:
    """Check if file exists and suffix it with (1), (2), etc."""
    if not path.exists():
        return path
        
    parent = path.parent
    stem = path.stem
    suffix = path.suffix
    
    counter = 1
    new_path = path
    while new_path.exists():
        new_path = parent / f"{stem} ({counter}){suffix}"
        counter += 1
        
    return new_path
