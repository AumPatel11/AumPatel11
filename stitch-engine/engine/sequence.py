"""Turn per-object stitches into one ordered list of machine commands.

The stitch generators (running, satin, fill) only know where the needle
goes. This module adds what a real machine needs between objects:

- tie-in / tie-off: 3 tiny stitches (about 0.8 mm) back and forth at the
  start and end of every sewn run, so the thread can't unravel;
- trim: cut the thread when the next object starts more than 3 mm away
  (closer than that, we simply stitch across);
- colour change: stop for a new thread when the thread changes;
- dropping stitches shorter than 0.5 mm, which machines sew badly (they
  can break thread or punch holes).
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np

from .geometry import Points, cumulative_lengths, distance, point_along

TIE_STITCH_MM = 0.8
TRIM_GAP_MM = 3.0
MIN_STITCH_MM = 0.5


class Cmd(str, Enum):
    STITCH = "stitch"  # move to (x, y) and put the needle down
    JUMP = "jump"  # move to (x, y) without sewing
    TRIM = "trim"  # cut the thread
    COLOR_CHANGE = "color_change"  # stop so the next thread can be loaded
    END = "end"  # end of design


@dataclass
class Block:
    """One continuous piece of stitching produced by a design object."""

    object_id: str
    thread_id: str
    points: Points  # (N, 2) needle points in mm, in sewing order


@dataclass
class Command:
    cmd: Cmd
    x: float
    y: float
    object_id: str | None = None  # which design object a stitch belongs to
    thread_id: str | None = None


def sequence(blocks: list[Block]) -> list[Command]:
    """Order the blocks into machine commands, adding ties, trims and colour changes."""
    commands: list[Command] = []
    position = (0.0, 0.0)  # the needle starts at the hoop centre
    thread = None

    for run in _group_into_runs(blocks):
        points, owners = _sew_run(run)
        if len(points) == 0:
            continue

        if commands:
            # The previous run already ended with its tie-off; cut the thread.
            commands.append(Command(Cmd.TRIM, *position))
            if run[0].thread_id != thread:
                commands.append(Command(Cmd.COLOR_CHANGE, *position))

        thread = run[0].thread_id
        commands.append(Command(Cmd.JUMP, *points[0]))
        for (x, y), owner in zip(points, owners, strict=True):
            commands.append(Command(Cmd.STITCH, float(x), float(y), owner, thread))
        position = (float(points[-1][0]), float(points[-1][1]))

    if commands:
        commands.append(Command(Cmd.TRIM, *position))
        commands.append(Command(Cmd.END, *position))
    return commands


def _group_into_runs(blocks: list[Block]) -> list[list[Block]]:
    """Group blocks that can be sewn without cutting the thread.

    A new run starts whenever the thread changes or the gap to the next
    block is over TRIM_GAP_MM.
    """
    runs: list[list[Block]] = []
    for block in blocks:
        if len(block.points) == 0:
            continue
        if runs:
            prev = runs[-1][-1]
            same_thread = prev.thread_id == block.thread_id
            gap = distance(prev.points[-1], block.points[0])
            if same_thread and gap <= TRIM_GAP_MM:
                runs[-1].append(block)
                continue
        runs.append([block])
    return runs


def _sew_run(run: list[Block]) -> tuple[Points, list[str]]:
    """Join a run's blocks, add tie-in and tie-off, then drop short stitches.

    Returns the needle points plus, for each point, the id of the object it
    belongs to (the API uses this to report stitches per object).
    """
    points = np.vstack([b.points for b in run])
    owners = [b.object_id for b in run for _ in range(len(b.points))]

    points, owners = _add_tie_in(points, owners)
    points, owners = _add_tie_off(points, owners)

    keep = drop_short_stitches(points)
    return points[keep], [owners[i] for i in keep]


def _add_tie_in(points: Points, owners: list[str]) -> tuple[Points, list[str]]:
    """Start with 3 short stitches: P0 -> A -> P0 -> A, A being 0.8 mm along the path.

    Sewing then carries on from the first original point past A.
    """
    a = point_along(points, TIE_STITCH_MM)
    tie = np.array([points[0], a, points[0], a])
    # Skip original points the tie stitches already covered.
    rest = np.nonzero(cumulative_lengths(points) > TIE_STITCH_MM + 1e-9)[0]
    first = int(rest[0]) if len(rest) else len(points)
    return (
        np.vstack([tie, points[first:]]),
        [owners[0]] * len(tie) + owners[first:],
    )


def _add_tie_off(points: Points, owners: list[str]) -> tuple[Points, list[str]]:
    """End with 3 short stitches: Pn -> B -> Pn -> B, B being 0.8 mm back along the path."""
    b = point_along(points[::-1], TIE_STITCH_MM)
    tie = np.array([b, points[-1], b])
    return np.vstack([points, tie]), owners + [owners[-1]] * len(tie)


def drop_short_stitches(points: Points, min_len: float = MIN_STITCH_MM) -> list[int]:
    """Indices of the points to keep so that no stitch is shorter than min_len.

    A point is dropped when it is too close to the last kept point. The
    final point is always kept so the run still ends where it should
    (unless the whole run fits inside min_len, which leaves one point).
    """
    if len(points) == 0:
        return []
    keep = [0]
    for i in range(1, len(points)):
        if distance(points[keep[-1]], points[i]) >= min_len:
            keep.append(i)
    last = len(points) - 1
    if keep[-1] != last and len(keep) > 1:
        keep[-1] = last  # swap the too-close point for the true end
    return keep
