"""Build a stitch test sheet and export it, to sew out and check settings.

    python scripts/test_sheet.py              # writes out/test_sheet.{dst,pes,png,json}
    python scripts/test_sheet.py --out build

Layout on a 150 x 150 mm hoop (top to bottom):
- running stitch at 1.5 / 2.5 / 3.5 mm, plus a 2.5 mm bean stitch
- satin bars: widths 1 / 2.5 / 5 / 7 mm (left to right) at densities
  0.35 / 0.4 / 0.5 mm (top to bottom)
- tatami fill squares at 0.35 / 0.4 / 0.45 mm row spacing (left to right)

Each section uses its own thread colour, so the sheet also exercises
colour changes and trims.
"""

import argparse
import json
import sys
from pathlib import Path

# Make `import engine` work when this file is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import Design, export_file, plan_design, render_png  # noqa: E402

RUNNING_LENGTHS = [1.5, 2.5, 3.5]
SATIN_WIDTHS = [1, 2.5, 5, 7]
SATIN_DENSITIES = [0.35, 0.4, 0.5]
FILL_SPACINGS = [0.35, 0.4, 0.45]


def build_design() -> dict:
    """The test sheet as design JSON (the same format the editor sends)."""
    objects = []

    # Running stitch: 60 mm lines across the top. The whole sheet is centred
    # on the hoop, since the origin is the hoop centre.
    for i, length in enumerate(RUNNING_LENGTHS):
        y = -49 + i * 5
        objects.append(_object(f"running-{length}", "running", "black", [[-30, y], [30, y]], stitchLengthMm=length))
    objects.append(
        _object("bean-2.5", "running", "black", [[-30, -34], [30, -34]], stitchLengthMm=2.5, passes=3),
    )

    # Satin: 28 mm bars, one column per width, one row per density.
    for row, density in enumerate(SATIN_DENSITIES):
        y = -23 + row * 12
        for col, width in enumerate(SATIN_WIDTHS):
            x = -48 + col * 32
            objects.append(
                _object(
                    f"satin-w{width}-d{density}",
                    "satin",
                    "navy",
                    [[x - 14, y], [x + 14, y]],
                    widthMm=width,
                    densityMm=density,
                ),
            )

    # Fill: 30 mm squares with 45 degree rows.
    for col, spacing in enumerate(FILL_SPACINGS):
        x = -40 + col * 40
        square = [[x - 15, 18], [x + 15, 18], [x + 15, 48], [x - 15, 48]]
        objects.append(
            _object(f"fill-{spacing}", "fill", "teal", square, angleDeg=45, densityMm=spacing, stitchLengthMm=4),
        )

    return {
        "version": 1,
        "name": "Test sheet",
        "hoop": {"widthMm": 150, "heightMm": 150},
        "threads": [
            {"id": "black", "name": "Black", "hex": "#1a1a1a"},
            {"id": "navy", "name": "Navy", "hex": "#1d3557"},
            {"id": "teal", "name": "Teal", "hex": "#2a9d8f"},
        ],
        "objects": objects,
    }


def _object(object_id: str, kind: str, thread: str, path: list, **props) -> dict:
    return {"id": object_id, "type": kind, "threadId": thread, "path": path, "props": props}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="out", help="output folder (default: out)")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    design_json = build_design()
    plan = plan_design(Design.model_validate(design_json))

    (out / "test_sheet.json").write_text(json.dumps(design_json, indent=2))
    export_file(plan, str(out / "test_sheet.dst"))
    export_file(plan, str(out / "test_sheet.pes"))
    render_png(plan, str(out / "test_sheet.png"))

    summary = plan.summary()
    for obj in summary["objects"]:
        print(f"  {obj['id']:<18} {obj['stitchCount']:>6} stitches")
    print(
        f"Total: {summary['stitchCount']} stitches, {summary['widthMm']} x {summary['heightMm']} mm, "
        f"{summary['colorChangeCount']} colour changes, {summary['trimCount']} trims"
    )
    print(f"Wrote {out}/test_sheet.dst (+ .pes, .png, .json)")


if __name__ == "__main__":
    main()
