"""Design JSON -> stitches. The one entry point the API, scripts and tests use.

    design = Design.model_validate(json_dict)
    plan = plan_design(design)
    plan.commands      # every machine command, in order
    plan.summary()     # what POST /stitches returns
"""

from dataclasses import dataclass

from .design import Design, RunningObject
from .geometry import as_points
from .running import running_stitch
from .sequence import Block, Cmd, Command, sequence


def object_blocks(obj) -> list[Block]:
    """Stitch one design object. Returns its blocks (usually just one)."""
    if isinstance(obj, RunningObject):
        pts = running_stitch(obj.path, obj.props.stitchLengthMm, obj.props.passes, obj.closed)
        runs = [pts]
    else:
        raise ValueError(f"unsupported object type {obj.type!r}")
    return [Block(obj.id, obj.threadId, as_points(r)) for r in runs if len(r) > 0]


@dataclass
class StitchPlan:
    design: Design
    commands: list[Command]

    def stitches(self) -> list[Command]:
        return [c for c in self.commands if c.cmd == Cmd.STITCH]

    def bounds(self) -> tuple[float, float, float, float]:
        """(min_x, min_y, max_x, max_y) of all needle points, in mm."""
        s = self.stitches()
        if not s:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [c.x for c in s]
        ys = [c.y for c in s]
        return (min(xs), min(ys), max(xs), max(ys))

    def object_segments(self) -> dict[str, list[list[tuple[float, float]]]]:
        """Stitches grouped by object, then into continuous segments.

        A segment is sewn without lifting the needle; the machine jumps
        between segments. Draw each one as its own polyline.
        """
        out: dict[str, list[list[tuple[float, float]]]] = {}
        current = None  # the segment being filled
        current_owner = None
        for c in self.commands:
            if c.cmd != Cmd.STITCH:
                current = None
                continue
            if current is None or c.object_id != current_owner:
                current = []
                current_owner = c.object_id
                out.setdefault(c.object_id, []).append(current)
            current.append((c.x, c.y))
        return out

    def summary(self) -> dict:
        """JSON-friendly result for POST /stitches. Coordinates are rounded to 0.01 mm."""
        min_x, min_y, max_x, max_y = self.bounds()
        segments = self.object_segments()
        objects = []
        for obj in self.design.objects:
            if not obj.visible:
                continue
            segs = [[[round(x, 2), round(y, 2)] for x, y in seg] for seg in segments.get(obj.id, [])]
            objects.append(
                {
                    "id": obj.id,
                    "type": obj.type,
                    "threadId": obj.threadId,
                    "color": self.design.thread(obj.threadId).hex,
                    "stitchCount": sum(len(s) for s in segs),
                    "segments": segs,
                }
            )
        return {
            "name": self.design.name,
            "widthMm": round(max_x - min_x, 2),
            "heightMm": round(max_y - min_y, 2),
            "bounds": {
                "minX": round(min_x, 2),
                "minY": round(min_y, 2),
                "maxX": round(max_x, 2),
                "maxY": round(max_y, 2),
            },
            "stitchCount": len(self.stitches()),
            "trimCount": sum(1 for c in self.commands if c.cmd == Cmd.TRIM),
            "colorChangeCount": sum(1 for c in self.commands if c.cmd == Cmd.COLOR_CHANGE),
            "objects": objects,
        }


def plan_design(design: Design) -> StitchPlan:
    """Stitch every visible object (in list order) and sequence the result."""
    blocks: list[Block] = []
    for obj in design.objects:
        if obj.visible:
            blocks.extend(object_blocks(obj))
    return StitchPlan(design, sequence(blocks))
