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
python scripts/test_sheet.py      # out/test_sheet.{dst,pes,png,json}
python scripts/render.py examples/cafe_logo.json   # out/cafe_logo.{png,dst,pes}
```

Try the API from a terminal:

```sh
curl -X POST localhost:8000/stitches -H 'content-type: application/json' -d @examples/cafe_logo.json
curl -X POST 'localhost:8000/export?format=dst' -H 'content-type: application/json' \
     -d @examples/cafe_logo.json -o cafe_logo.dst
curl -X POST localhost:8000/preview -H 'content-type: application/json' -d @examples/cafe_logo.json -o preview.png
```

## Test sheet

`scripts/test_sheet.py` builds a sheet for a 150 x 150 mm hoop and sews it
out on one hoop, so you can compare settings on real fabric:

- running stitch at 1.5 / 2.5 / 3.5 mm, plus a 2.5 mm bean stitch
- satin bars 1 / 2.5 / 5 / 7 mm wide (left to right) at 0.35 / 0.4 / 0.5 mm
  density (top to bottom)
- 30 mm tatami squares at 0.35 / 0.4 / 0.45 mm row spacing (left to right)

It writes `test_sheet.dst` (plus `.pes`, a `.png` preview and the design
`.json`, which you can load in the editor).

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

### `fill` (tatami)

The path is the **outline** of the shape and is always treated as closed.

| prop             | default | meaning                                                          |
| ---------------- | ------- | ---------------------------------------------------------------- |
| `angleDeg`       | 45      | row direction, counter-clockwise on screen (0 = —, 45 = /, 90 = \|) |
| `densityMm`      | 0.4     | distance between rows                                            |
| `stitchLengthMm` | 4.0     | stitch length along a row                                        |
| `underlay`       | `true`  | rows at 90° to the fill, 2 mm apart, 0.5 mm inside the edge      |

- Needle points sit on a grid that shifts by 1/3 of a stitch per row
  (brick pattern), so holes never line up into visible grooves.
- Shapes with dents (C, U, E, stars...) are split into regions that can
  each be sewn back and forth. Travel between regions runs inside the
  shape along the shortest route (a visibility graph + Dijkstra).
- The fill starts near the path's first point.
- A path that crosses itself is split into its separate pieces; the
  machine trims between them.

## What the sequencer adds

Applied to every design in `engine/sequence.py`:

- **Tie-in / tie-off**: 3 stitches of 0.8 mm back and forth at the start
  and end of every sewn run.
- **Trim** when the next object starts more than 3 mm away. Closer than
  that, the machine stitches straight across.
- **Colour change** (with a trim) when the thread changes.
- **Short stitches** under 0.5 mm are dropped.

## Decisions worth knowing

These are the judgement calls behind the brief; each is a single constant
at the top of its module if you want to change it.

- **Satin density** is measured peak to peak: the gap between needle
  points on the same side. 0.4 mm gives a solid satin.
- **Pull compensation** adds 0.2 mm to the total satin width (0.1 mm per
  side), not per side.
- **Satin underlay**: the `underlay` prop wins when set; the width rule
  (centre run under 2 mm, else edge run + zigzag) applies for `"auto"` or
  when the prop is missing. The Cafe logo example asks for `"center"`.
- **Fill rows vs the 0.5 mm rule**: rows 0.35–0.45 mm apart would turn at
  an edge with a stitch shorter than 0.5 mm, which the sequencer drops. To
  keep edges clean, each row starts about 0.3 mm in from the edge instead,
  so the turn stitch is just over 0.5 mm. Edges show a slight 0.3 mm
  serration. If your machine handles 0.4 mm stitches, lowering
  `MIN_STITCH_MM` in `engine/sequence.py` gives flush edges.
- **Stitch lengths** may stretch up to 0.5 mm over `stitchLengthMm` next to
  a row end or tie, rather than leaving a stub stitch.
- **Fill on curves**: near where rows run parallel to the edge (for
  example the "top" of a circle) the outer rows are straight chords, so
  the edge looks slightly faceted. That's normal for tatami and is why
  fills are usually outlined with a running or satin border.
- Objects are sewn in list order; there is no automatic reordering yet.

## Layout

```
engine/
  design.py     the design JSON contract (Pydantic models)
  geometry.py   small polyline helpers shared by all stitch types
  running.py    running and bean stitch
  satin.py      satin columns and their underlay
  fill.py       tatami fill, regions, travel inside the shape
  sequence.py   tie-in/off, trims, colour changes, short-stitch removal
  plan.py       design -> per-object stitches -> machine commands
  export.py     DST / PES via pyembroidery
  preview.py    PNG renderer (matplotlib)
api/main.py     FastAPI app
scripts/
  test_sheet.py the test sheet above
  render.py     any design JSON -> PNG + DST + PES
examples/       sample designs
tests/          pytest suite
```
