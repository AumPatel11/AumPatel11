import numpy as np
import pytest
from conftest import stitch_lengths

from engine.running import running_stitch


@pytest.mark.parametrize("length", [1.5, 2.5, 3.5])
def test_stitches_are_even_and_never_longer_than_the_stitch_length(length):
    stitches = running_stitch([[0, 0], [40, 0]], stitch_length=length)
    lengths = stitch_lengths(stitches)
    assert lengths.max() <= length + 1e-9
    # Evenly spread: no stubby last stitch.
    assert np.allclose(lengths, lengths[0])
    assert lengths[0] > length * 0.9


def test_path_ends_are_kept_exactly():
    stitches = running_stitch([[-12.3, 4.5], [7.7, -3.1]], stitch_length=2.5)
    assert np.allclose(stitches[0], [-12.3, 4.5])
    assert np.allclose(stitches[-1], [7.7, -3.1])


def test_sharp_corner_gets_a_needle_point():
    # 9 mm then a right-angle turn; 9 isn't a multiple of 2.5.
    stitches = running_stitch([[0, 0], [9, 0], [9, 9]], stitch_length=2.5)
    assert any(np.allclose(p, [9, 0]) for p in stitches)


def test_gentle_curve_is_not_chopped_at_every_vertex():
    # A half circle flattened into 60 tiny segments (3 degrees each).
    angles = np.linspace(0, np.pi, 61)
    arc = np.column_stack([20 * np.cos(angles), 20 * np.sin(angles)])
    stitches = running_stitch(arc, stitch_length=2.5)
    arc_length = np.pi * 20
    assert len(stitches) - 1 == pytest.approx(arc_length / 2.5, abs=1.5)
    assert stitch_lengths(stitches).min() > 2.0


def test_bean_stitch_sews_each_stitch_forward_back_forward():
    single = running_stitch([[0, 0], [10, 0]], stitch_length=2.5)
    bean = running_stitch([[0, 0], [10, 0]], stitch_length=2.5, passes=3)
    assert len(bean) == 3 * (len(single) - 1) + 1
    # The first stitch is sewn A->B, B->A, A->B.
    a, b = single[0], single[1]
    assert np.allclose(bean[:4], [a, b, a, b])
    # Bean stitch follows the same holes as the single run.
    assert np.allclose(bean[::3], single)


def test_closed_path_returns_to_start():
    square = [[0, 0], [10, 0], [10, 10], [0, 10]]
    stitches = running_stitch(square, stitch_length=2.5, closed=True)
    assert np.allclose(stitches[0], stitches[-1])
    # 40 mm perimeter at 2.5 mm per stitch.
    assert len(stitches) - 1 == 16


def test_repeated_points_are_ignored():
    stitches = running_stitch([[0, 0], [0, 0], [5, 0], [5, 0]], stitch_length=2.5)
    assert np.allclose(stitches, [[0, 0], [2.5, 0], [5, 0]])
