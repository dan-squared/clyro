from enum import Enum, auto
from dataclasses import dataclass
from typing import Literal
from pathlib import Path

class MediaType(Enum):
    IMAGE = auto()
    VIDEO = auto()
    DOCUMENT = auto() # e.g. PDF
    UNSUPPORTED = auto()

@dataclass
class JobSnapshot:
    id: str
    status: Literal["queued", "processing", "completed", "failed", "cancelled", "cached"]
    progress: float  # 0.0 to 1.0
    command: 'Command'
    result: 'Result | None'
    error_message: str | None

@dataclass
class Result:
    source_path: Path
    output_path: Path
    original_size: int
    optimized_size: int
    resolution: str | None = None
    outcome: Literal["optimized", "unchanged", "skipped_larger", "converted", "merged"] = "optimized"
    detail: str | None = None

    @property
    def reduction_percent(self) -> float:
        if self.original_size == 0:
            return 0.0
        return ((self.original_size - self.optimized_size) / self.original_size) * 100

class Command:
    """Base class for worker commands."""
    path: Path

@dataclass
class OptimiseCommand(Command):
    path: Path
    aggressive: bool
    output_mode: Literal["same_folder", "specific_folder", "in_place"]
    output_dir: Path | None = None

@dataclass
class ConvertCommand(Command):
    path: Path
    target_format: str
    output_mode: Literal["same_folder", "specific_folder", "in_place"]
    output_dir: Path | None = None

@dataclass
class MergeCommand(Command):
    """
    Command for merging multiple files into a single output file.
    The primary path is the first file, which identifies the job in the UI.
    """
    path: Path
    files_to_merge: list[Path]
    target_format: str
    sort_order: str = "none"
    output_mode: Literal["same_folder", "specific_folder", "in_place"] = "same_folder"
    output_dir: Path | None = None

@dataclass
class DropIntent:
    mode: Literal["optimize", "aggressive", "convert", "merge"]
    files: list[Path]
    target_format: str | None = None
