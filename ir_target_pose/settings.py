"""User-editable camera, detection, and board settings."""

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class CameraSettings:
    index: int = 0
    backend: str = "any"
    width: int = 1920
    height: int = 1080
    fps: int = 30
    exposure: float | None = None
    device_name: str | None = None


@dataclass(frozen=True)
class DetectionSettings:
    threshold: int = 60
    min_area: float = 10
    max_area: float = 300
    min_circularity: float = 0.4
    min_radius: float = 2
    max_radius: float = 15
    cluster_eps: float = 40
    min_cluster_points: int = 6


@dataclass(frozen=True)
class PoseSettings:
    max_reprojection_error_px: float = 3.0
    ransac_reprojection_error_px: float = 1.3


@dataclass(frozen=True)
class ProjectSettings:
    camera: CameraSettings
    detection: DetectionSettings
    pose: PoseSettings
    calibration_file: Path
    boards_file: Path


def load_settings(path: str | Path) -> ProjectSettings:
    path = Path(path).resolve()
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    base = path.parent
    calibration = Path(data["calibration_file"])
    boards = Path(data["boards_file"])
    return ProjectSettings(
        camera=CameraSettings(**data.get("camera", {})),
        detection=DetectionSettings(**data.get("detection", {})),
        pose=PoseSettings(**data.get("pose", {})),
        calibration_file=calibration if calibration.is_absolute() else base / calibration,
        boards_file=boards if boards.is_absolute() else base / boards,
    )


def load_boards(path: str | Path) -> dict[str, np.ndarray]:
    with Path(path).open(encoding="utf-8") as stream:
        data = json.load(stream)
    if data.get("units") != "mm":
        raise ValueError("Board coordinates must use millimetres (units: mm).")
    boards = {}
    for name, points in data["boards"].items():
        array = np.asarray(points, dtype=np.float32)
        if array.ndim != 2 or array.shape[1] != 3 or len(array) < 4:
            raise ValueError(f"Invalid board {name}: expected at least four XYZ points")
        boards[name] = array
    return boards


def load_board_colors(path: str | Path) -> dict[str, tuple[int, int, int]]:
    """Read preview colors keyed by board name in OpenCV BGR order."""
    with Path(path).open(encoding="utf-8") as stream:
        data = json.load(stream)
    colors = {}
    for name, value in data.get("colors_bgr", {}).items():
        if name not in data.get("boards", {}):
            raise ValueError(f"Color configured for unknown board: {name}")
        if (not isinstance(value, list) or len(value) != 3
                or any(type(component) is not int or not 0 <= component <= 255
                       for component in value)):
            raise ValueError(f"Invalid BGR color for board {name}: {value}")
        colors[name] = tuple(value)
    return colors

