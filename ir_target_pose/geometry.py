"""Separate nearby dots into boards and establish template point order."""

from itertools import combinations

import numpy as np


def cluster_spots(points: np.ndarray, eps: float, min_points: int) -> list[np.ndarray]:
    if len(points) < min_points:
        return []
    # With min_samples=2 the original DBSCAN groups points connected by
    # distances <= eps; isolated points are noise. A small graph search gives
    # the same grouping without a scikit-learn runtime dependency.
    near = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2) <= eps
    seen = set()
    groups = []
    for start in range(len(points)):
        if start in seen:
            continue
        stack = [start]
        component = []
        seen.add(start)
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbour in np.flatnonzero(near[current]):
                index = int(neighbour)
                if index not in seen:
                    seen.add(index)
                    stack.append(index)
        if len(component) >= max(2, min_points):
            groups.append(points[sorted(component)])
    return groups


def _line_score(vectors: np.ndarray) -> float:
    if len(vectors) < 2:
        return float("inf")
    unit = vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-6)
    return float(np.sum(1.0 - np.clip(unit @ unit[0], -1.0, 1.0)))


def order_l6(points: np.ndarray) -> np.ndarray:
    """Order the 6-dot L board as corner, three long-arm, two short-arm dots."""
    if len(points) != 6:
        raise ValueError("L6 requires six points")
    best_score = float("inf")
    best_order = None
    # Projective transforms preserve straight lines. Identify the four-point
    # long arm first; angular proximity from a candidate corner alone can pick
    # the opposite end of the short arm in an oblique view.
    for long_group in combinations(range(6), 4):
        long_points = points[list(long_group)]
        center = np.mean(long_points, axis=0)
        _, _, vh = np.linalg.svd(long_points - center, full_matrices=False)
        long_dir = vh[0]
        long_rms = float(np.sqrt(np.mean(((long_points - center) @ vh[1]) ** 2)))
        projected = (long_points - center) @ long_dir
        end_ids = [long_group[i] for i in (int(np.argmin(projected)), int(np.argmax(projected)))]
        short_ids = [i for i in range(6) if i not in long_group]
        for corner in end_ids:
            short_points = points[[corner] + short_ids]
            short_center = np.mean(short_points, axis=0)
            _, _, short_vh = np.linalg.svd(short_points - short_center, full_matrices=False)
            short_rms = float(np.sqrt(np.mean(
                ((short_points - short_center) @ short_vh[1]) ** 2)))
            orthogonality = abs(float(np.dot(long_dir, short_vh[0])))
            score = long_rms + short_rms + 5 * orthogonality
            if score < best_score:
                long_ids = sorted((i for i in long_group if i != corner),
                                  key=lambda i: np.linalg.norm(points[i] - points[corner]))
                short_order = sorted(short_ids,
                                     key=lambda i: np.linalg.norm(points[i] - points[corner]))
                best_order = [corner] + long_ids + short_order
                best_score = score
    return points[best_order]


def _opening_index(points: np.ndarray) -> int:
    """Keep the original C-board heuristic: smallest angle to two nearest dots."""
    angles = []
    for i, point in enumerate(points):
        distance = np.linalg.norm(points - point, axis=1)
        nearest = np.argsort(distance)[1:3]
        a, b = points[nearest] - point
        cosine = np.dot(a, b) / max(np.linalg.norm(a) * np.linalg.norm(b), 1e-6)
        angles.append(np.arccos(np.clip(cosine, -1.0, 1.0)))
    return int(np.argmin(angles))


def order_c(points: np.ndarray) -> np.ndarray:
    """Walk the C-board from its detected opening by nearest neighbours."""
    if len(points) not in (7, 8, 9):
        raise ValueError("C board requires 7, 8, or 9 points")
    first = _opening_index(points)
    order = [first]
    remaining = set(range(len(points))) - {first}
    while remaining:
        next_index = min(remaining, key=lambda i: np.linalg.norm(points[i] - points[order[-1]]))
        order.append(next_index)
        remaining.remove(next_index)
    return points[order]


def order_board(points: np.ndarray) -> tuple[str, np.ndarray]:
    name = {6: "L6", 7: "C7", 8: "C8", 9: "C9"}.get(len(points))
    if name is None:
        raise ValueError(f"Unsupported number of board points: {len(points)}")
    return name, order_l6(points) if name == "L6" else order_c(points)

