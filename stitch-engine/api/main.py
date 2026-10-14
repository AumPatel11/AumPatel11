"""HTTP API for the stitch engine.

Run it from the stitch-engine folder:

    uvicorn api.main:app --reload

then open http://127.0.0.1:8000/docs for interactive docs.
"""

import re
from typing import Literal

from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.design import Design
from engine.export import export_bytes
from engine.plan import plan_design
from engine.preview import render_png

app = FastAPI(title="Stitch engine", version="0.1.0")

# Let a frontend dev server (Vite, Next, ...) call the API from the browser.
# Tighten allow_origins before deploying anywhere public.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# --- Response shape of POST /stitches (also documents it in /docs) ---------


class Bounds(BaseModel):
    minX: float
    minY: float
    maxX: float
    maxY: float


class ObjectStitches(BaseModel):
    id: str
    type: str
    threadId: str
    color: str  # the thread's hex colour, handy for drawing
    stitchCount: int
    # Continuous runs of [x, y] needle points in mm. Draw each segment as
    # its own polyline; the machine jumps between them. Most objects have
    # exactly one segment.
    segments: list[list[tuple[float, float]]]


class StitchesResponse(BaseModel):
    name: str
    widthMm: float
    heightMm: float
    bounds: Bounds
    stitchCount: int
    trimCount: int
    colorChangeCount: int
    objects: list[ObjectStitches]


# --- Endpoints -------------------------------------------------------------


@app.post("/stitches", response_model=StitchesResponse)
def stitches(design: Design) -> dict:
    """Stitch the design and return the needle points per object plus totals."""
    return plan_design(design).summary()


@app.post("/export")
def export(design: Design, format: Literal["dst", "pes"] = Query(...)) -> Response:
    """Stitch the design and return a DST or PES file to download."""
    data = export_bytes(plan_design(design), format)
    filename = f"{_safe_filename(design.name)}.{format}"
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/preview", response_class=Response)
def preview(design: Design, points: bool = False) -> Response:
    """Render the stitches to a PNG. Pass ?points=true to show every needle point."""
    return Response(content=render_png(plan_design(design), show_points=points), media_type="image/png")


def _safe_filename(name: str) -> str:
    """'Cafe logo!' -> 'Cafe_logo'. Keeps the download header valid."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "design"
