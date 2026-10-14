"""Small 2D helpers shared by every stitch type.

Conventions used everywhere in the engine:
- Units are millimetres.
- A "path" is a NumPy array of shape (N, 2): one [x, y] row per point.
- The origin is the hoop centre. +x points right and +y points DOWN,
  the same as SVG and <canvas>, so frontend coordinates can be sent as-is.
"""

import math
from itertools import pairwise

import numpy as np

# Type alias for readability: an (N, 2) array of [x, y] points in mm.
Points = np.ndarray


def as_points(path) -> Points:
    """Turn [[x, y], ...] into an (N, 2) float array, dropping repeated points.

    Repeated points would give zero-length segments, which break direction
    and normal calculations further down.
    """
    pts = np.asarray(path, dtype=float).reshape(-1, 2)
    if len(pts) < 2:
        return pts
    keep = np.ones(len(pts), dtype=bool)
    keep[1:] = np.linalg.norm(np.diff(pts, axis=0), axis=1) > 1e-9
    return pts[keep]


def close_path(pts: Points) -> Points:
    """Append the first point to the end so the path returns to its start."""
    if len(pts) >= 2 and not np.allclose(pts[0], pts[-1]):
        return np.vstack([pts, pts[:1]])
    return pts


def cumulative_lengths(pts: Points) -> np.ndarray:
    """Distance along the path at each point: [0, d1, d1+d2, ...]."""
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(seg)])


def path_length(pts: Points) -> float:
    return float(cumulative_lengths(pts)[-1]) if len(pts) >= 2 else 0.0


def locate(pts: Points, distances) -> tuple[np.ndarray, np.ndarray]:
    """For each distance along the path, which segment it falls in and how far along it.

    Returns (seg, t): distance d lies on segment pts[seg] -> pts[seg + 1],
    a fraction t (0..1) of the way along. Distances are clamped to the path.
    """
    cum = cumulative_lengths(pts)
    d = np.clip(np.atleast_1d(np.asarray(distances, dtype=float)), 0.0, cum[-1])
    seg = np.clip(np.searchsorted(cum, d, side="right") - 1, 0, len(pts) - 2)
    t = (d - cum[seg]) / (cum[seg + 1] - cum[seg])
    return seg, t


def points_at(pts: Points, distances) -> Points:
    """Points at the given distances along the path (clamped to its ends)."""
    if len(pts) < 2:
        return np.repeat(pts[:1], len(np.atleast_1d(distances)), axis=0)
    seg, t = locate(pts, distances)
    return pts[seg] + (pts[seg + 1] - pts[seg]) * t[:, None]


def point_along(pts: Points, distance: float) -> np.ndarray:
    """The single point `distance` mm along the path."""
    return points_at(pts, [distance])[0]


def resample_evenly(pts: Points, max_step: float) -> Points:
    """Spread points evenly along the path so no gap is longer than max_step.

    Both ends are kept. Spreading evenly (instead of stepping exactly
    max_step and leaving a stubby remainder) avoids a tiny last stitch.
    """
    length = path_length(pts)
    if length == 0:
        return pts[:1].copy()
    # The small epsilon stops 10.0 / 2.5 from rounding up to 5 segments.
    n = max(1, math.ceil(length / max_step - 1e-9))
    return points_at(pts, np.linspace(0.0, length, n + 1))


def turn_angles(pts: Points) -> np.ndarray:
    """How sharply the path turns at each interior point, in degrees.

    0 means it carries straight on, 180 means it doubles straight back.
    """
    if len(pts) < 3:
        return np.zeros(0)
    d = np.diff(pts, axis=0)
    d /= np.linalg.norm(d, axis=1)[:, None]
    cos = np.clip(np.sum(d[:-1] * d[1:], axis=1), -1.0, 1.0)
    return np.degrees(np.arccos(cos))


def split_at_corners(pts: Points, corner_deg: float) -> list[Points]:
    """Cut the path into pieces at points where it turns more than corner_deg.

    Neighbouring pieces share the corner point. Gentle bends (for example a
    curve the frontend flattened into many short segments) stay in one piece.
    """
    corners = np.nonzero(turn_angles(pts) > corner_deg)[0] + 1
    bounds = [0, *corners.tolist(), len(pts) - 1]
    return [pts[a : b + 1] for a, b in pairwise(bounds)]


def distance(a, b) -> float:
    return float(math.hypot(b[0] - a[0], b[1] - a[1]))
