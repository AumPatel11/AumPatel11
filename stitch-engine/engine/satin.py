"""Satin stitch: a smooth column of thread zigzagging across a path.

The path is the centre line of the column. We build two "rails", one each
side of the centre line, and stitch back and forth between them.

Props:
- widthMm: column width.
- densityMm: distance between neighbouring stitches on the same side
  ("peak to peak"). 0.4 mm is a typical dense satin.
- underlay: "auto" (default), "center", "edge" or "none". Underlay is a
  lighter layer sewn first to hold the fabric flat and lift the satin.
  "auto" uses a centre run under 2 mm wide, otherwise an edge run plus a
  light zigzag.

Sewing order: the underlay goes from the start of the path to the end, and
the satin comes back over it, so the object finishes where it started.
"""

import math

import numpy as np

from .geometry import Points, as_points, close_path, locate, path_length
from .running import run_along

# The fabric pulls stitches narrower as they're sewn; make the satin this
# much wider in total (half on each side) to compensate.
PULL_COMP_MM = 0.2

CENTER_UNDERLAY_MAX_WIDTH_MM = 2.0  # below this width "auto" uses a centre run
UNDERLAY_STITCH_MM = 2.0  # stitch length of running underlay
EDGE_INSET_MM = 0.4  # edge run sits this far inside the satin's edges
ZIGZAG_UNDERLAY_SPACING_MM = 2.0  # peak to peak; "light" compared to ~0.4 on top

# At a corner the rails move further out so the column keeps its width
# (like a mitred picture frame). Cap that so very sharp corners don't spike.
MITER_LIMIT = 1.5


def satin_stitches(path, width: float, density: float = 0.4, underlay: str = "auto", closed: bool = False) -> Points:
    """Needle points for a satin column: underlay first, then the satin on top."""
    centre = as_points(path)
    if closed:
        centre = close_path(centre)
    if len(centre) < 2:
        return centre.copy()

    if underlay == "auto":
        underlay = "center" if width < CENTER_UNDERLAY_MAX_WIDTH_MM else "edge"

    parts = satin_underlay(centre, width, underlay, closed)
    top = satin_top(centre, width, density, closed)
    if parts:
        # The underlay ended at the far end of the path: sew the satin back.
        top = top[::-1]
    return np.vstack([*parts, top])


def satin_top(centre: Points, width: float, density: float, closed: bool = False) -> Points:
    """The visible satin, sewn from the start of the path to the end."""
    left, right = rails(centre, (width + PULL_COMP_MM) / 2, closed)
    return zigzag(centre, left, right, density, closed)


def satin_underlay(centre: Points, width: float, kind: str, closed: bool = False) -> list[Points]:
    """Underlay pieces in sewing order. All of them end at the far end of the path."""
    if kind == "none":
        return []
    if kind == "center":
        # A single running stitch down the middle.
        return [run_along(centre, UNDERLAY_STITCH_MM)]
    if kind == "edge":
        # Run up one edge and back down the other, then a light zigzag across.
        left, right = rails(centre, max(width / 2 - EDGE_INSET_MM, 0.1), closed)
        return [
            run_along(left, UNDERLAY_STITCH_MM),
            run_along(right[::-1], UNDERLAY_STITCH_MM),
            zigzag(centre, left, right, ZIGZAG_UNDERLAY_SPACING_MM, closed),
        ]
    raise ValueError(f"unknown underlay {kind!r}")


def rails(centre: Points, half_width: float, closed: bool = False) -> tuple[Points, Points]:
    """The two edges of the column: the centre line pushed half_width to each side.

    Each rail has one point per centre-line point, so point i on the left,
    centre and right rails all line up across the column.
    """
    offsets = _vertex_normals(centre, closed) * half_width
    return centre + offsets, centre - offsets


def zigzag(centre: Points, left: Points, right: Points, spacing: float, closed: bool = False) -> Points:
    """Stitch back and forth between the rails, one pair every `spacing` mm.

    The spacing is measured along the centre line, so it is the distance
    between neighbouring needle points on the same side.
    """
    length = path_length(centre)
    n = max(1, math.ceil(length / spacing - 1e-9))
    distances = np.linspace(0.0, length, n + 1)
    if closed:
        distances = distances[:-1]  # the last pair would repeat the first

    # Find each distance on the centre line, then take the matching spot on
    # each rail (same segment, same fraction along it).
    seg, t = locate(centre, distances)
    t = t[:, None]
    lefts = left[seg] + (left[seg + 1] - left[seg]) * t
    rights = right[seg] + (right[seg + 1] - right[seg]) * t

    # Interleave: L0, R0, L1, R1, ...
    out = np.empty((2 * len(distances), 2))
    out[0::2] = lefts
    out[1::2] = rights
    return out


def _vertex_normals(pts: Points, closed: bool) -> Points:
    """A unit-ish sideways vector at every point of the path.

    Along a straight segment it is simply perpendicular to the segment. At
    a corner it points along the bisector and is lengthened (up to
    MITER_LIMIT) so the column keeps its full width through the corner.
    """
    d = np.diff(pts, axis=0)
    d /= np.linalg.norm(d, axis=1)[:, None]
    seg_normals = np.column_stack([-d[:, 1], d[:, 0]])  # rotate 90 degrees

    normals = np.empty_like(pts)
    normals[0] = seg_normals[0]
    normals[-1] = seg_normals[-1]
    for i in range(1, len(pts) - 1):
        normals[i] = _miter(seg_normals[i - 1], seg_normals[i])
    if closed:
        # The start/end point is a corner too: between the last and first segments.
        normals[0] = normals[-1] = _miter(seg_normals[-1], seg_normals[0])
    return normals


def _miter(n_before: np.ndarray, n_after: np.ndarray) -> np.ndarray:
    bisector = n_before + n_after
    size = np.linalg.norm(bisector)
    if size < 1e-6:  # the path doubles straight back; no sensible corner
        return n_after
    bisector /= size
    # 1 / cos(half the turn angle), capped.
    stretch = 1.0 / max(float(np.dot(bisector, n_after)), 1.0 / MITER_LIMIT)
    return bisector * stretch
