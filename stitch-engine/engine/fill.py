"""Tatami fill: covers a closed shape with rows of running stitches.

Props:
- angleDeg: direction of the rows, counter-clockwise from the +x axis as
  you see it on screen (0 = horizontal, 90 = vertical, 45 = "/").
- densityMm: distance between rows.
- stitchLengthMm: stitch length along a row.
- underlay: sew a light layer first (rows at 90 degrees to the top rows,
  2 mm apart) to stabilise the fabric.

How it works:
1. Rotate the shape so the rows are horizontal (easier maths) and slice it
   with horizontal lines densityMm apart. Each line gives one or more
   segments inside the shape.
2. Group the segments into regions that can each be sewn back and forth in
   one go. A "U" shape, for example, splits into its two arms and the
   bottom.
3. Sew the regions one by one, always picking the nearest next one, and
   travel between them with running stitches that stay inside the shape.
4. Along each row the needle points sit on a grid that shifts by 1/3 of a
   stitch from one row to the next (the "brick" pattern), so the holes
   never line up into visible grooves.
"""

import math

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, Polygon

from .geometry import Points, as_points, distance
from .running import run_along
from .sequence import MIN_STITCH_MM

UNDERLAY_ANGLE_DEG = 90.0  # underlay rows cross the top rows
UNDERLAY_SPACING_MM = 2.0
UNDERLAY_STITCH_MM = 3.0
UNDERLAY_INSET_MM = 0.5  # keep the underlay away from the edges so it can't peek out
BRICK_STEPS = 3  # each row's grid shifts by 1/3 of a stitch


def fill_stitches(
    path, angle_deg: float = 45.0, spacing: float = 0.4, stitch_length: float = 4.0, underlay: bool = True
) -> list[Points]:
    """Needle points for a tatami fill of the closed shape `path`.

    Returns one array per separate piece of the shape: normally one, more
    only if the path crosses itself and splits the shape apart.
    """
    pts = as_points(path)
    position = tuple(pts[0]) if len(pts) else (0.0, 0.0)  # fill starts near the path's first point
    runs = []
    for shape in _polygons(pts):
        sewer = _Sewer(shape, position)
        if underlay:
            for part in _polygon_parts(shape.buffer(-UNDERLAY_INSET_MM)):
                sewer.sew_rows(part, angle_deg + UNDERLAY_ANGLE_DEG, UNDERLAY_SPACING_MM, UNDERLAY_STITCH_MM)
        sewer.sew_rows(shape, angle_deg, spacing, stitch_length)
        if sewer.stitches:
            runs.append(np.array(sewer.stitches))
            position = tuple(sewer.stitches[-1])
    return runs


# --- Sewing --------------------------------------------------------------


class _Sewer:
    """Collects the needle points for one connected shape, in sewing order."""

    def __init__(self, shape: Polygon, start):
        self.router = _Router(shape)
        self.stitches: list[tuple[float, float]] = []
        self.start = start

    @property
    def position(self):
        return self.stitches[-1] if self.stitches else self.start

    def sew_rows(self, area: Polygon, angle_deg: float, spacing: float, stitch_length: float) -> None:
        """Fill `area` with rows at `angle_deg`, region by region."""
        regions = _regions(_scan_rows(area, angle_deg, spacing))
        while regions:
            # Work in the rotated frame, where rows are horizontal. Rotation
            # keeps distances, so "nearest" is the same in both frames.
            here = _rotate(np.array([self.position]), angle_deg)[0]
            i, from_top, start_left = _nearest_entry(regions, here)
            region = regions.pop(i)
            for row in _region_rows(region, from_top, start_left, stitch_length):
                if self.stitches:
                    here = _rotate(np.array([self.position]), angle_deg)[0]
                    row = _ease_turn(row, here)
                row = _rotate(row, -angle_deg)  # back to design coordinates
                self._move_to(row[0], stitch_length)
                self.stitches.extend(map(tuple, row[1:]))

    def _move_to(self, point, max_stitch: float) -> None:
        """Get from the current position to `point` without leaving the shape."""
        point = tuple(point)
        if not self.stitches:
            self.stitches.append(point)
            return
        route = self.router.route(self.stitches[-1], point)
        # run_along also splits long hops into stitches no longer than max_stitch.
        self.stitches.extend(map(tuple, run_along(route, max_stitch)[1:]))


def _scan_rows(area: Polygon, angle_deg: float, spacing: float):
    """Slice the shape into rows. Returns [(row_index, y, [(x0, x1), ...]), ...].

    Coordinates are in the rotated frame where rows are horizontal. The rows
    are centred on the shape, so the first and last rows sit between 1/4 and
    3/4 of a spacing from the edge, where the thread's width covers the gap.
    """
    rotated = affinity.rotate(area, angle_deg, origin=(0, 0))
    min_x, min_y, max_x, max_y = rotated.bounds
    height = max_y - min_y
    n = max(1, round(height / spacing))
    ys = min_y + (height - (n - 1) * spacing) / 2 + np.arange(n) * spacing

    lines = shapely.linestrings([[[min_x - 1, y], [max_x + 1, y]] for y in ys])
    cuts = shapely.intersection(lines, rotated)

    rows = []
    for k, (y, cut) in enumerate(zip(ys, cuts, strict=True)):
        segments = []
        for part in shapely.get_parts(cut):
            if part.geom_type == "LineString" and part.length > 1e-6:
                xs = shapely.get_coordinates(part)[:, 0]
                segments.append((float(xs.min()), float(xs.max())))
        rows.append((k, float(y), _merge_touching(sorted(segments))))
    return rows


