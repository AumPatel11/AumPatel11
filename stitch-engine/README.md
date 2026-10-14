# Stitch engine

A Python service that turns a design JSON (vector paths in mm) into
embroidery stitches, and exports Tajima DST and Brother PES files.

## Setup

Needs Python 3.12+.

```sh
cd stitch-engine
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```sh
uvicorn api.main:app --reload     # API on http://127.0.0.1:8000, docs at /docs
pytest                            # unit tests
python scripts/render.py examples/cafe_logo.json   # out/cafe_logo.{png,dst,pes}
```

## Coordinates

- Units are **millimetres**.
- The origin `[0, 0]` is the **hoop centre**.
- **+x is right, +y is down**, the same as SVG and `<canvas>`, so editor
  coordinates can be sent as they are. (pyembroidery uses the same
  convention; the DST writer flips y for the machine.)
- Objects are sewn in the order they appear in `objects`. Objects with
  `"visible": false` are skipped. `locked` and `backdrop` are editor-only.

## API

### `POST /stitches`

Body: a design JSON. Returns:

```jsonc
{
  "name": "Cafe logo",
  "widthMm": 40.0, "heightMm": 15.0,
  "bounds": { "minX": -20, "minY": 10, "maxX": 20, "maxY": 25 },
  "stitchCount": 52, "trimCount": 1, "colorChangeCount": 0,
  "objects": [
    {
      "id": "o1", "type": "running", "threadId": "t1", "color": "#000000",
      "stitchCount": 52,
      // Continuous runs of [x, y] needle points. Draw each as its own
      // polyline; the machine jumps between them. Usually just one.
      "segments": [[[-20, 10], [-19.36, 10.48], ...]]
    }
  ]
}
```

Stitch counts include tie-in and tie-off stitches, so they match the
exported file.

### `POST /export?format=dst|pes`

Body: a design JSON. Returns the machine file as a download.

### `POST /preview`

Body: a design JSON. Returns a PNG of the stitches, at true thread
thickness. Add `?points=true` to mark every needle point.

## Object types

### `running`

| prop             | default | meaning                                         |
| ---------------- | ------- | ----------------------------------------------- |
| `stitchLengthMm` | 2.5     | longest stitch; stitches are spread evenly      |
| `passes`         | 1       | 1 = running stitch, 3 = bean stitch (A→B→A→B)   |

Sharp corners (over 30°) always get a needle point, so corners stay crisp.
`"closed": true` sews back to the first point.

### `satin`

The path is the **centre line** of the column.

| prop        | default  | meaning                                                   |
| ----------- | -------- | --------------------------------------------------------- |
| `widthMm`   | 3.0      | column width (0.2 mm pull compensation is added on top)   |
| `densityMm` | 0.4      | gap between needle points on the same side (peak to peak) |
| `underlay`  | `"auto"` | `"auto"`, `"center"`, `"edge"` or `"none"`                |

- `"auto"` underlay: a centre run below 2 mm wide, otherwise an edge run
  (0.4 mm inside each edge) plus a light zigzag (2 mm peak to peak).
  An explicit value always wins.
- The underlay is sewn from the start of the path to the end and the satin
  comes back over it, so a satin finishes where it started.
- Corners are mitred so the column keeps its width, capped at 1.5x so very
  sharp corners don't spike.
- `"closed": true` makes a ring.

## What the sequencer adds

Applied to every design in `engine/sequence.py`:

- **Tie-in / tie-off**: 3 stitches of 0.8 mm back and forth at the start
  and end of every sewn run.
- **Trim** when the next object starts more than 3 mm away. Closer than
  that, the machine stitches straight across.
- **Colour change** (with a trim) when the thread changes.
- **Short stitches** under 0.5 mm are dropped.

## Layout

```
engine/
  design.py     the design JSON contract (Pydantic models)
  geometry.py   small polyline helpers shared by all stitch types
  running.py    running and bean stitch
  satin.py      satin columns and their underlay
  sequence.py   tie-in/off, trims, colour changes, short-stitch removal
  plan.py       design -> per-object stitches -> machine commands
  export.py     DST / PES via pyembroidery
  preview.py    PNG renderer (matplotlib)
api/main.py     FastAPI app
scripts/        command-line helpers
tests/          pytest suite
```
