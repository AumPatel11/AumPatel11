"""Render a StitchPlan to a PNG so output can be checked without a machine.

Stitches are drawn at true thread thickness (about 0.35 mm), so satin and
fill look solid when the density is right and stripy when it is too open.
Jumps show as dotted grey lines. The y axis points down, as in the editor.
"""

import io

from matplotlib.collections import LineCollection
from matplotlib.figure import Figure  # the pyplot-free API is safe in a web server
from matplotlib.patches import Rectangle

from .plan import StitchPlan
from .sequence import Cmd

THREAD_WIDTH_MM = 0.35
FABRIC_COLOR = "#ebe7de"
MARGIN_MM = 5.0
HEADER_IN = 0.45  # space above the drawing for the title line


def render_png(plan: StitchPlan, path: str | None = None, *, show_points: bool = False, width_px: int = 1600) -> bytes:
    """Draw the plan; returns PNG bytes and also writes them to `path` if given."""
    hoop = plan.design.hoop
    min_x, min_y, max_x, max_y = plan.bounds()
    # Show the whole hoop (centred on the origin) plus anything outside it.
    left = min(-hoop.widthMm / 2, min_x) - MARGIN_MM
    right = max(hoop.widthMm / 2, max_x) + MARGIN_MM
    top = min(-hoop.heightMm / 2, min_y) - MARGIN_MM
    bottom = max(hoop.heightMm / 2, max_y) + MARGIN_MM
    view_w, view_h = right - left, bottom - top

    # Size the figure so 1 mm is the same on both axes and the axes fill it.
    width_in = 8.0
    drawing_h_in = width_in * view_h / view_w
    fig = Figure(figsize=(width_in, drawing_h_in + HEADER_IN), dpi=width_px / width_in)
    ax = fig.add_axes((0, 0, 1, drawing_h_in / (drawing_h_in + HEADER_IN)))
    ax.set_xlim(left, right)
    ax.set_ylim(bottom, top)  # flipped so +y points down
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.add_patch(Rectangle((left, top), view_w, view_h, color=FABRIC_COLOR, zorder=0))

    # Hoop outline and a small cross at the hoop centre.
    ax.add_patch(
        Rectangle(
            (-hoop.widthMm / 2, -hoop.heightMm / 2),
            hoop.widthMm,
            hoop.heightMm,
            fill=False,
            linestyle="--",
            linewidth=0.8,
            edgecolor="#9a958a",
        )
    )
    ax.plot([-2, 2], [0, 0], color="#9a958a", linewidth=0.6)
    ax.plot([0, 0], [-2, 2], color="#9a958a", linewidth=0.6)

    segments, colors, jumps = _segments(plan)
    points_per_mm = width_in * 72 / view_w
    ax.add_collection(
        LineCollection(
            segments,
            colors=colors,
            linewidths=THREAD_WIDTH_MM * points_per_mm,
            capstyle="round",
            joinstyle="round",
        )
    )
    if jumps:
        ax.add_collection(LineCollection(jumps, colors="#7d786e", linewidths=0.5, linestyles=":"))
    if show_points:
        xs = [c.x for c in plan.stitches()]
        ys = [c.y for c in plan.stitches()]
        # White dots with a dark rim show up on any thread colour.
        ax.scatter(xs, ys, s=(0.45 * points_per_mm) ** 2, c="#ffffff", edgecolors="#000000", linewidths=0.3, zorder=3)

    s = plan.summary()
    fig.text(
        0.01,
        1 - (HEADER_IN / 2) / (drawing_h_in + HEADER_IN),
        f"{s['name']}  |  {s['stitchCount']:,} stitches  |  {s['widthMm']:.1f} x {s['heightMm']:.1f} mm  |  "
        f"colour changes: {s['colorChangeCount']}  |  trims: {s['trimCount']}",
        va="center",
        fontsize=10,
    )

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    data = buffer.getvalue()
    if path:
        with open(path, "wb") as f:
            f.write(data)
    return data


def _segments(plan: StitchPlan):
    """Split the command list into sewn polylines (with colours) and jump lines."""
    segments, colors, jumps = [], [], []
    current = None
    position = (0.0, 0.0)
    for c in plan.commands:
        if c.cmd == Cmd.STITCH:
            if current is None:
                current = [position]
                segments.append(current)
                colors.append(plan.design.thread(c.thread_id).hex)
            current.append((c.x, c.y))
            position = (c.x, c.y)
        elif c.cmd == Cmd.JUMP:
            jumps.append([position, (c.x, c.y)])
            position = (c.x, c.y)
            current = None
        else:
            current = None
    return segments, colors, jumps
