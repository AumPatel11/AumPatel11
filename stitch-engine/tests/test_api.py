import io

import pyembroidery
import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

DESIGN = {
    "version": 1,
    "name": "Cafe logo",
    "hoop": {"widthMm": 150, "heightMm": 150},
    "threads": [{"id": "t1", "name": "Black", "hex": "#000000"}],
    "objects": [
        {
            "id": "o1",
            "type": "running",
            "threadId": "t1",
            "path": [[-20, 10], [0, 25], [20, 10]],
            "props": {"stitchLengthMm": 2.5},
        }
    ],
}


def test_stitches_returns_per_object_stitches_and_totals():
    res = client.post("/stitches", json=DESIGN)
    assert res.status_code == 200
    body = res.json()
    assert body["stitchCount"] > 0
    assert body["widthMm"] == pytest.approx(40, abs=0.1)
    assert body["heightMm"] == pytest.approx(15, abs=0.1)
    [obj] = body["objects"]
    assert obj["id"] == "o1" and obj["color"] == "#000000"
    assert obj["stitchCount"] == body["stitchCount"]
    assert obj["segments"][0][0] == [-20, 10]


@pytest.mark.parametrize("fmt", ["dst", "pes"])
def test_export_returns_a_machine_file(fmt):
    res = client.post(f"/export?format={fmt}", json=DESIGN)
    assert res.status_code == 200
    assert res.headers["content-disposition"] == f'attachment; filename="Cafe_logo.{fmt}"'
    reader = pyembroidery.read_dst if fmt == "dst" else pyembroidery.read_pes
    pattern = reader(io.BytesIO(res.content))
    assert pattern.count_stitch_commands(pyembroidery.STITCH) > 0


def test_export_rejects_unknown_formats():
    assert client.post("/export?format=svg", json=DESIGN).status_code == 422
    assert client.post("/export", json=DESIGN).status_code == 422


def test_unknown_thread_is_a_validation_error():
    bad = {**DESIGN, "objects": [{**DESIGN["objects"][0], "threadId": "nope"}]}
    res = client.post("/stitches", json=bad)
    assert res.status_code == 422
    assert "unknown threadId" in res.text


def test_preview_returns_png():
    res = client.post("/preview", json=DESIGN)
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.content.startswith(b"\x89PNG")
