"""Cross-sheet mutations, actual native readback, revision safety and stdio MCP."""
import copy
import json
import os
from pathlib import Path
import sys

import ezdxf
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pypdf import PdfReader

from luomu_cad.cli import unpack
from luomu_cad.qa import file_hash
from luomu_cad.shared_project import build, normalize, project, review, walls, world
from luomu_cad.storage import ROOT


def example():
    return json.loads((ROOT/'examples/shared-project.json').read_text(encoding='utf8'))


def manifest(path):
    return json.loads((path/'project-manifest.json').read_text(encoding='utf8'))


def test_saved_atlas_and_native_3300_650_2700_cabinet(tmp_path):
    out = tmp_path/'base'; result = build(example(), out)
    assert result['ok'], result['findings']
    assert result['sheets_checked'] == 7 and result['atlas_pages'] == 8
    assert result['references_checked'] == 4
    assert result['dimensions_mm']['A201/C1/height'] == pytest.approx(2700)
    assert result['dimensions_mm']['A301/C1/height'] == pytest.approx(2700)
    assert result['dimensions_mm']['A201/C1/width'] == 3300
    assert [result['dimensions_mm']['A201/C1/module.'+str(i)] for i in range(1, 7)] == [550]*6
    assert result['dimensions_mm']['A101/C1/width'] == 3300
    assert result['dimensions_mm']['A101/C1/depth'] == result['dimensions_mm']['A301/C1/depth'] == 650
    assert result['cross_view_pairs_checked'] == 5
    assert result['dimensions_mm']['A101/D1/width'] == result['dimensions_mm']['A202/D1/width'] == 900
    doc = ezdxf.readfile(out/'A101.dxf'); model = manifest(out)
    # A real doorway void: no full finished-face perimeter line survives across it.
    from shapely.geometry import LineString
    wall_lines = [LineString([r['a'], r['b']]) for r in model['sheets']['A101']['records'] if r['kind'] == 'LINE' and r['key'].startswith('walls:')]
    offset = model['sheets']['A101']['offset_mm']
    crossing = LineString([[offset[0]+4000, offset[1]-210], [offset[0]+4000, offset[1]+10]])
    assert not any(line.intersects(crossing) for line in wall_lines)
    assert all(e.dxftype() in {'LINE', 'TEXT', 'DIMENSION'} for e in doc.modelspace())
    assert not result['complete_19_type_construction_set']
    pdf = PdfReader(out/'atlas.pdf')
    assert len(pdf.outline) == 8
    for p in pdf.pages[1:]:
        assert float(p.mediabox.width)*25.4/72 == pytest.approx(420, abs=.001)


def test_real_revision_height_updates_elevation_and_section_only(tmp_path):
    spec = example(); base = tmp_path/'base'; out = tmp_path/'r2'
    build(spec, base); old_hash = file_hash(base/'atlas.pdf')
    spec['revision'] = 'R02'; spec['changes'] = ['C1 overall height 2700 -> 3000']
    spec['cabinets'][0]['spec']['height_mm'] = 3000
    result = build(spec, out, base)
    assert result['ok'] and result['changed_sheets'] == ['A201', 'A301']
    assert result['dimensions_mm']['A201/C1/height'] == pytest.approx(3000)
    assert result['dimensions_mm']['A301/C1/height'] == pytest.approx(3000)
    assert file_hash(base/'atlas.pdf') == old_hash
    assert manifest(out)['previous_model_hash'] == manifest(base)['model_hash']
    before, after = manifest(base), manifest(out)
    for sid in ['A101', 'A102', 'A103', 'A202', 'A203']:
        assert before['sheets'][sid]['content_hash'] == after['sheets'][sid]['content_hash']


@pytest.mark.parametrize('change,affected', [
    ('door', ['A101', 'A202']),
    ('ceiling', ['A103', 'A201', 'A202', 'A203', 'A301']),
    ('finish', ['A101', 'A102', 'A103', 'A201', 'A202', 'A203', 'A301']),
])
def test_cross_sheet_impacts_come_from_shared_geometry(change, affected):
    spec = example(); before = normalize(spec)
    if change == 'door':
        spec['openings'][0]['width_mm'] = 1000
    elif change == 'ceiling':
        spec['rooms'][0]['ceiling_z_mm'] = 3400
    else:
        spec['materials'][0]['description'] = 'New approved finish'
    after = normalize(spec)
    actual = [s['id'] for s in before['sheets'] if project(before, s) != project(after, s)]
    assert actual == affected


