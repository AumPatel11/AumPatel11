"""Embroidery stitch engine: design JSON in, stitches and machine files out.

Typical use:

    from engine import Design, plan_design, export_bytes, render_png

    plan = plan_design(Design.model_validate(design_json))
    plan.summary()               # stitches per object, size, stitch count
    export_bytes(plan, "dst")    # Tajima DST file as bytes
    render_png(plan, "out.png")  # preview image
"""

from .design import Design
from .export import export_bytes, export_file
from .plan import StitchPlan, plan_design
from .preview import render_png

__all__ = ["Design", "StitchPlan", "export_bytes", "export_file", "plan_design", "render_png"]
