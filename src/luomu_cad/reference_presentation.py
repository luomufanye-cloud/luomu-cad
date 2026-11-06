"""Explicit PDF presentation conversion; never infer drawing semantics."""
import math
from pathlib import Path

from ezdxf.colors import rgb2int, float2transparency
from ezdxf.lldxf.const import VALID_DXF_LINEWEIGHTS


def finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def stroke_attributes(rgb, width_pt, opacity=1, *, tolerance_mm=0.025):
    """PDF width is a paper width, NOT scaled model geometry. Zero is hairline.

    DXF has discrete hundredths-of-mm lineweights. Reject unrepresentable widths
    instead of silently flattening the hierarchy. Dash/clip conversion is separate.
    """
    if len(rgb) != 3 or any(not finite(c) or not 0 <= c <= 1 for c in rgb):
        raise ValueError('Three finite RGB components in [0, 1] required')
    if not finite(opacity) or not 0 <= opacity <= 1:
        raise ValueError('Opacity must be in [0, 1]')
    if not finite(width_pt) or width_pt < 0 or not finite(tolerance_mm) or tolerance_mm < 0:
        raise ValueError('Nonnegative finite width and tolerance required')
    width_mm = width_pt * 25.4 / 72
    choices = [w for w in VALID_DXF_LINEWEIGHTS if w >= 0]
    weight = min(choices, key=lambda w: abs(w / 100 - width_mm))
    if abs(weight / 100 - width_mm) > tolerance_mm:
        raise ValueError('PDF stroke width cannot be represented within tolerance')
    return {'true_color': rgb2int(tuple(round(c * 255) for c in rgb)),
            'lineweight': weight, 'transparency': float2transparency(1 - opacity)}


def measured_text_attributes(transform, *, source_ink_bounds, source_origin,
                             source_direction, target_ink_bounds):
    """Fit editable TEXT to measured ink bounds, not PDF font size/line box.

    Source bounds use baseline-local X/right and Y/up, in source page units.
    Target bounds are measured in the selected font at CAD height=1, width=1.
    The font must be available; a span line-height bbox is NOT an ink bound.
    Returns LEFT-baseline attributes including the measured bearing correction.
    """
    for bounds in (source_ink_bounds, target_ink_bounds):
        if len(bounds) != 4 or any(not finite(v) for v in bounds) or bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
            raise ValueError('Nonempty measured glyph ink bounds required')
    if len(source_direction) != 2 or any(not finite(v) for v in source_direction):
        raise ValueError('Finite text baseline direction required')
    dx, dy = source_direction
    length = math.hypot(dx, dy)
    if length == 0:raise ValueError('Nonzero text direction required')
    dx, dy = dx / length, dy / length * (-1 if transform.flip_y else 1)
    sx0, sy0, sx1, sy1 = source_ink_bounds
    tx0, ty0, tx1, ty1 = target_ink_bounds
    height = (sy1 - sy0) * transform.scale / (ty1 - ty0)
    horizontal = (sx1 - sx0) * transform.scale / (tx1 - tx0)
    local_x = sx0 * transform.scale - tx0 * horizontal
    local_y = sy0 * transform.scale - ty0 * height
    x, y, _ = transform.point(source_origin)
    return {'height': height, 'width': horizontal / height,
            'insert': (x + dx * local_x - dy * local_y, y + dy * local_x + dx * local_y, 0),
            'rotation': math.degrees(math.atan2(dy, dx)) % 360, 'halign': 0, 'valign': 0}


def font_ink_bounds(text, font_path):
    """Measure real glyph outlines. Reject missing glyphs and silent fallback."""
    from fontTools.ttLib import TTFont
    from ezdxf.fonts.fonts import TrueTypeFont
    path = Path(font_path)
    if not path.is_file():raise ValueError('An existing explicit font file is required')
    with TTFont(path, fontNumber=0) as font:
        cmap = font.getBestCmap() or {}
        if any(not c.isspace() and ord(c) not in cmap for c in text):
            raise ValueError('Selected font lacks a required glyph')
    box = TrueTypeFont(str(path), 1).text_path(text).bbox()
    if not box.has_data:raise ValueError('Text has no measurable ink')
    return (*box.extmin, *box.extmax)


def add_solid_fill(modelspace, loops, *, dxfattribs=None):
    """Solid polygon fill with explicit outer/hole roles; no added outline.

    Input loops contain points and role='outer'/'hole'. Curved boundaries,
    clipping and overlapping nonzero-winding paths need their own conversion.
    """
    from shapely.geometry import Polygon
    if not loops or sum(l.get('role') == 'outer' for l in loops) != 1:
        raise ValueError('Exactly one outer polygon and explicit hole roles required')
    if any(l.get('role') not in ('outer', 'hole') for l in loops):
        raise ValueError('Unknown fill loop role')
    outer = next(l['points'] for l in loops if l['role'] == 'outer')
    holes = [l['points'] for l in loops if l['role'] == 'hole']
    if any(len(p) != 2 or any(not finite(v) for v in p) for l in loops for p in l['points']):
        raise ValueError('Finite planar fill points required')
    polygon = Polygon(outer, holes)
    if not polygon.is_valid or polygon.area <= 0:raise ValueError('Invalid fill boundary or hole topology')
    hatch = modelspace.add_hatch(dxfattribs=dxfattribs)
    hatch.dxf.hatch_style = 0
    for loop in loops:
        hatch.paths.add_polyline_path(loop['points'], is_closed=True, flags=1 if loop['role'] == 'outer' else 0)
    return hatch
