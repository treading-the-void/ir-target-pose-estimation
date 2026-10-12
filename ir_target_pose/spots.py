"""Find bright circular targets in a monochrome infrared image."""

import cv2
import numpy as np

from .settings import DetectionSettings


def detect_spots(frame: np.ndarray, settings: DetectionSettings) -> tuple[np.ndarray, np.ndarray]:
    if frame.ndim == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    if gray.dtype != np.uint8:
        gray = cv2.convertScaleAbs(gray)
    _, binary = cv2.threshold(gray, settings.threshold, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    centers = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not settings.min_area <= area <= settings.max_area:
            continue
        _, radius = cv2.minEnclosingCircle(contour)
        if not settings.min_radius <= radius <= settings.max_radius:
            continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0 or 4 * np.pi * area / (perimeter * perimeter) < settings.min_circularity:
            continue
        moments = cv2.moments(contour)
        if moments["m00"]:
            centers.append([moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]])
    return np.asarray(centers, dtype=np.float32).reshape(-1, 2), binary

