"""Stitch any design JSON file and write a preview PNG plus DST and PES files.

    python scripts/render.py examples/cafe_logo.json            # writes to out/
    python scripts/render.py my_design.json --out build --points
"""

import argparse
import json
import sys
from pathlib import Path

# Make `import engine` work when this file is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import Design, export_file, plan_design, render_png  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("design", help="path to a design JSON file")
    parser.add_argument("--out", default="out", help="output folder (default: out)")
    parser.add_argument("--points", action="store_true", help="draw every needle point in the preview")
    args = parser.parse_args()

    design = Design.model_validate(json.loads(Path(args.design).read_text()))
    plan = plan_design(design)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = Path(args.design).stem
    for ext in ("dst", "pes"):
        export_file(plan, str(out / f"{stem}.{ext}"))
    render_png(plan, str(out / f"{stem}.png"), show_points=args.points)

    s = plan.summary()
    print(f"{s['name']}: {s['stitchCount']} stitches, {s['widthMm']} x {s['heightMm']} mm")
    print(f"wrote {out / stem}.dst, .pes and .png")


if __name__ == "__main__":
    main()
