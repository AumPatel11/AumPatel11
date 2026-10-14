"""Running stitch: a dotted line of needle points along a path.

Props:
- stitchLengthMm: the longest stitch allowed.
- passes: 1 for plain running stitch, 3 for bean stitch.
"""

from itertools import pairwise

import numpy as np

from .geometry import Points, as_points, close_path, resample_evenly, split_at_corners

# Turns sharper than this always get a needle point exactly on the corner,
# so sharp corners stay crisp instead of being cut off.
CORNER_DEG = 30.0


def running_stitch(path, stitch_length: float = 2.5, passes: int = 1, closed: bool = False) -> Points:
    """Needle points for a running (or bean) stitch along `path`."""
    pts = as_points(path)
    if closed:
        pts = close_path(pts)
    if len(pts) < 2:
        return pts.copy()

    stitches = run_along(pts, stitch_length)
    if passes == 3:
        stitches = bean(stitches)
    return stitches


def run_along(pts: Points, stitch_length: float) -> Points:
    """Plain running stitch along a polyline.

    The path is cut at its sharp corners, and each piece is resampled so its
    stitches are evenly spaced and no longer than `stitch_length`. Satin
    underlay and fill travel reuse this.
    """
    pieces = split_at_corners(pts, CORNER_DEG)
    out = [pieces[0][:1]]  # the very first point
    for piece in pieces:
        # [1:] skips the first point, which is the previous piece's last.
        out.append(resample_evenly(piece, stitch_length)[1:])
    return np.vstack(out)


def bean(stitches: Points) -> Points:
    """Sew every stitch three times: A->B, back to A, then A->B again.

    The needle reuses the same holes, so the line gets three times the
    thread without getting wider.
    """
    out = [stitches[0]]
    for a, b in pairwise(stitches):
        out.extend([b, a, b])
    return np.array(out)
