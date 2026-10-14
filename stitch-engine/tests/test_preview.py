from engine.plan import plan_design
from engine.preview import render_png

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def test_preview_is_a_png_and_can_be_saved(make_design, tmp_path):
    plan = plan_design(make_design({"id": "a", "type": "running", "path": [[0, 0], [30, 10]]}))
    target = tmp_path / "preview.png"
    data = render_png(plan, str(target), show_points=True)
    assert data.startswith(PNG_SIGNATURE)
    assert target.read_bytes() == data


def test_empty_design_still_renders(make_design):
    assert render_png(plan_design(make_design())).startswith(PNG_SIGNATURE)
