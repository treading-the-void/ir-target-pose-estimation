"""PnP pose computation from ordered infrared dots."""

from dataclasses import dataclass

import cv2
import numpy as np


def euler_zyx_degrees(rotation: np.ndarray) -> tuple[float, float, float]:
    """Return roll(X), pitch(Y), yaw(Z) using the original ZYX convention."""
    sy = float(np.hypot(rotation[0, 0], rotation[1, 0]))
    if sy >= 1e-6:
        roll = np.arctan2(rotation[2, 1], rotation[2, 2])
        pitch = np.arctan2(-rotation[2, 0], sy)
        yaw = np.arctan2(rotation[1, 0], rotation[0, 0])
    else:
        roll = np.arctan2(-rotation[1, 2], rotation[1, 1])
        pitch = np.arctan2(-rotation[2, 0], sy)
        yaw = 0.0
    return tuple(float(np.degrees(value)) for value in (roll, pitch, yaw))


@dataclass
class BoardPose:
    board: str
    image_points: np.ndarray
    rvec: np.ndarray
    tvec_mm: np.ndarray
    rotation_matrix: np.ndarray
    reprojection_error_px: float
    inlier_count: int

    def as_dict(self) -> dict:
        return {
            "board": self.board,
            "image_points": self.image_points.tolist(),
            "rvec": self.rvec.reshape(3).tolist(),
            "tvec_mm": self.tvec_mm.reshape(3).tolist(),
            "rotation_matrix": self.rotation_matrix.tolist(),
            "euler_xyz_deg": list(euler_zyx_degrees(self.rotation_matrix)),
            "reprojection_error_px": self.reprojection_error_px,
            "inlier_count": self.inlier_count,
        }


def estimate_pose(board: str, object_points: np.ndarray, image_points: np.ndarray,
                  camera_matrix: np.ndarray, distortion: np.ndarray,
                  ransac_error_px: float = 1.3, max_error_px: float = 3.0) -> BoardPose | None:
    if len(object_points) != len(image_points) or len(image_points) < 4:
        return None
    ok, rvec, tvec, inliers = cv2.solvePnPRansac(
        np.ascontiguousarray(object_points, dtype=np.float32),
        np.ascontiguousarray(image_points, dtype=np.float32),
        camera_matrix, distortion, flags=cv2.SOLVEPNP_IPPE,
        reprojectionError=ransac_error_px, iterationsCount=2000, confidence=0.995,
    )
    if not ok or inliers is None or len(inliers) < 4 or float(tvec[2]) <= 0:
        # Sparse, nearly collinear dot layouts can make RANSAC fail even when
        # all supplied correspondences fit. The final reprojection gate below
        # still rejects a poor direct fit.
        ok, rvec, tvec = cv2.solvePnP(
            np.ascontiguousarray(object_points, dtype=np.float32),
            np.ascontiguousarray(image_points, dtype=np.float32),
            camera_matrix, distortion, flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not ok or float(tvec[2]) <= 0:
            return None
        inliers = np.arange(len(image_points))
    projected, _ = cv2.projectPoints(object_points, rvec, tvec, camera_matrix, distortion)
    error = float(np.mean(np.linalg.norm(image_points - projected.reshape(-1, 2), axis=1)))
    if error > max_error_px:
        return None
    rotation, _ = cv2.Rodrigues(rvec)
    return BoardPose(board, image_points, rvec, tvec, rotation, error, len(inliers))

