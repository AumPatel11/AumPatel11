import io

import pyembroidery
import pytest

from engine.export import export_bytes
from engine.plan import plan_design


@pytest.fixture
def two_colour_plan(make_design):
    design = make_design(
        {"id": "a", "type": "running", "path": [[-20, -10], [20, -10]]},
        {"id": "b", "type": "running", "threadId": "t2", "path": [[-20, 10], [20, 10]], "props": {"passes": 3}},
    )
    return plan_design(design)


def read_back(data: bytes, fmt: str) -> pyembroidery.EmbPattern:
    reader = pyembroidery.read_dst if fmt == "dst" else pyembroidery.read_pes
    return reader(io.BytesIO(data))


@pytest.mark.parametrize("fmt", ["dst", "pes"])
def test_file_reads_back_with_the_same_stitches(two_colour_plan, fmt):
    data = export_bytes(two_colour_plan, fmt)
    pattern = read_back(data, fmt)
    assert pattern.count_stitch_commands(pyembroidery.STITCH) == len(two_colour_plan.stitches())
    assert pattern.count_color_changes() == 1


@pytest.mark.parametrize("fmt", ["dst", "pes"])
def test_positions_survive_in_tenths_of_a_millimetre(two_colour_plan, fmt):
    pattern = read_back(export_bytes(two_colour_plan, fmt), fmt)
    stitches = [s for s in pattern.stitches if s[2] == pyembroidery.STITCH]
    xs = [s[0] for s in stitches]
    ys = [s[1] for s in stitches]
    # 40 mm wide, 20 mm tall: 400 x 200 units.
    assert max(xs) - min(xs) == pytest.approx(400, abs=1)
    assert max(ys) - min(ys) == pytest.approx(200, abs=1)
    # +y is down in both the design and the file, so the first object
    # (y = -10) is still above the second (y = +10).
    assert stitches[0][1] < stitches[-1][1]


def test_pes_keeps_thread_colours(two_colour_plan):
    pattern = read_back(export_bytes(two_colour_plan, "pes"), "pes")
    assert [t.hex_color() for t in pattern.threadlist][:1] == ["#000000"]
    assert len(pattern.threadlist) == 2


def test_dst_starts_with_the_standard_header(two_colour_plan):
    data = export_bytes(two_colour_plan, "dst")
    assert data.startswith(b"LA:Test")
    assert len(data) > 512  # header is exactly 512 bytes, stitches follow


def test_unknown_format_is_rejected(two_colour_plan):
    with pytest.raises(ValueError):
        export_bytes(two_colour_plan, "svg")
