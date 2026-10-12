"""Monocular camera calibration and calibration-file I/O."""

from pathlib import Path
import warnings

import cv2
import numpy as np


def save_calibration(path: str | Path, camera_matrix: np.ndarray, distortion: np.ndarray,
                     image_size: tuple[int, int]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fs = cv2.FileStorage("calibration.yml", cv2.FILE_STORAGE_WRITE | cv2.FILE_STORAGE_MEMORY)
    if not fs.isOpened():
        raise OSError(f"Cannot write calibration file: {path}")
    try:
        fs.write("K", camera_matrix)
        fs.write("D", distortion)
        fs.write("image_width", image_size[0])
        fs.write("image_height", image_size[1])
    finally:
        content = fs.releaseAndGetString()
    path.write_text(content, encoding="utf-8")


def load_calibration(path: str | Path, image_size: tuple[int, int] | None = None
                     ) -> tuple[np.ndarray, np.ndarray]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Camera calibration not found: {path}")
    fs = cv2.FileStorage(path.read_text(encoding="utf-8"),
                         cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY)
    if not fs.isOpened():
        raise FileNotFoundError(f"Camera calibration not found: {path}")
    try:
        K = fs.getNode("K").mat()
        D = fs.getNode("D").mat()
        width = int(fs.getNode("image_width").real()) if not fs.getNode("image_width").empty() else 0
        height = int(fs.getNode("image_height").real()) if not fs.getNode("image_height").empty() else 0
    finally:
        fs.release()
    if K is None or K.shape != (3, 3) or D is None:
        raise ValueError(f"Invalid calibration file: {path}")
    if image_size and width and height:
        sx, sy = image_size[0] / width, image_size[1] / height
        K = K.copy()
        K[0, 0] *= sx
        K[0, 2] *= sx
        K[1, 1] *= sy
        K[1, 2] *= sy
    elif image_size and (not width or not height):
        warnings.warn(
            f"{path} has no calibration image dimensions; using K unchanged. "
            "Verify that it matches the current camera resolution, or recalibrate.",
            RuntimeWarning,
            stacklevel=2,
        )
    return K, D


def calibrate_chessboard(images: list[Path], pattern: tuple[int, int], square_mm: float
                         ) -> tuple[float, np.ndarray, np.ndarray, tuple[int, int], int]:
    if square_mm <= 0:
        raise ValueError("square_mm must be positive")
    cols, rows = pattern
    object_grid = np.zeros((cols * rows, 3), np.float32)
    object_grid[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_mm
    object_points, image_points = [], []
    size = None
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    for image_path in images:
        raw = np.fromfile(image_path, dtype=np.uint8)
        gray = cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE) if raw.size else None
        if gray is None:
            continue
        this_size = (gray.shape[1], gray.shape[0])
        if size and this_size != size:
            raise ValueError("All calibration images must have the same dimensions")
        size = this_size
        found, corners = cv2.findChessboardCorners(gray, pattern)
        if found:
            refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            object_points.append(object_grid)
            image_points.append(refined)
    if len(object_points) < 3 or size is None:
        raise ValueError(f"Need at least three usable chessboard images; found {len(object_points)}")
    rms, K, D, _, _ = cv2.calibrateCamera(object_points, image_points, size, None, None)
    return float(rms), K, D, size, len(object_points)
