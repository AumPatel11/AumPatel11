import numpy as np
import pytest
from conftest import stitch_lengths
from shapely.geometry import LineString, Polygon

from engine.fill import UNDERLAY_INSET_MM, UNDERLAY_SPACING_MM, _rotate, _Router, fill_stitches
from engine.plan import plan_design
from engine.sequence import MIN_STITCH_MM

SQUARE = [[-10, -10], [10, -10], [10, 10], [-10, 10]]
# A "C": the gap on the right means you can't walk straight from the top
# arm to the bottom arm.
C_SHAPE = [[-10, -10], [10, -10], [10, -5], [-4, -5], [-4, 5], [10, 5], [10, 10], [-10, 10]]
_t = np.linspace(0, 2 * np.pi, 11)[:-1]
STAR = np.column_stack(
    [np.where(np.arange(10) % 2 == 0, 14, 6) * np.sin(_t), -np.where(np.arange(10) % 2 == 0, 14, 6) * np.cos(_t)]
).tolist()


def assert_stays_inside(stitches, outline, tolerance=0.05):
    """Every stitch (not just every needle point) lies inside the shape."""
    shape = Polygon(outline).buffer(tolerance)
    outside = [i for i in range(len(stitches) - 1) if not shape.covers(LineString(stitches[i : i + 2]))]
    assert outside == [], f"stitches leaving the shape: {outside[:5]}"


@pytest.mark.parametrize("outline", [SQUARE, C_SHAPE, STAR], ids=["square", "C", "star"])
@pytest.mark.parametrize("underlay", [False, True])
def test_every_stitch_stays_inside_the_shape(outline, underlay):
    [run] = fill_stitches(outline, angle_deg=0, spacing=0.4, stitch_length=4.0, underlay=underlay)
    assert_stays_inside(run, outline)


@pytest.mark.parametrize("spacing", [0.35, 0.4, 0.45])
def test_rows_are_density_apart(spacing):
    [run] = fill_stitches(SQUARE, angle_deg=0, spacing=spacing, underlay=False)
    rows = np.unique(run[:, 1].round(6))
    assert np.allclose(np.diff(rows), spacing)
    # Rows are centred, so the first and last sit well within the shape.
    assert spacing / 4 - 1e-9 <= rows[0] + 10 <= spacing * 3 / 4 + 1e-9


def test_angle_is_counter_clockwise_on_screen():
    # +y is down, so a "/" row goes right and UP: x grows while y shrinks.
    [run] = fill_stitches(SQUARE, angle_deg=45, spacing=0.4, stitch_length=4.0, underlay=False)
    d = np.diff(run, axis=0)
    long_stitches = d[np.linalg.norm(d, axis=1) > 3.9]  # full-length stitches along a row
    slopes = long_stitches[:, 1] / long_stitches[:, 0]
    assert np.allclose(slopes, -1)


def test_stitch_length_along_rows():
    [run] = fill_stitches(SQUARE, angle_deg=0, spacing=0.4, stitch_length=4.0, underlay=False)
    lengths = stitch_lengths(run)
    # Mid-row stitches are exactly the stitch length; the ones next to a row
    # end can stretch by up to MIN_STITCH_MM rather than leave a stub.
    assert lengths.max() <= 4.0 + MIN_STITCH_MM + 1e-9
    assert np.isclose(lengths, 4.0).sum() > len(lengths) / 2


def test_rows_never_turn_with_a_stitch_shorter_than_the_minimum():
    # 0.4 mm rows meeting a square edge would turn with a 0.4 mm stitch,
    # which the sequencer drops; the fill eases the turn to 0.5 mm instead.
    [run] = fill_stitches(SQUARE, angle_deg=0, spacing=0.4, underlay=False)
    assert stitch_lengths(run).min() >= MIN_STITCH_MM


def test_brick_offset_shifts_each_row_by_a_third_of_a_stitch():
    length = 3.0
    [run] = fill_stitches(SQUARE, angle_deg=0, spacing=0.4, stitch_length=length, underlay=False)
    rows = {}
    for x, y in run:
        rows.setdefault(round(y, 6), []).append(x)
    ys = sorted(rows)
    offsets = []
    for y in ys[1:4]:
        # Grid points are the ones not on the square's edges.
        inner = [x for x in rows[y] if abs(abs(x) - 10) > 1]
        offsets.append(round(inner[0] % length, 6))
    # Three consecutive rows: three different offsets, a third of a stitch apart.
    assert sorted(np.round(np.diff(sorted(offsets)), 6)) == [1.0, 1.0]