def _merge_touching(segments):
    """A row that passes exactly through a corner can come back in two touching pieces."""
    merged = []
    for x0, x1 in segments:
        if merged and x0 - merged[-1][1] < 1e-6:
            merged[-1] = (merged[-1][0], max(x1, merged[-1][1]))
        else:
            merged.append((x0, x1))
    return merged


def _regions(rows):
    """Group row segments into regions that can be sewn back and forth.

    A segment continues the region above it when it overlaps exactly one
    segment in the row above, and that segment overlaps only this one
    below. Anywhere the shape splits or merges, new regions start.
    Each region is a list of (row_index, y, x0, x1), top row first.
    """
    regions = []
    open_regions = []  # (region, segment) pairs that ended on the previous row

    for k, y, segments in rows:
        still_open = []
        for seg in segments:
            above = [(r, s) for r, s in open_regions if _overlaps(s, seg)]
            if len(above) == 1:
                region, above_seg = above[0]
                if sum(_overlaps(above_seg, other) for other in segments) == 1:
                    region.append((k, y, *seg))
                    still_open.append((region, seg))
                    continue
            region = [(k, y, *seg)]
            regions.append(region)
            still_open.append((region, seg))
        open_regions = still_open
    return regions


def _overlaps(a, b) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _nearest_entry(regions, here):
    """Pick the region and the corner to start it from that is closest to `here`.

    A region can start at either end of its first or its last row.
    Returns (region_index, from_top, start_left).
    """
    best = None
    for i, region in enumerate(regions):
        for from_top in (True, False):
            _, y, x0, x1 = region[0] if from_top else region[-1]
            for start_left in (True, False):
                d = distance(here, (x0 if start_left else x1, y))
                if best is None or d < best[0]:
                    best = (d, i, from_top, start_left)
    return best[1:]


def _region_rows(region, from_top: bool, start_left: bool, stitch_length: float):
    """The needle points of each row of a region, alternating direction (rotated frame)."""
    rows = region if from_top else region[::-1]
    left_to_right = start_left
    for k, y, x0, x1 in rows:
        xs = _row_xs(x0, x1, k, stitch_length)
        if not left_to_right:
            xs = xs[::-1]
        yield np.column_stack([xs, np.full(len(xs), y)])
        left_to_right = not left_to_right


def _ease_turn(row: Points, here) -> Points:
    """Keep the hop from the previous row's end to this row's start >= MIN_STITCH_MM.

    Rows are often only 0.35-0.45 mm apart, so hopping straight across at
    the edge would make a stitch the sequencer drops, and the row would
    then start with a long diagonal stitch. Instead we start the row a
    little way in from the edge (about 0.3 mm), just far enough for the
    turn stitch to be exactly MIN_STITCH_MM long.
    """
    target = MIN_STITCH_MM + 0.01  # a hair over, so rounding can't drop it
    start, end = row[0], row[-1]
    gap = start - here
    if len(row) < 2 or np.hypot(*gap) >= target:
        return row
    direction = np.sign(end[0] - start[0])  # rows are horizontal here: +1 or -1
    along = gap[0] * direction
    # Solve |gap + inset * direction| = target for the inset.
    inset = -along + math.sqrt(along**2 - gap @ gap + target**2)
    new_start = start + np.array([inset * direction, 0.0])
    if abs(end[0] - new_start[0]) < MIN_STITCH_MM:
        return row  # row too short to ease; the sequencer tidies it up
    # Drop grid points the new start is now too close to (the end always stays).
    middle = [p for p in row[1:-1] if abs(p[0] - new_start[0]) >= MIN_STITCH_MM]
    return np.array([new_start, *middle, end])


def _row_xs(x0: float, x1: float, row_index: int, stitch_length: float) -> np.ndarray:
    """Needle x positions along one row: both ends plus the brick grid between them.

    The grid is every stitch_length mm, shifted by 1/3 of a stitch per row.
    Grid points that would make a stitch shorter than MIN_STITCH_MM next to
    an end are skipped.
    """
    offset = (row_index % BRICK_STEPS) * stitch_length / BRICK_STEPS
    first = math.ceil((x0 + MIN_STITCH_MM - offset) / stitch_length)
    last = math.floor((x1 - MIN_STITCH_MM - offset) / stitch_length)
    inner = offset + np.arange(first, last + 1) * stitch_length
    return np.concatenate([[x0], inner, [x1]])


def _rotate(points: Points, angle_deg: float) -> Points:
    """Rotate points about the origin; same formula as shapely.affinity.rotate."""
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    x, y = points[:, 0], points[:, 1]
    return np.column_stack([x * c - y * s, x * s + y * c])


