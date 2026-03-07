import json
import logging
from dataclasses import asdict

from clyro.config.schema import Settings
from clyro.utils.paths import get_app_data_dir

logger = logging.getLogger(__name__)

def _coerce_settings(s: Settings) -> Settings:
    """Clamp and type-coerce settings to guard against hand-edited config.json."""
    s.image_jpeg_quality   = max(1,  min(100, int(s.image_jpeg_quality)))
    s.image_webp_quality   = max(1,  min(100, int(s.image_webp_quality)))
    s.image_png_min_quality = max(1, min(100, int(s.image_png_min_quality)))  # correct field name
    s.video_crf            = max(0,  min(51,  int(s.video_crf)))
    s.schema_version = Settings().schema_version
    return s

class SettingsStore:
    def __init__(self):
        self.config_dir = get_app_data_dir()
        self.config_path = self.config_dir / "config.json"
        
    def load(self) -> Settings:
        if not self.config_path.exists():
            return Settings()
            
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            return self._migrate(data)
        except Exception as e:
            logger.error(f"Failed to load settings from {self.config_path}: {e}")
            return Settings()
            
    def save(self, settings: Settings):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(asdict(settings), f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save settings to {self.config_path}: {e}")
            
    def _migrate(self, data: dict) -> Settings:
        current_version = data.get("schema_version", 1)
        
        if current_version < 8:
            logger.info(f"Migrating settings from v{current_version} to v8")
            # For simplicity, if it's an old schema with ~50 fields and distinct structures, 
            # we try to preserve key mappings but mostly reset to defaults since v8 changes 
            # fundamental behavior (e.g. output flow, dropzone).
            
            migrated = Settings()
            
            # General mappings
            if "start_on_login" in data:
                migrated.start_on_login = data["start_on_login"]
            if "show_tray_icon" in data:
                migrated.show_tray = data["show_tray_icon"]
            
            # Output mappings - Old v7 had complex download destinations
            # We'll just reset to `same_folder` by default as it's safe.
            migrated.output_mode = "same_folder"
            
            # Map simple quality scalars if present, otherwise rely on preset
            if "quality_profile" in data:
                qp = data["quality_profile"]
                migrated.quality_preset = qp if qp in ["balanced", "max"] else "balanced"
                
            return _coerce_settings(migrated)
            
        # Parse directly
        # Filter out unknown fields to avoid TypeError in dataclass init
        valid_keys = {k for k in Settings.__annotations__.keys()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        
        try:
            return _coerce_settings(Settings(**filtered_data))
        except Exception as e:
            logger.error(f"Error parsing setting mapping: {e}")
            return Settings()