def test_underlay_is_sewn_first_across_the_rows_and_inside_the_edges():
    [run] = fill_stitches(SQUARE, angle_deg=0, spacing=0.4, stitch_length=4.0, underlay=True)
    # With rows at 0 degrees the underlay rows are vertical, 2 mm apart.
    first = run[:30]
    xs = np.unique(first[:, 0].round(6))
    assert np.allclose(np.diff(xs), UNDERLAY_SPACING_MM)
    inner_edge = 10 - UNDERLAY_INSET_MM
    assert np.all(np.abs(first) <= inner_edge + 1e-9)


def test_underlay_can_be_switched_off():
    with_underlay = fill_stitches(SQUARE, underlay=True)[0]
    without = fill_stitches(SQUARE, underlay=False)[0]
    assert len(with_underlay) > len(without)


def test_router_goes_around_the_gap_of_a_c_shape():
    router = _Router(Polygon(C_SHAPE))
    top_tip, bottom_tip = (9, -7.5), (9, 7.5)
    route = router.route(top_tip, bottom_tip)
    assert len(route) > 2  # it had to turn corners
    assert_stays_inside(route, C_SHAPE, tolerance=0.02)
    # Turns happen inside the edge, never in a hop the sequencer would drop.
    assert stitch_lengths(route).min() >= MIN_STITCH_MM
    # A straight line works when nothing is in the way.
    assert len(router.route((-8, -8), (-8, 8))) == 2


def test_rows_in_a_rotated_frame_line_up_with_the_angle():
    [run] = fill_stitches(SQUARE, angle_deg=30, spacing=0.5, underlay=False)
    rotated = _rotate(run, 30)
    # Rotating back by the fill angle makes every row horizontal.
    rows = np.unique(rotated[:, 1].round(6))
    assert np.allclose(np.diff(rows), 0.5)


def test_self_crossing_outline_gives_one_run_per_piece():
    # A bow tie: two triangles touching at the origin.
    bow_tie = [[-10, -5], [10, 5], [10, -5], [-10, 5]]
    runs = fill_stitches(bow_tie, underlay=False)
    assert len(runs) == 2


def test_fill_object_through_the_planner(make_design):
    design = make_design(
        {
            "id": "f",
            "type": "fill",
            "path": C_SHAPE,
            "props": {"angleDeg": 0, "densityMm": 0.4, "stitchLengthMm": 4},
        }
    )
    plan = plan_design(design)
    stitches = np.array([(s.x, s.y) for s in plan.stitches()])
    assert_stays_inside(stitches, C_SHAPE)
    assert plan.summary()["widthMm"] == pytest.approx(20, abs=0.05)


TRICKY_SHAPES = {
    "C": C_SHAPE,
    "E": [[0, 0], [20, 0], [20, 4], [4, 4], [4, 8], [16, 8], [16, 12], [4, 12], [4, 16], [20, 16], [20, 20], [0, 20]],
    "spiral": [
        [0, 0], [30, 0], [30, 30], [5, 30], [5, 10], [20, 10], [20, 20], [15, 20],
        [15, 15], [10, 15], [10, 25], [25, 25], [25, 5], [0, 5],
    ],  # fmt: skip
    # Two squares joined by a 0.8 mm neck: too narrow for the usual route waypoints.
    "neck": [
        [0, 0], [10, 0], [10, 4.6], [20, 4.6], [20, 0], [30, 0],
        [30, 10], [20, 10], [20, 5.4], [10, 5.4], [10, 10], [0, 10],
    ],  # fmt: skip
}


@pytest.mark.parametrize("name", TRICKY_SHAPES)
@pytest.mark.parametrize("angle", [0, 45, 90, 157])
def test_finished_stitches_stay_inside_tricky_shapes(make_design, name, angle):
    """After sequencing too: dropping short stitches must never cut a corner outside."""
    outline = TRICKY_SHAPES[name]
    plan = plan_design(make_design({"id": "f", "type": "fill", "path": outline, "props": {"angleDeg": angle}}))
    assert_stays_inside(np.array([(s.x, s.y) for s in plan.stitches()]), outline)
