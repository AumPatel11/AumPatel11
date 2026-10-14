import numpy as np
import pytest
from conftest import stitch_lengths

from engine.plan import plan_design
from engine.sequence import (
    MIN_STITCH_MM,
    TIE_STITCH_MM,
    Block,
    Cmd,
    drop_short_stitches,
    sequence,
)


def line_block(object_id, thread_id, start, end, n=11):
    pts = np.linspace(start, end, n)
    return Block(object_id, thread_id, pts)


def kinds(commands):
    return [c.cmd for c in commands]


def stitch_points(commands):
    return np.array([(c.x, c.y) for c in commands if c.cmd == Cmd.STITCH])


def test_starts_with_a_jump_and_ends_with_trim_and_end():
    cmds = sequence([line_block("a", "t1", (0, 0), (10, 0))])
    assert cmds[0].cmd == Cmd.JUMP
    assert kinds(cmds)[-2:] == [Cmd.TRIM, Cmd.END]


def test_tie_in_is_three_short_stitches_back_and_forth():
    cmds = sequence([line_block("a", "t1", (0, 0), (10, 0))])
    pts = stitch_points(cmds)
    assert np.allclose(pts[:4], [[0, 0], [TIE_STITCH_MM, 0], [0, 0], [TIE_STITCH_MM, 0]])
    assert stitch_lengths(pts[:4]) == pytest.approx([0.8, 0.8, 0.8])


def test_tie_off_is_three_short_stitches_back_and_forth():
    cmds = sequence([line_block("a", "t1", (0, 0), (10, 0))])
    pts = stitch_points(cmds)
    b = 10 - TIE_STITCH_MM
    assert np.allclose(pts[-4:], [[10, 0], [b, 0], [10, 0], [b, 0]])


def test_gap_over_3mm_is_trimmed_and_tied():
    cmds = sequence(
        [
            line_block("a", "t1", (0, 0), (10, 0)),
            line_block("b", "t1", (13.5, 0), (20, 0)),  # 3.5 mm gap
        ]
    )
    assert kinds(cmds).count(Cmd.TRIM) == 2  # between the blocks, and at the end
    assert Cmd.COLOR_CHANGE not in kinds(cmds)
    # The second block starts with a jump and its own tie-in.
    jump = [c for c in cmds if c.cmd == Cmd.JUMP][1]
    assert (jump.x, jump.y) == (13.5, 0)


def test_small_gap_is_stitched_across_without_trim():
    cmds = sequence(
        [
            line_block("a", "t1", (0, 0), (10, 0)),
            line_block("b", "t1", (12, 0), (20, 0)),  # 2 mm gap
        ]
    )
    assert kinds(cmds).count(Cmd.TRIM) == 1  # only the final one
    assert kinds(cmds).count(Cmd.JUMP) == 1  # only the first move from the origin


def test_thread_change_adds_trim_and_colour_change_even_when_close():
    cmds = sequence(
        [
            line_block("a", "t1", (0, 0), (10, 0)),
            line_block("b", "t2", (10.5, 0), (20, 0)),
        ]
    )
    k = kinds(cmds)
    assert k.count(Cmd.COLOR_CHANGE) == 1
    i = k.index(Cmd.COLOR_CHANGE)
    assert k[i - 1] == Cmd.TRIM and k[i + 1] == Cmd.JUMP
    assert cmds[i + 2].thread_id == "t2"


def test_no_stitch_is_shorter_than_half_a_millimetre():
    # Points every 0.2 mm would all be too short.
    cmds = sequence([line_block("a", "t1", (0, 0), (10, 0), n=51)])
    assert stitch_lengths(stitch_points(cmds)).min() >= MIN_STITCH_MM - 1e-9


def test_drop_short_stitches_keeps_first_and_last_point():
    pts = np.array([[0, 0], [0.2, 0], [1, 0], [1.3, 0]])
    assert drop_short_stitches(pts) == [0, 3]
    assert drop_short_stitches(np.array([[0, 0], [0.1, 0]])) == [0]


def test_stitches_are_attributed_to_their_objects(make_design):
    design = make_design(
        {"id": "first", "type": "running", "path": [[0, 0], [10, 0]]},
        {"id": "second", "type": "running", "path": [[11, 0], [20, 0]]},
    )
    segments = plan_design(design).object_segments()
    assert set(segments) == {"first", "second"}
    assert np.allclose(segments["first"][0][0], [0, 0])
    assert np.allclose(segments["second"][-1][-1][0], 20 - TIE_STITCH_MM)


def test_hidden_objects_are_not_stitched(make_design):
    design = make_design(
        {"id": "shown", "type": "running", "path": [[0, 0], [10, 0]]},
        {"id": "hidden", "type": "running", "path": [[0, 5], [10, 5]], "visible": False},
    )
    summary = plan_design(design).summary()
    assert [o["id"] for o in summary["objects"]] == ["shown"]
