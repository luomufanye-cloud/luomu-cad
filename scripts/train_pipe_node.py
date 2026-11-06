"""Original simulated pipe-node delivery, measured from saved DXF; no live CAD.

The seal lines demonstrate topology only. Their gap and the assigned minima
are not a tested sealant joint design or a catalogue pipe-fit specification.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import ezdxf
from luomu_cad.qa import file_hash, render_dxf
from luomu_cad.storage import ROOT, atomic_json


POSITIVE = (
    'backing_mm', 'lower_bond_mm', 'membrane_mm', 'upper_bond_mm',
    'tile_mm', 'pipe_od_mm', 'opening_mm', 'pipe_end_x_mm',
    'minimum_annulus_mm', 'minimum_projection_mm', 'band_width_mm',
    'minimum_lap_mm',
)
SIGNED = ('pipe_offset_mm', 'band_offset_mm')
EXPECTED = set(POSITIVE + SIGNED + ('seam_gap_mm',))


def validate(spec):
    if spec.get('simulation_only') is not True or spec.get('units') != 'mm':
        raise ValueError('Explicit simulation_only=true and millimetres required')
    g = spec.get('geometry', {})
    if set(g) != EXPECTED:
        raise ValueError('Complete, recognized geometry inputs required')
    for name, value in g.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Finite numeric geometry required: ' + name)
        if name in POSITIVE and value <= 0:
            raise ValueError('Positive dimension required: ' + name)
    if g['seam_gap_mm'] < 0:
        raise ValueError('Negative seam gap')
    if g['opening_mm'] <= g['pipe_od_mm'] + 2 * abs(g['pipe_offset_mm']):
        raise ValueError('Pipe must remain inside the simulated opening')
    if g['band_width_mm'] <= g['seam_gap_mm'] + 2 * abs(g['band_offset_mm']):
        raise ValueError('Band must reach both sides of the seam')
    if not spec.get('conditions') or not spec.get('parameter_provenance'):
        raise ValueError('Conditions and parameter provenance required')
    return g


def calculate(spec):
    g = validate(spec)
    membrane_x = g['backing_mm'] + g['lower_bond_mm']
    finish_x = membrane_x + g['membrane_mm'] + g['upper_bond_mm'] + g['tile_mm']
    radial = (g['opening_mm'] - g['pipe_od_mm']) / 2
    coverage = (g['band_width_mm'] - g['seam_gap_mm']) / 2
    return {
        'membrane_x_mm': membrane_x, 'finish_x_mm': finish_x,
        'annuli_mm': [radial + g['pipe_offset_mm'], radial - g['pipe_offset_mm']],
        'projection_mm': g['pipe_end_x_mm'] - finish_x,
        'laps_mm': [coverage - g['band_offset_mm'], coverage + g['band_offset_mm']],
    }


def draw(path, spec, defect=None):
    g = validate(spec)
    if defect not in (None, 'missing_upper_connection', 'buried_connection'):
        raise ValueError('Unknown training defect')
    c = calculate(spec)
    doc = ezdxf.new('R2013')
    doc.units = 4
    style = doc.styles.get('Standard')
    style.dxf.font = 'arial.ttf'
    style.set_extended_font_data('Arial')
    m = doc.modelspace()
    doc.appids.add('LUOMU_PIPE_DIM')
    layers = {
        'BACKING': 8, 'LOWER_BOND': 3, 'MEMBRANE': 1, 'UPPER_BOND': 3,
        'FINISH': 4, 'PIPE': 5, 'OPENING_EDGE': 8, 'CONNECTION': 2,
        'PLAN_PIPE': 5, 'PLAN_OPENING': 8, 'SEAM': 1, 'BAND': 2,
        'NOTE': 7, 'DIM': 7,
    }
    for name, color in layers.items():
        doc.layers.add(name, color=color)
    for name, rgb in {'NOTE': 0x222222, 'DIM': 0x333333, 'CONNECTION': 0xA45100,
                      'BAND': 0xA45100, 'FINISH': 0x00757A, 'BACKING': 0x606060,
                      'PLAN_OPENING': 0x606060}.items():
        doc.layers.get(name).dxf.true_color = rgb
    def line(layer, a, b):
        return m.add_line(a, b, dxfattribs={'layer': layer})
    def note(text, position, height=2.5):
        m.add_text(text, dxfattribs={'layer': 'NOTE', 'height': height, 'insert': position})
    def dim(role, a, b, base, angle=0):
        d = m.add_linear_dim(base=base, p1=a, p2=b, angle=angle,
            dimstyle='Standard', dxfattribs={'layer': 'DIM'},
            override={'dimtxt': 2.5, 'dimasz': 1.5, 'dimgap': 0.8,
                      'dimexo': 1, 'dimexe': 1, 'dimscale': 1, 'dimlfac': 1,
                      'dimdec': 4, 'dimdsep': ord('.'),
                      'dimclrd': 250, 'dimclre': 250, 'dimclrt': 250})
        d.render()
        d.dimension.set_xdata('LUOMU_PIPE_DIM', [(1000, role)])
    hole = g['opening_mm'] / 2
    bottom = g['pipe_offset_mm'] - g['pipe_od_mm'] / 2
    top = g['pipe_offset_mm'] + g['pipe_od_mm'] / 2
    bounds = [(0, 'BACKING'), (g['backing_mm'], 'BACKING'),
        (c['membrane_x_mm'], 'MEMBRANE'),
        (c['membrane_x_mm'] + g['membrane_mm'], 'MEMBRANE'),
        (c['finish_x_mm'] - g['tile_mm'], 'UPPER_BOND'), (c['finish_x_mm'], 'FINISH')]
    for x, layer in bounds:
        for a, b in [(-42, -hole), (hole, 42)]:
            line(layer, (x, a), (x, b))
    for y in (-hole, hole):
        line('OPENING_EDGE', (0, y), (c['finish_x_mm'], y))
    for y in (bottom, top):
        line('PIPE', (-15, y), (g['pipe_end_x_mm'], y))
    connection_x = g['backing_mm'] / 2 if defect == 'buried_connection' else c['membrane_x_mm']
    line('CONNECTION', (connection_x, -hole), (connection_x, bottom))
    if defect != 'missing_upper_connection':
        line('CONNECTION', (connection_x, top), (connection_x, hole))
    dim('pipe_od', (g['pipe_end_x_mm'], bottom), (g['pipe_end_x_mm'], top), (g['pipe_end_x_mm'] + 10, 0), 90)
    dim('projection', (c['finish_x_mm'], 42), (g['pipe_end_x_mm'], 42), (0, 52))
    note('A-A SECTION - assigned layers', (-15, 68))
    note('Connections at membrane plane; topology only', (-15, -54), 2)
    note('No sealant section or fit certification', (-15, -59), 2)
    # Orthogonal plan through the wall opening, independent of section placement.
    pc = (190, 0)
    m.add_circle(pc, hole, dxfattribs={'layer': 'PLAN_OPENING'})
    m.add_circle((190, g['pipe_offset_mm']), g['pipe_od_mm'] / 2,
                 dxfattribs={'layer': 'PLAN_PIPE'})
    dim('opening', (190 - hole, 0), (190 + hole, 0), (190, -40))
    note('B PLAN - opening and permanent pipe', (150, 68))
    note('Opening center fixed; pipe offset measured', (145, -54), 2)
    # Two straight seam edges and the original assigned rectangular band.
    center = 390
    gap = g['seam_gap_mm'] / 2
    for x in (center - gap, center + gap):
        line('SEAM', (x, -25), (x, 25))
    lo = center + g['band_offset_mm'] - g['band_width_mm'] / 2
    hi = center + g['band_offset_mm'] + g['band_width_mm'] / 2
    m.add_lwpolyline([(lo, -30), (hi, -30), (hi, 30), (lo, 30)], close=True,
                     dxfattribs={'layer': 'BAND'})
    dim('band_width', (lo, 30), (hi, 30), (center, 52))
    dim('lap_left', (lo, -30), (center - gap, -30), (center, -40))
    dim('lap_right', (center + gap, -30), (hi, -30), (center, -48))
    note('C SEAM - effective overlap each side', (320, 68))
    note('Lap threshold is tied to this exercise', (320, -60), 2)
    note('SIMULATED NODE STUDY / mm / NOT A CONSTRUCTION SPECIFICATION', (-15, 90), 3.5)
    note('Bare fixed metal pipe; non-steam room-temperature scenario', (-15, 82), 2.5)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(path)
    return path


def inspect(path, spec):
    """Read actual saved entities; requirements come from the independent input."""
    g = validate(spec)
    doc = ezdxf.readfile(path)
    m = doc.modelspace()
    issues = []
    tolerance = 1e-6
    def near(a, b): return abs(a - b) <= tolerance
    def point_near(actual, wanted):
        wanted = (*wanted, 0) if len(wanted) == 2 else wanted
        return len(actual) == 3 and all(math.isfinite(float(a)) and near(a, b) for a, b in zip(actual, wanted))
    def lines(layer): return list(m.query(f'LINE[layer=="{layer}"]'))
    def issue(code):
        if code not in issues: issues.append(code)
    def expect_segments(layer, wanted, code):
        actual = [(e.dxf.start, e.dxf.end) for e in lines(layer)]
        for a, b in wanted:
            matched = next((i for i, (x, y) in enumerate(actual)
                            if (point_near(x, a) and point_near(y, b))
                            or (point_near(x, b) and point_near(y, a))), None)
            if matched is None:
                issue(code)
            else:
                actual.pop(matched)
        if actual: issue(code)
    if doc.units != 4: issue('UNITS')
    pipe = lines('PIPE')
    membrane = lines('MEMBRANE')
    finish = lines('FINISH')
    edges = lines('OPENING_EDGE')
    circles = {name: list(m.query(f'CIRCLE[layer=="{name}"]')) for name in ('PLAN_PIPE', 'PLAN_OPENING')}
    band = list(m.query('LWPOLYLINE[layer=="BAND"]'))
    seams = lines('SEAM')
    if (len(pipe) != 2 or len(membrane) != 4 or len(finish) != 2 or len(edges) != 2
            or len(band) != 1 or len(seams) != 2 or any(len(x) != 1 for x in circles.values())):
        return {'ok': False, 'issues': ['ENTITY_INVENTORY'], 'engineering_approval': False}
    all_lines = pipe + membrane + finish + edges + seams + lines('CONNECTION')
    if any(not all(math.isfinite(float(v)) for v in (*e.dxf.start, *e.dxf.end)) for e in all_lines):
        return {'ok': False, 'issues': ['NONFINITE_GEOMETRY'], 'engineering_approval': False}
    if any(not near(e.dxf.start.y, e.dxf.end.y) for e in pipe + edges): issue('SECTION_ALIGNMENT')
    if any(not near(e.dxf.start.x, e.dxf.end.x) for e in membrane + finish + seams): issue('SECTION_ALIGNMENT')
    ys = sorted(e.dxf.start.y for e in pipe)
    opening_ys = sorted(e.dxf.start.y for e in edges)
    mx = min(e.dxf.start.x for e in membrane)
    fx = max(e.dxf.start.x for e in finish)
    ends = [max(e.dxf.start.x, e.dxf.end.x) for e in pipe]
    measured_od, measured_hole = ys[1] - ys[0], opening_ys[1] - opening_ys[0]
    annuli = [ys[0] - opening_ys[0], opening_ys[1] - ys[1]]
    projection = min(ends) - fx
    if not near(ends[0], ends[1]): issue('PIPE_END_ALIGNMENT')
    expected = calculate(spec)
    # Compare complete segments to independent input-derived coordinates.
    # Merely sharing X coordinates does not prove contact with the opening.
    h = g['opening_mm'] / 2
    p0 = g['pipe_offset_mm'] - g['pipe_od_mm'] / 2
    p1 = g['pipe_offset_mm'] + g['pipe_od_mm'] / 2
    intended_mx = expected['membrane_x_mm']
    intended_fx = expected['finish_x_mm']
    for layer, xs in {
            'BACKING': [0, g['backing_mm']],
            'MEMBRANE': [intended_mx, intended_mx + g['membrane_mm']],
            'UPPER_BOND': [intended_fx - g['tile_mm']],
            'FINISH': [intended_fx]}.items():
        expect_segments(layer, [((x, a), (x, b)) for x in xs for a, b in [(-42, -h), (h, 42)]],
                        'SECTION_ENDPOINTS_' + layer)
    expect_segments('PIPE', [((-15, y), (g['pipe_end_x_mm'], y)) for y in (p0, p1)], 'PIPE_ENDPOINTS')
    expect_segments('OPENING_EDGE', [((0, y), (intended_fx, y)) for y in (-h, h)], 'OPENING_ENDPOINTS')
    expect_segments('CONNECTION', [((intended_mx, -h), (intended_mx, p0)),
                                  ((intended_mx, p1), (intended_mx, h))], 'CONNECTION_ENDPOINTS')
    if (not near(measured_od, g['pipe_od_mm']) or not near(measured_hole, g['opening_mm'])
            or not near(sum(ys) / 2, g['pipe_offset_mm']) or not near(sum(opening_ys), 0)
            or not near(mx, expected['membrane_x_mm']) or not near(fx, expected['finish_x_mm'])
            or not all(near(end, g['pipe_end_x_mm']) for end in ends)):
        issue('ASSIGNED_GEOMETRY_CHANGED')
    # Saved layer boundaries must still match each assigned thickness.
    actual_bounds = {
        'BACKING': sorted(set(e.dxf.start.x for e in lines('BACKING'))),
        'MEMBRANE': sorted(set(e.dxf.start.x for e in membrane)),
        'UPPER_BOND': sorted(set(e.dxf.start.x for e in lines('UPPER_BOND'))),
    }
    wanted_bounds = {'BACKING': [0, g['backing_mm']],
        'MEMBRANE': [expected['membrane_x_mm'], expected['membrane_x_mm'] + g['membrane_mm']],
        'UPPER_BOND': [expected['finish_x_mm'] - g['tile_mm']]}
    if any(len(actual_bounds[k]) != len(v) or any(not near(a, b) for a, b in zip(actual_bounds[k], v))
           for k, v in wanted_bounds.items()): issue('LAYER_THICKNESS')
    connections = lines('CONNECTION')
    for a, b in [(opening_ys[0], ys[0]), (ys[1], opening_ys[1])]:
        if not any(near(e.dxf.start.x, mx) and near(e.dxf.end.x, mx)
                   and all(near(x, y) for x, y in zip(sorted([e.dxf.start.y, e.dxf.end.y]), [a, b]))
                   for e in connections): issue('MEMBRANE_CONNECTION')
    if len(connections) != 2: issue('CONNECTION_INVENTORY')
    if min(annuli) < g['minimum_annulus_mm'] - tolerance: issue('ANNULUS_BELOW_ASSIGNED_MINIMUM')
    if projection < g['minimum_projection_mm'] - tolerance: issue('PROJECTION_BELOW_ASSIGNED_MINIMUM')
    cp, co = circles['PLAN_PIPE'][0], circles['PLAN_OPENING'][0]
    if (not near(2 * cp.dxf.radius, measured_od) or not near(2 * co.dxf.radius, measured_hole)
            or not near(cp.dxf.center.y - co.dxf.center.y, sum(ys) / 2)
            or not near(cp.dxf.center.x, co.dxf.center.x)):
        issue('PLAN_SECTION_MISMATCH')
    if (not point_near(cp.dxf.center, (190, g['pipe_offset_mm']))
            or not point_near(co.dxf.center, (190, 0))
            or not point_near(cp.dxf.extrusion, (0, 0, 1))
            or not point_near(co.dxf.extrusion, (0, 0, 1))):
        issue('PLAN_DATUM')
    sx = sorted(e.dxf.start.x for e in seams)
    band_points = list(band[0].get_points('xyseb'))
    if not band_points or any(not math.isfinite(float(v)) for point in band_points for v in point):
        return {'ok': False, 'issues': issues + ['BAND_NONFINITE_OR_EMPTY'], 'engineering_approval': False}
    bx = [p[0] for p in band_points]
    laps = [sx[0] - min(bx), max(bx) - sx[1]]
    if not band[0].closed or len(bx) != 4: issue('BAND_BOUNDARY')
    gap = g['seam_gap_mm'] / 2
    intended_lo = 390 + g['band_offset_mm'] - g['band_width_mm'] / 2
    intended_hi = 390 + g['band_offset_mm'] + g['band_width_mm'] / 2
    expect_segments('SEAM', [((x, -25), (x, 25)) for x in (390 - gap, 390 + gap)], 'SEAM_ENDPOINTS')
    from shapely.geometry import Polygon, LineString
    polygon = Polygon([(p[0], p[1]) for p in band_points]) if len(band_points) >= 3 else Polygon()
    expected_band = Polygon([(intended_lo, -30), (intended_hi, -30), (intended_hi, 30), (intended_lo, 30)])
    if (polygon.is_empty or not polygon.is_valid or not polygon.equals(expected_band)
            or any(any(not near(v, 0) for v in point[2:]) for point in band_points)
            or not near(band[0].dxf.elevation, 0) or not point_near(band[0].dxf.extrusion, (0, 0, 1))):
        issue('BAND_SHAPE_AND_POSITION')
    if not polygon.is_valid or polygon.is_empty or any(not polygon.covers(LineString([
            (e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)])) for e in seams):
        issue('BAND_DOES_NOT_COVER_SEAM')
    if (not near(max(bx) - min(bx), g['band_width_mm']) or not near(sx[1] - sx[0], g['seam_gap_mm'])
            or not near((min(bx) + max(bx) - sx[0] - sx[1]) / 2, g['band_offset_mm'])):
        issue('ASSIGNED_BAND_CHANGED')
    if min(laps) < g['minimum_lap_mm'] - tolerance: issue('LAP_BELOW_ASSIGNED_MINIMUM')
    dims = list(m.query('DIMENSION'))
    measures = []
    # Each measurement is tied to its intended feature, not a sorted bag of values.
    end = g['pipe_end_x_mm']
    roles = {
        'pipe_od': ((end, p0), (end, p1), (end + 10, p0), (end + 10, (p0 + p1) / 2), 90),
        'projection': ((intended_fx, 42), (end, 42), (intended_fx, 52), ((intended_fx + end) / 2, 52), 0),
        'opening': ((190 - h, 0), (190 + h, 0), (190 - h, -40), (190, -40), 0),
        'band_width': ((intended_lo, 30), (intended_hi, 30), (intended_lo, 52), ((intended_lo + intended_hi) / 2, 52), 0),
        'lap_left': ((intended_lo, -30), (390 - gap, -30), (intended_lo, -40), ((intended_lo + 390 - gap) / 2, -40), 0),
        'lap_right': ((390 + gap, -30), (intended_hi, -30), (390 + gap, -48), ((390 + gap + intended_hi) / 2, -48), 0),
    }
    found_roles = set()
    for dim in dims:
        value = dim.get_measurement()
        if not isinstance(value, (int, float)) or not math.isfinite(value): issue('DIMENSION_MEASUREMENT'); continue
        measures.append(value)
        if dim.dxf.get('text', '').strip() not in ('', '<>'): issue('DIMENSION_TEXT_OVERRIDE')
        for key in ('dimlfac', 'dimscale'):
            scale = dim.override().get(key, 1)
            if not isinstance(scale, (int, float)) or not math.isfinite(scale) or not near(scale, 1): issue('DIMENSION_SCALE')
        tags = dim.get_xdata('LUOMU_PIPE_DIM') if dim.has_xdata('LUOMU_PIPE_DIM') else []
        role = tags[0].value if len(tags) == 1 and tags[0].code == 1000 else None
        if role not in roles or role in found_roles:
            issue('DIMENSION_ROLE')
            continue
        found_roles.add(role)
        a, b, base, text_point, angle = roles[role]
        if (dim.dimtype != 0 or not point_near(dim.dxf.defpoint2, a)
                or not point_near(dim.dxf.defpoint3, b) or not point_near(dim.dxf.defpoint, base)
                or not point_near(dim.dxf.text_midpoint, text_point)
                or not near(dim.dxf.get('angle', 0), angle)
                or not point_near(dim.dxf.extrusion, (0, 0, 1))):
            issue('DIMENSION_FEATURE_BINDING')
        block = doc.blocks.get(dim.dxf.get('geometry', ''), default=None)
        if not block:
            issue('DIMENSION_RENDER_BLOCK')
            continue
        texts = list(block.query('TEXT MTEXT'))
        expected_value = math.dist(a, b)
        expected_text = f'{expected_value:.4f}'.rstrip('0').rstrip('.')
        if len(texts) != 1:
            issue('DIMENSION_DISPLAY_TEXT')
        else:
            text = texts[0]
            actual_text = text.plain_text() if text.dxftype() == 'MTEXT' else text.dxf.text
            height = text.dxf.char_height if text.dxftype() == 'MTEXT' else text.dxf.height
            if actual_text != expected_text:
                issue('DIMENSION_DISPLAY_TEXT')
            if (not point_near(text.dxf.insert, text_point) or not near(height, 2.5)
                    or not near(text.dxf.get('rotation', 0), angle)
                    or text.dxf.get('invisible', 0)):
                issue('DIMENSION_DISPLAY_POSITION')
    if found_roles != set(roles): issue('DIMENSION_ROLE_INVENTORY')
    wanted = sorted([measured_od, projection, measured_hole, max(bx) - min(bx), *laps])
    if len(measures) != 6 or any(not near(a, b) for a, b in zip(sorted(measures), wanted)):
        issue('DIMENSION_GEOMETRY')
    auditor = doc.audit()
    if auditor.errors or auditor.fixes: issue('DXF_STRUCTURE')
    return {'ok': not issues, 'issues': issues, 'measurements': {
        'pipe_od_mm': measured_od, 'opening_mm': measured_hole, 'annuli_mm': annuli,
        'projection_mm': projection, 'laps_mm': laps, 'membrane_x_mm': mx, 'finish_x_mm': fx,
        'native_dimensions': measures}, 'sha256': file_hash(path),
        'engineering_approval': False, 'scope': 'Saved original simulation geometry and assigned thresholds only'}


def run(spec, output):
    validate(spec)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    scenarios = [
        ('normal', {}, None, True),
        ('missing_connection', {}, 'missing_upper_connection', False),
        ('buried_connection', {}, 'buried_connection', False),
        ('eccentric_failure', {'pipe_offset_mm': 3}, None, False),
        ('eccentric_repaired', {'pipe_offset_mm': 3, 'opening_mm': 46}, None, True),
        ('finish_failure', {'tile_mm': 18}, None, False),
        ('finish_repaired', {'tile_mm': 18, 'pipe_end_x_mm': 65}, None, True),
        ('lap_failure', {'band_offset_mm': 12}, None, False),
        ('lap_repaired', {'band_offset_mm': 12, 'band_width_mm': 150}, None, True),
    ]
    records = {}
    for name, changes, defect, expected in scenarios:
        case = copy.deepcopy(spec)
        case['geometry'].update(changes)
        atomic_json(output / (name + '-input.json'), case)
        path = draw(output / (name + '.dxf'), case, defect)
        result = inspect(path, case)
        if result['ok'] != expected:
            raise AssertionError((name, result))
        records[name] = {'input_changes': changes, 'injected_defect': defect, 'expected_ok': expected, **result}
    previews = {}
    for name in ('normal', 'eccentric_repaired', 'finish_repaired', 'lap_repaired'):
        previews[name] = render_dxf(output / (name + '.dxf'), output / (name + '.png'))
    result = {'ok': True, 'simulation_only': True, 'cad_contacted': False,
        'engineering_approval': False, 'actual_material_test_performed': False,
        'actual_water_test_performed': False, 'scenarios': records, 'previews': previews,
        'knowledge_questions_assessed': False,
        'scope': 'Original assigned-input plans, sections, dimensions and condition-change diagnosis; independent knowledge review is recorded separately'}
    atomic_json(output / 'results.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, default=ROOT / 'examples/pipe-node-training.json')
    p.add_argument('--output', type=Path, default=ROOT / 'runtime/training/pipe-node')
    args = p.parse_args()
    result = run(json.loads(args.input.read_text(encoding='utf-8-sig')), args.output)
    print(json.dumps({'ok': result['ok'], 'geometry_cases': len(result['scenarios']),
        'result': str((args.output / 'results.json').resolve()), 'cad_contacted': False}))


if __name__ == '__main__': main()
