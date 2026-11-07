"""Original fixtures test measurements and routing, not AI recognition accuracy."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import ezdxf
import pytest

from luomu_cad.professional import audit, building_line_group, measure, profiles, style_findings, template
from luomu_cad.storage import ROOT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exercise(tmp_path, profile='interior'):
    """One explicit source contour, with other categories outside this exercise."""
    points = [[0, 0], [100, 0], [100, 60], [70, 60], [70, 80], [0, 80], [0, 0]]
    source = tmp_path / 'source.json'
    source.write_text(json.dumps({'contour': points, 'scope': 'Original contour-only measurement exercise'}))
    doc = ezdxf.new()
    doc.units = 4
    doc.layers.new('OUTLINE', dxfattribs={'lineweight': 25})
    entity = doc.modelspace().add_lwpolyline(points[:-1], close=True, dxfattribs={'layer': 'OUTLINE'})
    drawing = tmp_path / 'exercise.dxf'
    doc.saveas(drawing)
    value = template([profile])
    value.update(drawing_sha256=digest(drawing), expected_handles=[entity.dxf.handle],
                 source={'path': source.name, 'sha256': digest(source), 'locator': 'source.json contour'},
                 coordinate_basis='Original explicit XY millimetre exercise coordinates',
                 drawing_type='Synthetic single-contour exercise', stage='measurement test')
    categories = profiles()['category_measurements']
    category = next(c for c in value['categories'] if 'contour' in categories[c])
    for key in value['categories']:
        value['categories'][key] = {'status': 'not_applicable', 'reason': 'Outside explicit contour-only exercise',
                                    'source_locator': 'source.json scope', 'checks': []}
    value['categories'][category] = {'status': 'present', 'source_locator': 'source.json contour', 'checks': ['outline']}
    value['checks'] = [{'id': 'outline', 'kind': 'contour', 'source_locator': 'source.json contour',
                        'handles': [entity.dxf.handle], 'expected_points': points, 'tolerance': .01}]
    value['style'] = {'basis': 'Original exercise style contract, 0.25 mm with zero geometric width',
                      'layers': {'OUTLINE': {'lineweight_mm': [.25, .25], 'linetypes': ['CONTINUOUS'], 'polyline_width': [0, 0]}}}
    evidence = tmp_path / 'review.txt'
    evidence.write_text('Original synthetic contour exercise, reviewed known fixture. No field or recognition test.')
    for row in value['reviews'].values():
        row.update(status='reviewed', finding='Known original fixture matches explicitly limited exercise scope',
                   drawing_sha256=digest(drawing), evidence={'path': evidence.name, 'sha256': digest(evidence)})
    return drawing, value


@pytest.mark.parametrize('profile', [p['id'] for p in profiles()['profiles']])
def test_all_profile_routes_measure_real_dxf_and_reject_changed_contour(tmp_path, profile):
    drawing, value = exercise(tmp_path, profile)
    result = audit(drawing, value, tmp_path)
    assert result['technical_checks_passed'] and result['review_record_complete'], result
    assert not result['recognition_accuracy_proven'] and not result['engineering_approval']
    doc = ezdxf.readfile(drawing)
    entity = next(iter(doc.modelspace()))
    entity.set_points([(0, 0), (100, 0), (100, 80), (0, 80)])
    doc.saveas(drawing)
    value['drawing_sha256'] = digest(drawing)
    result = audit(drawing, value, tmp_path)
    assert 'MEASUREMENT_FAILED:outline' in result['errors']
    assert result['pending_reviews']  # old preview/review cannot cover revised geometry


@pytest.mark.parametrize('fault,code', [
    ('layer_weight', 'LINEWEIGHT:'), ('entity_weight', 'LINEWEIGHT:'),
    ('constant_width', 'POLYLINE_WIDTH:'), ('vertex_width', 'POLYLINE_WIDTH:'),
    ('extra_entity', 'MODEL_INVENTORY_MISMATCH'), ('missing_category', 'CATEGORY_MEASUREMENTS_REQUIRED:'),
    ('stale_drawing', 'PROFESSIONAL_STALE_DRAWING'), ('wrong_units', 'PROFESSIONAL_UNITS_MISMATCH'),
])
def test_real_failure_regressions(tmp_path, fault, code):
    drawing, value = exercise(tmp_path)
    doc = ezdxf.readfile(drawing)
    entity = next(iter(doc.modelspace()))
    if fault == 'layer_weight': doc.layers.get('OUTLINE').dxf.lineweight = 70
    if fault == 'entity_weight': entity.dxf.lineweight = 70
    if fault == 'constant_width': entity.dxf.const_width = 5
    if fault == 'vertex_width': entity[0] = (0, 0, 2, 2, 0)
    if fault == 'extra_entity': doc.modelspace().add_line((0, 0), (1, 0))
    if fault == 'wrong_units': doc.units = 6
    if fault == 'missing_category': value['categories']['doors'] = {'status': 'pending'}
    doc.saveas(drawing)
    if fault != 'stale_drawing': value['drawing_sha256'] = digest(drawing)
    result = audit(drawing, value, tmp_path)
    assert any(e.startswith(code) for e in result['errors']), result


def test_byblock_inheritance_and_scaled_polyline_width():
    doc = ezdxf.new()
    doc.layers.new('PART', dxfattribs={'lineweight': 50})
    block = doc.blocks.new('PART_BLOCK')
    block.add_lwpolyline([(0, 0), (5, 0)], dxfattribs={'lineweight': -2, 'const_width': 2})
    doc.modelspace().add_blockref('PART_BLOCK', (0, 0), dxfattribs={'layer': 'PART', 'xscale': 3, 'yscale': 3})
    result = style_findings(doc, {'basis': 'Fixture', 'layers': {
        'part': {'lineweight_mm': [.5, .5], 'linetypes': ['continuous'], 'polyline_width': [0, 5]}}})
    assert all(e['lineweight_mm'] == .5 for e in result['entities'])
    assert any(e.startswith('POLYLINE_WIDTH:') for e in result['errors'])
    assert result['entities'][-1]['polyline_widths'][0] == 6


def test_building_groups_are_explicit_and_do_not_change_other_industries():
    assert building_line_group(.5) == [.5, .35, .25, .13]
    assert building_line_group(.7) == [.7, .5, .35, .18]
    with pytest.raises(ValueError): building_line_group(.25)
    doc = ezdxf.new()
    doc.layers.new('DETAIL', dxfattribs={'lineweight': 9})
    doc.modelspace().add_line((0, 0), (10, 0), dxfattribs={'layer': 'DETAIL'})
    rule = {'basis': 'Explicit fixture', 'layers': {'DETAIL': {
        'lineweight_mm': [.09, .09], 'linetypes': ['CONTINUOUS'], 'polyline_width': [0, 0]}}}
    assert not style_findings(doc, rule)['errors']
    rule['building_base_mm'] = .5
    assert any(e.startswith('BUILDING_LINE_GROUP:') for e in style_findings(doc, rule)['errors'])


def test_dimensions_distances_closed_area_and_direction():
    doc = ezdxf.new()
    model = doc.modelspace()
    wall = model.add_line((0, 0), (100, 0))
    furniture = model.add_line((20, 30), (80, 30))
    h = [wall.dxf.handle]
    common = {'handles': h, 'tolerance': .01}
    assert measure(doc, {**common, 'kind': 'distance', 'other_handles': [furniture.dxf.handle], 'range': [30, 30]})['passed']
    assert not measure(doc, {**common, 'kind': 'distance', 'other_handles': [furniture.dxf.handle], 'range': [40, 45]})['passed']
    assert measure(doc, {**common, 'kind': 'angle', 'expected': 0, 'angle_tolerance': .1})['passed']
    assert not measure(doc, {**common, 'kind': 'angle', 'expected': 180, 'angle_tolerance': .1})['passed']
    ring = model.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True)
    common['handles'] = [ring.dxf.handle]
    assert measure(doc, {**common, 'kind': 'area', 'range': [5000, 5000]})['passed']
    ring.closed = False
    assert not measure(doc, {**common, 'kind': 'closed', 'expected': True})['passed']
    dim = model.add_linear_dim(base=(0, -20), p1=(0, 0), p2=(100, 0)).dimension
    assert measure(doc, {'kind': 'dimension', 'handles': [dim.dxf.handle], 'range': [100, 100]})['passed']
    dim.dxf.text = '200'
    assert not measure(doc, {'kind': 'dimension', 'handles': [dim.dxf.handle], 'range': [100, 100]})['passed']


def test_curved_contour_and_invalid_source_values():
    doc = ezdxf.new()
    circle = doc.modelspace().add_circle((0, 0), 10)
    import math
    expected = [[10 * math.cos(i * math.pi / 64), 10 * math.sin(i * math.pi / 64)] for i in range(129)]
    check = {'kind': 'contour', 'handles': [circle.dxf.handle], 'expected_points': expected, 'tolerance': .02}
    assert measure(doc, check)['passed']
    check['expected_points'] = [[-10, -10], [10, -10], [10, 10], [-10, 10], [-10, -10]]
    assert not measure(doc, check)['passed']
    check['tolerance'] = float('nan')
    with pytest.raises(ValueError): measure(doc, check)


def test_source_changed_and_template_cannot_pass(tmp_path):
    drawing, value = exercise(tmp_path)
    (tmp_path / 'source.json').write_text('Changed source')
    with pytest.raises(ValueError, match='changed evidence'): audit(drawing, value, tmp_path)
    with pytest.raises(ValueError): audit(drawing, template(['interior']), tmp_path)
    with pytest.raises(ValueError): template(['imagined_industry'])
    assert [p['id'] for p in template(['garment'])['guidance']] == ['garment']


def test_live_snapshot_reader_reports_widths_and_property_gaps():
    from types import SimpleNamespace
    from luomu_cad.presentation_snapshot import capture

    class Collection:
        def __init__(self, rows):
            self.rows = rows
            self.Count = len(rows)

        def Item(self, index):
            return self.rows[index]

    entity = SimpleNamespace(Handle='AB', ObjectName='AcDbPolyline', Layer='PART', Lineweight=-1,
                             Linetype='ByLayer', LinetypeScale=1, Color=256, Coordinates=(0,0,10,0),
                             ConstantWidth=0, GetWidth=lambda i: (i, i))
    layer = SimpleNamespace(Name='PART', Lineweight=25, Linetype='Continuous', Color=7,
                            LayerOn=True, Freeze=False, Plottable=True)
    doc = SimpleNamespace(Layers=Collection([layer]), ModelSpace=Collection([entity]), GetVariable=lambda name: 0)
    retry = lambda fn, **kwargs: fn()
    result = capture(doc, retry)
    assert result['properties_complete'] and not result['settings_changed']
    assert result['model'][0]['VertexWidths'] == [[0,0],[1,1]]
    del entity.ConstantWidth
    result = capture(doc, retry)
    assert not result['properties_complete']
    assert result['issues'][0]['property'] == 'ConstantWidth'
    with pytest.raises(ValueError, match='max_entities'): capture(doc, retry, True)


def test_actual_pdf_has_physical_lineweights_and_page_size(tmp_path):
    from io import BytesIO
    from pypdf import PdfReader
    from pypdf.generic import ContentStream
    from luomu_cad.pdf_export import render_pdf
    doc = ezdxf.new()
    doc.units = 4
    for index, weight in enumerate([13, 25, 50]):
        doc.modelspace().add_line((0, index * 10), (100, index * 10), dxfattribs={'lineweight': weight})
    drawing = tmp_path / 'weights.dxf'
    doc.saveas(drawing)
    data, info = render_pdf(drawing, [210, 297], [-10, -10, 110, 40], 1)
    reader = PdfReader(BytesIO(data))
    page = reader.pages[0]
    assert float(page.mediabox.width) == pytest.approx(210 * 72 / 25.4)
    assert info['scale'] == 1
    widths = [float(args[0]) for args, op in ContentStream(page.get_contents(), reader).operations if op == b'w']
    for mm in [.13, .25, .5]:
        assert any(abs(pt - mm * 72 / 25.4) < .001 for pt in widths), widths


def test_cli_normal_entry_and_pending_review_exit(tmp_path):
    drawing, value = exercise(tmp_path)
    manifest = tmp_path / 'manifest.json'
    report = tmp_path / 'result.json'
    for pending, expected_exit in [(False, 0), (True, 1)]:
        if pending: value['reviews']['sheet_delivery']['status'] = 'pending'
        manifest.write_text(json.dumps(value), encoding='utf-8')
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_professional.py'),
                                 str(drawing), str(manifest), '--report', str(report)], capture_output=True, text=True)
        assert result.returncode == expected_exit, result.stderr
        assert json.loads(report.read_text())['technical_checks_passed']


@pytest.mark.asyncio
async def test_real_stdio_mcp_professional_entry(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from luomu_cad.cli import unpack
    drawing, value = exercise(tmp_path)
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), LUOMU_CAD_ROOT=str(tmp_path), LUOMU_CAD_LIVE_WRITES='0')
    params = StdioServerParameters(command=sys.executable, args=['-m', 'luomu_cad.server'], env=env, cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = unpack(await session.call_tool('workbench_professional', {
                'operation': 'review', 'drawing': str(drawing), 'manifest': value, 'evidence_directory': str(tmp_path)}))
            assert result['technical_checks_passed'], result
            listed = unpack(await session.call_tool('workbench_professional', {'operation': 'profiles'}))
            assert len(listed['profiles']) == 13
