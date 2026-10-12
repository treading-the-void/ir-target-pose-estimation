"""Infrared frame to one or more board poses."""

import numpy as np

from .calibration import load_calibration
from .geometry import cluster_spots, order_board
from .pose import BoardPose, estimate_pose
from .settings import ProjectSettings, load_board_colors, load_boards
from .spots import detect_spots
from .visualization import annotate


class TargetPoseEstimator:
    def __init__(self, settings: ProjectSettings):
        self.settings = settings
        self.boards = load_boards(settings.boards_file)
        self.board_colors = load_board_colors(settings.boards_file)
        self._image_size = None
        self._K = None
        self._D = None

    @property
    def camera_matrix(self) -> np.ndarray:
        if self._K is None:
            raise RuntimeError("Process a frame before requesting camera intrinsics")
        return self._K

    @property
    def distortion(self) -> np.ndarray:
        if self._D is None:
            raise RuntimeError("Process a frame before requesting camera distortion")
        return self._D

    def process(self, frame: np.ndarray) -> tuple[list[BoardPose], np.ndarray]:
        size = (frame.shape[1], frame.shape[0])
        if size != self._image_size:
            self._K, self._D = load_calibration(self.settings.calibration_file, size)
            self._image_size = size
        spots, binary = detect_spots(frame, self.settings.detection)
        groups = cluster_spots(spots, self.settings.detection.cluster_eps,
                               self.settings.detection.min_cluster_points)
        poses = []
        for group in groups:
            if len(group) not in (6, 7, 8, 9):
                continue
            name, ordered = order_board(group)
            if name not in self.boards:
                continue
            pose = estimate_pose(name, self.boards[name], ordered, self._K, self._D,
                                 self.settings.pose.ransac_reprojection_error_px,
                                 self.settings.pose.max_reprojection_error_px)
            if pose is not None:
                poses.append(pose)
        return poses, binary


