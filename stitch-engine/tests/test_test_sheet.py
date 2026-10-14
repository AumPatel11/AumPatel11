import importlib.util
import sys
from pathlib import Path

import pyembroidery

from engine import Design, plan_design

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "test_sheet.py"


def load_script():
    spec = importlib.util.spec_from_file_location("test_sheet", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_test_sheet_has_every_sample_and_fits_the_hoop():
    sheet = load_script()
    design = Design.model_validate(sheet.build_design())
    ids = [o.id for o in design.objects]
    assert [i for i in ids if i.startswith("running-")] == ["running-1.5", "running-2.5", "running-3.5"]
    assert len([i for i in ids if i.startswith("satin-")]) == 4 * 3
    assert [i for i in ids if i.startswith("fill-")] == ["fill-0.35", "fill-0.4", "fill-0.45"]

    plan = plan_design(design)
    min_x, min_y, max_x, max_y = plan.bounds()
    assert -75 < min_x and max_x < 75 and -75 < min_y and max_y < 75
    assert plan.summary()["colorChangeCount"] == 2


def test_script_writes_the_dst(tmp_path, monkeypatch):
    sheet = load_script()
    monkeypatch.setattr(sys, "argv", ["test_sheet.py", "--out", str(tmp_path)])
    sheet.main()
    pattern = pyembroidery.read(str(tmp_path / "test_sheet.dst"))
    assert pattern.count_stitch_commands(pyembroidery.STITCH) > 5000
    for name in ("test_sheet.pes", "test_sheet.png", "test_sheet.json"):
        assert (tmp_path / name).stat().st_size > 0