# --- Travelling inside the shape -----------------------------------------

MAX_ROUTER_CORNERS = 300  # simplify very detailed outlines to keep routing fast

# Route waypoints sit this far inside the edge. Rows start and end on the
# edge, so every hop onto or off a waypoint is at least this long and the
# sequencer's short-stitch rule can never drop a corner the route needs.
ROUTER_INSET_MM = MIN_STITCH_MM


class _Router:
    """Finds the shortest way between two points without leaving the shape.

    If the straight line stays inside, that's the route. Otherwise we use
    a "visibility graph": the shape's corners, pulled ROUTER_INSET_MM
    inside, are the waypoints; two waypoints are linked when the straight
    line between them stays inside; and Dijkstra's algorithm finds the
    shortest chain of links.
    """

    def __init__(self, shape: Polygon):
        self.shape = shape
        # A hair of tolerance so lines running along the edge count as inside.
        self.area = shape.buffer(0.01)
        shapely.prepare(self.area)
        self._graphs = {}  # inset -> (waypoints, links), built on first use

    def route(self, a, b) -> Points:
        a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
        if self.area.covers(LineString([a, b])):
            return np.array([a, b])

        # Narrow necks close up when the corners are pulled in, so try
        # smaller insets before falling back to the real corners.
        for inset in (ROUTER_INSET_MM, ROUTER_INSET_MM / 2, 0.0):
            waypoints, links = self._graph(inset)
            # Stops: 0 = a, 1 = b, then the waypoints.
            stops = np.vstack([a, b, waypoints])
            weights = np.full((len(stops), len(stops)), np.inf)
            weights[2:, 2:] = links
            for i, p in enumerate((a, b)):
                visible = self._visible(p, waypoints)
                d = np.where(visible, np.linalg.norm(waypoints - p, axis=1), np.inf)
                weights[i, 2:] = d
                weights[2:, i] = d
            order = _shortest_path(weights, 0, 1)
            if order is not None:
                return stops[order]
        return np.array([a, b])  # shouldn't happen for a connected shape

    def _graph(self, inset: float):
        """Waypoints and the distance between every pair that can see each other."""
        if inset not in self._graphs:
            outline = self.shape.buffer(-inset, join_style="mitre") if inset else self.shape
            parts = _polygon_parts(outline)
            waypoints = np.vstack([_corner_points(p) for p in parts]) if parts else np.zeros((0, 2))
            n = len(waypoints)
            i, j = np.triu_indices(n, 1)
            lines = shapely.linestrings(np.stack([waypoints[i], waypoints[j]], axis=1))
            visible = shapely.covers(self.area, lines)
            lengths = np.linalg.norm(waypoints[i] - waypoints[j], axis=1)
            links = np.full((n, n), np.inf)
            links[i[visible], j[visible]] = lengths[visible]
            links[j[visible], i[visible]] = lengths[visible]
            self._graphs[inset] = (waypoints, links)
        return self._graphs[inset]

    def _visible(self, p, waypoints) -> np.ndarray:
        if len(waypoints) == 0:
            return np.zeros(0, dtype=bool)
        starts = np.repeat(p[None, :], len(waypoints), axis=0)
        return shapely.covers(self.area, shapely.linestrings(np.stack([starts, waypoints], axis=1)))


def _corner_points(shape: Polygon) -> Points:
    tolerance = 0.05
    while True:
        simple = shape.simplify(tolerance)
        rings = [simple.exterior, *simple.interiors]
        corners = np.vstack([np.asarray(r.coords)[:-1] for r in rings])
        if len(corners) <= MAX_ROUTER_CORNERS:
            return corners
        tolerance *= 2


def _shortest_path(weights: np.ndarray, start: int, end: int) -> list[int] | None:
    """Dijkstra's algorithm on a dense matrix of link lengths (inf = no link)."""
    n = len(weights)
    dist = np.full(n, np.inf)
    dist[start] = 0.0
    previous = np.full(n, -1)
    done = np.zeros(n, dtype=bool)
    for _ in range(n):
        u = int(np.argmin(np.where(done, np.inf, dist)))
        if dist[u] == np.inf or u == end:
            break
        done[u] = True
        through_u = dist[u] + weights[u]
        better = through_u < dist
        dist[better] = through_u[better]
        previous[better] = u
    if dist[end] == np.inf:
        return None
    order = [end]
    while order[-1] != start:
        order.append(int(previous[order[-1]]))
    return order[::-1]


# --- Shape helpers -------------------------------------------------------


def _polygons(pts: Points) -> list[Polygon]:
    """The closed path as clean polygons (a self-crossing path may give several)."""
    if len(pts) < 3:
        return []
    shape = shapely.make_valid(Polygon(pts))
    return [p for p in _polygon_parts(shape) if p.area > 0.01]


def _polygon_parts(geom) -> list[Polygon]:
    """All polygons inside any shapely geometry (Polygon, MultiPolygon, collections)."""
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    parts = []
    for part in shapely.get_parts(geom):
        if part.geom_type in ("Polygon", "MultiPolygon", "GeometryCollection"):
            parts.extend(_polygon_parts(part))
    return parts