@pytest.mark.parametrize('bad', ['wrong_units', 'counterclockwise', 'room_overlap', 'missing_host', 'cabinet_outside',
                                 'opening_collision', 'opening_outside', 'bad_index', 'wrong_wall_index',
                                 'wrong_cut', 'unknown_material', 'duplicate', 'paper_fit', 'bad_height'])
def test_invalid_projects_are_rejected_before_output(tmp_path, bad):
    s = example()
    if bad == 'wrong_units': s['units'] = 'm'
    elif bad == 'counterclockwise': s['rooms'][0]['boundary_mm'].reverse()
    elif bad == 'room_overlap':
        r = copy.deepcopy(s['rooms'][0]); r['id'] = 'R2'; s['rooms'].append(r)
    elif bad == 'missing_host': s['cabinets'][0]['host'] = 'missing'
    elif bad == 'cabinet_outside': s['cabinets'][0]['offset_mm'] = 2000
    elif bad == 'opening_collision':
        op = copy.deepcopy(s['openings'][0]); op['id'] = 'D2'; s['openings'].append(op)
    elif bad == 'opening_outside': s['openings'][0]['height_mm'] = 4000
    elif bad == 'bad_index': s['references'][0]['target_sheet'] = 'missing'
    elif bad == 'wrong_wall_index': s['references'][0]['object_id'] = 'R1:W1'
    elif bad == 'wrong_cut': s['sheets'][-1]['at_mm'] = 10000
    elif bad == 'unknown_material': s['rooms'][0]['finishes']['floor'] = 'missing'
    elif bad == 'duplicate': s['sheets'][1]['id'] = 'A101'
    elif bad == 'paper_fit': s['sheets'][0]['scale'] = 1
    else: s['cabinets'][0]['spec']['height_mm'] = 4000
    out = tmp_path/'bad'
    with pytest.raises(ValueError): build(s, out)
    assert not out.exists()


@pytest.fixture
def bundle(tmp_path):
    out = tmp_path/'base'; build(example(), out); return out


@pytest.mark.parametrize('mutation', ['geometry', 'dimension', 'display', 'dimension_style', 'extra', 'source_link', 'lineweight', 'text', 'model', 'index', 'missing_pdf'])
def test_saved_content_tampering_is_detected(bundle, mutation):
    m = manifest(bundle); path = bundle/'A201.dxf'; doc = ezdxf.readfile(path)
    sheet = m['sheets']['A201']
    if mutation == 'geometry':
        rec = next(r for r in sheet['records'] if r['kind'] == 'LINE' and r['owner'] == 'C1')
        doc.entitydb[rec['handle']].dxf.end += (0, 20, 0)
    elif mutation == 'dimension':
        rec = next(r for r in sheet['records'] if r['kind'] == 'DIMENSION' and r['owner'] == 'C1')
        doc.entitydb[rec['handle']].dxf.text = '9999'
    elif mutation == 'display':
        rec = next(r for r in sheet['records'] if r['kind'] == 'DIMENSION')
        e = doc.entitydb[rec['handle']]
        next(v for v in doc.blocks[e.dxf.geometry] if v.dxftype() == 'MTEXT').text = '9999'
    elif mutation == 'dimension_style':
        rec = next(r for r in sheet['records'] if r['kind'] == 'DIMENSION')
        override = doc.entitydb[rec['handle']].override(); override['dimtxt'] = 5; override.commit()
    elif mutation == 'extra': doc.modelspace().add_line((0, 0), (10, 10))
    elif mutation == 'source_link': next(iter(doc.modelspace())).discard_xdata('LUOMU-PROJECT')
    elif mutation == 'lineweight': doc.layers.get('PR-CUT').dxf.lineweight = 80
    elif mutation == 'text': next(iter(doc.modelspace().query('TEXT'))).dxf.text = 'wrong'
    elif mutation == 'model':
        m['model']['cabinets'][0]['spec']['height_mm'] = 3000
        (bundle/'project-manifest.json').write_text(json.dumps(m), encoding='utf8')
    elif mutation == 'index':
        index = ezdxf.readfile(bundle/'drawing-index.dxf')
        next(iter(index.modelspace())).dxf.text = 'wrong'
        index.saveas(bundle/'drawing-index.dxf')
    else:
        # Replace a page with the real PDF of a different view, preserving a valid PDF.
        (bundle/'A201.pdf').write_bytes((bundle/'A202.pdf').read_bytes())
    if mutation not in {'model', 'index', 'missing_pdf'}:
        doc.saveas(path)
        # Rebind just the file hash: native checks must independently catch changes.
        m['artifacts'][path.name] = file_hash(path)
        (bundle/'project-manifest.json').write_text(json.dumps(m), encoding='utf8')
    assert not review(bundle)['ok']


