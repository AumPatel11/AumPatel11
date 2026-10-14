"""Write a StitchPlan to DST or PES using pyembroidery.

pyembroidery measures in 1/10 mm and, like us, treats +y as down (its DST
writer flips y for the machine), so the only conversion is mm * 10.
"""

import io

import pyembroidery

from .plan import StitchPlan
from .sequence import Cmd

UNITS_PER_MM = 10  # pyembroidery units are 0.1 mm

FORMATS = ("dst", "pes")

_PYEMB_COMMAND = {
    Cmd.STITCH: pyembroidery.STITCH,
    Cmd.JUMP: pyembroidery.JUMP,
    Cmd.TRIM: pyembroidery.TRIM,
    Cmd.COLOR_CHANGE: pyembroidery.COLOR_CHANGE,
    Cmd.END: pyembroidery.END,
}


def to_pattern(plan: StitchPlan) -> pyembroidery.EmbPattern:
    """Build a pyembroidery pattern: one thread per colour block, then every command."""
    pattern = pyembroidery.EmbPattern()
    pattern.metadata("name", plan.design.name)

    # pyembroidery wants one thread entry per colour block, in sewing order,
    # so a design that goes black -> red -> black lists black twice.
    block_threads = []
    pending_change = True
    for c in plan.commands:
        if c.cmd == Cmd.COLOR_CHANGE:
            pending_change = True
        elif c.cmd == Cmd.STITCH and pending_change:
            block_threads.append(plan.design.thread(c.thread_id))
            pending_change = False
    for t in block_threads:
        thread = pyembroidery.EmbThread()
        thread.set_hex_color(t.hex)
        thread.description = t.name
        pattern.add_thread(thread)

    for c in plan.commands:
        x, y = c.x * UNITS_PER_MM, c.y * UNITS_PER_MM
        if c.cmd in (Cmd.STITCH, Cmd.JUMP):
            pattern.add_stitch_absolute(_PYEMB_COMMAND[c.cmd], x, y)
        else:
            # Commands that don't move the needle.
            pattern.add_command(_PYEMB_COMMAND[c.cmd], x, y)
    return pattern


def export_bytes(plan: StitchPlan, fmt: str) -> bytes:
    """The machine file as bytes. fmt is "dst" (Tajima) or "pes" (Brother)."""
    pattern = to_pattern(plan)
    buffer = io.BytesIO()
    if fmt == "dst":
        pyembroidery.write_dst(pattern, buffer)
    elif fmt == "pes":
        pyembroidery.write_pes(pattern, buffer)
    else:
        raise ValueError(f"unknown format {fmt!r}, expected one of {FORMATS}")
    return buffer.getvalue()


def export_file(plan: StitchPlan, path: str) -> None:
    """Write the machine file; the format comes from the extension (.dst or .pes)."""
    fmt = path.rsplit(".", 1)[-1].lower()
    with open(path, "wb") as f:
        f.write(export_bytes(plan, fmt))
