import numpy as np
import pytest
from conftest import stitch_lengths

from engine.geometry import as_points
from engine.satin import (
    EDGE_INSET_MM,
    MITER_LIMIT,
    PULL_COMP_MM,
    ZIGZAG_UNDERLAY_SPACING_MM,
    satin_stitches,
    satin_top,
    satin_underlay,
)

STRAIGHT = as_points([[0, 0], [20, 0]])  # 20 mm long, along x


@pytest.mark.parametrize("width", [1, 2.5, 5, 7])
def test_top_stitches_cross_the_column_at_full_width_plus_pull_comp(width):
    top = satin_top(STRAIGHT, width, density=0.4)
    half = (width + PULL_COMP_MM) / 2
    # Needle points alternate sides: +half, -half, +half, ...
    assert np.allclose(top[0::2, 1], half)
    assert np.allclose(top[1::2, 1], -half)


@pytest.mark.parametrize("density", [0.35, 0.4, 0.5])
def test_density_is_the_spacing_between_points_on_the_same_side(density):
    top = satin_top(STRAIGHT, 2.5, density)
    same_side = np.diff(top[0::2, 0])
    assert same_side.max() <= density + 1e-9
    assert same_side.min() > density * 0.9
    # Starts and ends exactly at the ends of the path.
    assert top[0, 0] == 0 and top[-1, 0] == 20


def test_narrow_satin_gets_a_centre_run_underlay():
    [run] = satin_underlay(STRAIGHT, 1.5, "center")
    assert np.allclose(run[:, 1], 0)
    assert run[0, 0] == 0 and run[-1, 0] == 20


def test_wide_satin_gets_edge_runs_and_a_light_zigzag():
    width = 5
    left, right, zz = satin_underlay(STRAIGHT, width, "edge")
    inset_half = width / 2 - EDGE_INSET_MM
    assert np.allclose(np.abs(left[:, 1]), inset_half)
    assert np.allclose(np.abs(right[:, 1]), inset_half)
    # Up one side, back down the other.
    assert left[0, 0] == 0 and left[-1, 0] == 20
    assert right[0, 0] == 20 and right[-1, 0] == 0
    # The zigzag goes back to the far end, crossing the column.
    assert zz[0, 0] == 0 and zz[-1, 0] == 20
    assert np.allclose(np.diff(zz[0::2, 0]), ZIGZAG_UNDERLAY_SPACING_MM)


def test_auto_underlay_picks_by_width():
    narrow = satin_stitches(STRAIGHT, 1.9, underlay="auto")
    wide = satin_stitches(STRAIGHT, 2.0, underlay="auto")
    assert len(narrow) == len(satin_stitches(STRAIGHT, 1.9, underlay="center"))
    assert len(wide) == len(satin_stitches(STRAIGHT, 2.0, underlay="edge"))


def test_explicit_underlay_overrides_auto():
    # The example design asks for a centre run on a 2.5 mm satin.
    with_center = satin_stitches(STRAIGHT, 2.5, underlay="center")
    top_only = satin_stitches(STRAIGHT, 2.5, underlay="none")
    assert len(with_center) == len(top_only) + len(satin_underlay(STRAIGHT, 2.5, "center")[0])


def test_satin_comes_back_over_its_underlay_and_ends_at_the_start():
    stitches = satin_stitches(STRAIGHT, 2.5, underlay="center")
    assert stitches[0, 0] == 0  # starts at the path start
    assert stitches[-1, 0] == pytest.approx(0)  # finishes back there
    # Without underlay the satin simply runs start -> end.
    assert satin_stitches(STRAIGHT, 2.5, underlay="none")[-1, 0] == pytest.approx(20)


def test_corner_keeps_the_column_width_without_spiking():
    # The example "V": a 74 degree turn at (0, 25).
    v = as_points([[-20, 10], [0, 25], [20, 10]])
    width = 2.5
    top = satin_top(v, width, 0.4)
    lengths = stitch_lengths(top)
    assert lengths.min() >= width + PULL_COMP_MM - 1e-6
    assert lengths.max() <= (width + PULL_COMP_MM) * MITER_LIMIT + 0.5


def test_closed_ring_has_no_seam_gap_or_duplicate_pair():
    t = np.linspace(0, 2 * np.pi, 49)[:-1]
    ring = np.column_stack([10 * np.cos(t), 10 * np.sin(t)])
    top = satin_stitches(ring, 3, underlay="none", closed=True)
    # Every needle point sits on one of the two edges.
    radii = np.linalg.norm(top, axis=1)
    half = (3 + PULL_COMP_MM) / 2
    assert np.all((np.abs(radii - (10 - half)) < 0.1) | (np.abs(radii - (10 + half)) < 0.1))
    # The last pair is one step before the first, not on top of it.
    assert not np.allclose(top[-2:], top[:2])
    assert np.linalg.norm(top[-2] - top[0]) < 0.6


def test_example_design_stitches_through_the_api(make_design):
    from engine.plan import plan_design

    design = make_design(
        {
            "id": "o1",
            "type": "satin",
            "path": [[-20, 10], [0, 25], [20, 10]],
            "props": {"widthMm": 2.5, "densityMm": 0.4, "underlay": "center"},
        }
    )
    summary = plan_design(design).summary()
    assert summary["stitchCount"] > 200
    # The end stitches are perpendicular to the 3:4 slope, so each end sticks
    # out sideways by half the width (1.35 mm) times 0.6.
    assert summary["widthMm"] == pytest.approx(40 + 2 * 1.35 * 0.6, abs=0.01)
