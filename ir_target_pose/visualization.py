"""Draw target detections in the style of the original infrared preview."""

import cv2
import numpy as np

from .geometry import cluster_spots, order_board
from .pose import BoardPose, euler_zyx_degrees
from .settings import DetectionSettings
from .spots import detect_spots


_BOARD_NAMES = {6: "L6", 7: "C7", 8: "C8", 9: "C9"}
_DEFAULT_COLORS = {"L6": (0, 255, 0), "C7": (0, 255, 255),
                   "C8": (255, 153, 51), "C9": (0, 140, 255)}
_STATUS_COLOR = (255, 255, 0)


def _draw_axes(output: np.ndarray, pose: BoardPose, camera_matrix: np.ndarray,
               distortion: np.ndarray) -> None:
    # The extracted project displays the board coordinate frame at its actual
    # projected origin. Draw it first so the original solid dots remain visible.
    axes_3d = np.float32([[0, 0, 0], [30, 0, 0], [0, 30, 0], [0, 0, -30]])
    axes_2d, _ = cv2.projectPoints(axes_3d, pose.rvec, pose.tvec_mm,
                                   camera_matrix, distortion)
    origin, *ends = np.rint(axes_2d.reshape(-1, 2)).astype(int)
    for end, color in zip(ends, ((0, 0, 255), (0, 255, 0), (255, 0, 0))):
        cv2.line(output, tuple(origin), tuple(end), color, 2)


def annotate(frame: np.ndarray, poses: list[BoardPose], camera_matrix: np.ndarray,
             distortion: np.ndarray, detection: DetectionSettings | None = None,
             mode: str = "idle",
             board_colors: dict[str, tuple[int, int, int]] | None = None) -> np.ndarray:
    """Return a preview with filled dots, group labels, status and board axes."""
    output = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR) if frame.ndim == 2 else frame.copy()
    detection = detection or DetectionSettings()
    board_colors = {**_DEFAULT_COLORS, **(board_colors or {})}
    spots, _ = detect_spots(frame, detection)
    groups = cluster_spots(spots, detection.cluster_eps, detection.min_cluster_points)

    for pose in poses:
        _draw_axes(output, pose, camera_matrix, distortion)

    status_lines = [f"Mode: {mode} | Clusters: {len(groups)} | Points: {sum(map(len, groups))}"]
    for cluster_index, group in enumerate(groups, start=1):
        count = len(group)
        name = _BOARD_NAMES.get(count)
        color = board_colors.get(name, (255, 255, 255))
        ordered = order_board(group)[1] if name else group

        for point_index, (x, y) in enumerate(ordered, start=1):
            cx, cy = int(x), int(y)
            cv2.circle(output, (cx, cy), 4, color, -1)
            cv2.putText(output, str(point_index), (cx + 6, cy + 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        center = np.mean(group, axis=0).astype(int)
        cv2.putText(output, f"G{cluster_index}: {count} pts",
                    (int(center[0]) + 25, int(center[1]) - 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        group_center = np.mean(group, axis=0)
        matching = [pose for pose in poses if len(pose.image_points) == count]
        if matching:
            pose = min(matching, key=lambda item: np.linalg.norm(
                np.mean(item.image_points, axis=0) - group_center))
            if np.linalg.norm(np.mean(pose.image_points, axis=0) - group_center) < detection.cluster_eps:
                x, y, z = pose.tvec_mm.reshape(3)
                rx, ry, rz = euler_zyx_degrees(pose.rotation_matrix)
                status_lines.append(
                    f"Cluster{cluster_index}: Pos({x:.0f},{y:.0f},{z:.0f})mm "
                    f"RotXYZ({rx:.1f},{ry:.1f},{rz:.1f})deg"
                )

    for line_index, line in enumerate(status_lines):
        cv2.putText(output, line, (10, 30 + line_index * 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, _STATUS_COLOR, 2)
    return output