def test_independent_dimensions_and_source_are_checked(bundle, tmp_path):
    source = tmp_path/'brief.txt'; source.write_text('Cabinet C1: W3300 D650 H2700 overall; six modules of 550.', encoding='utf8')
    req = {'source': {'sha256': file_hash(source), 'locator': 'Independent brief, first sentence'},
           'tolerance_mm': .001, 'dimensions_mm': {'A101/C1/width': 3300, 'A101/C1/depth': 650,
            'A201/C1/height': 2700, 'A301/C1/height': 2700, 'A301/C1/depth': 650}}
    result = review(bundle, req, source)
    assert result['ok'] and result['independent_source_check']['passed']
    req['dimensions_mm']['A301/C1/depth'] = 600
    result = review(bundle, req, source)
    assert not result['ok'] and any(f['kind'] == 'independent_dimension_mismatch' for f in result['findings'])
    source.write_text('Changed source', encoding='utf8')
    assert any(f['kind'] == 'independent_source_hash_mismatch' for f in review(bundle, req, source)['findings'])


def test_no_overwrite_and_stale_revision_refused(bundle, tmp_path):
    sha = file_hash(bundle/'atlas.pdf')
    with pytest.raises(ValueError, match='empty'): build(example(), bundle)
    with pytest.raises(ValueError, match='different revision'): build(example(), tmp_path/'stale', bundle)
    assert file_hash(bundle/'atlas.pdf') == sha


def test_section_direction_is_not_silently_ignored():
    m = normalize(example()); s = m['sheets'][-1]
    left = project(m, s)['primitives']
    s['direction'] = -1
    right = project(m, s)['primitives']
    a = next(r for r in left if r['kind'] == 'LINE' and r['owner'] == 'C1')
    b = next(r for r in right if r['kind'] == 'LINE' and r['owner'] == 'C1')
    assert a['a'][0] == -b['a'][0] and a['b'][0] == -b['b'][0]


def test_wall_index_avoids_opening_dimension_lane_and_its_own_arrow():
    m = normalize(example()); s = m['sheets'][0]; rows = project(m, s)['primitives']
    arrow = next(r for r in rows if r['key'] == 'xref_direction:E3')
    label = next(r for r in rows if r['key'] == 'xref:E3')
    assert arrow['a'][0] == 2500  # .25 wall length is inside the window; .5 is clear.
    assert label['a'][0]+len(label['text'])*1.6*s['scale'] < arrow['a'][0]


@pytest.mark.asyncio
async def test_real_stdio_mcp_and_workspace_boundary(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(ROOT/'src'), LUOMU_CAD_ROOT=str(tmp_path), LUOMU_CAD_LIVE_WRITES='0', PYTHONUTF8='1')
    params = StdioServerParameters(command=sys.executable, args=['-m', 'luomu_cad.server'], env=env, cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = unpack(await session.call_tool('workbench_project', {'spec': example(), 'output': str(tmp_path/'mcp')}))
            assert result['ok'], result
            again = unpack(await session.call_tool('workbench_project', {'operation': 'review', 'output': str(tmp_path/'mcp')}))
            assert again['ok'] and again['atlas_pages'] == 8
            outside = await session.call_tool('workbench_project', {'spec': example(), 'output': str(tmp_path.parent/'escape')})
            assert outside.isError
