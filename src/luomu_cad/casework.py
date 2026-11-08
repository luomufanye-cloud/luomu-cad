"""Shared cabinet dimensions, orthographic drawings and saved-file verification.

This is a drawing model, not a hardware/manufacturing or image-recognition engine.
All sizes are explicit millimetres; drawing scale affects annotation only.
"""
from __future__ import annotations

import copy
import math
import re
from pathlib import Path

import ezdxf

from .annotations import configure_cjk_style, short_extensions, text_style_findings
from .qa import file_hash
from .storage import atomic_json, digest, workspace_lock


def number(value, name, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + ' must be a finite number')
    if value < 0 or (not zero and value == 0):
        raise ValueError(name + ' must be ' + ('nonnegative' if zero else 'positive'))
    return float(value)


def normalize(spec):
    """Fail on incomplete geometry instead of substituting catalogue defaults."""
    if not isinstance(spec, dict) or spec.get('units') != 'mm':
        raise ValueError('Casework requires explicit units=mm')
    allowed = {'schema_version', 'id', 'units', 'width_mm', 'depth_mm', 'height_mm',
               'height_basis', 'top_closure_mm', 'plinth_mm', 'front_widths_mm',
               'opening_mm', 'install_gaps_mm', 'detail_level', 'panel_mm',
               'back_mm', 'section_bay', 'interiors', 'sheet', 'notes', 'source'}
    if set(spec) - allowed:
        raise ValueError('Unknown casework fields: ' + ', '.join(sorted(set(spec) - allowed)))
    result = copy.deepcopy(spec)
    if result.get('schema_version', 1) != 1:
        raise ValueError('Unsupported casework schema')
    if not isinstance(result.get('id'), str) or not result['id'].strip():
        raise ValueError('Cabinet id is required')
    for key in ('width_mm', 'depth_mm', 'height_mm'):
        result[key] = number(result.get(key), key)
    for key in ('top_closure_mm', 'plinth_mm'):
        if key not in result:
            raise ValueError(key + ' must be explicit, including zero')
        result[key] = number(result[key], key, zero=True)
    if result.get('height_basis') not in {'body', 'overall'}:
        raise ValueError('height_basis must say body or overall; do not guess whether closure is included')
    closure = result['top_closure_mm']
    result['body_height_mm'] = result['height_mm'] - (closure if result['height_basis'] == 'overall' else 0)
    result['overall_height_mm'] = result['body_height_mm'] + closure
    h = result['body_height_mm']
    if h <= result['plinth_mm']:
        raise ValueError('Plinth must leave positive cabinet body height')
    widths = result.get('front_widths_mm')
    if not isinstance(widths, list) or not 1 <= len(widths) <= 40:
        raise ValueError('front_widths_mm requires 1..40 explicit front modules')
    result['front_widths_mm'] = [number(v, 'front width') for v in widths]
    if not math.isclose(sum(widths), result['width_mm'], abs_tol=1e-6, rel_tol=0):
        raise ValueError('Front dimension chain does not equal cabinet width')
    if 'opening_mm' in result or 'install_gaps_mm' in result:
        gaps = result.get('install_gaps_mm')
        if not isinstance(gaps, list) or len(gaps) != 2:
            raise ValueError('Both left/right installation gaps are required')
        result['install_gaps_mm'] = [number(v, 'installation gap', zero=True) for v in gaps]
        result['opening_mm'] = number(result.get('opening_mm'), 'opening_mm')
        if not math.isclose(result['opening_mm'], result['width_mm'] + sum(gaps), abs_tol=1e-6, rel_tol=0):
            raise ValueError('Opening must equal cabinet width plus both installation gaps')
    detail = result.get('detail_level')
    if detail not in {'reference_outline', 'panel_section'}:
        raise ValueError('Choose reference_outline or panel_section')
    if detail == 'panel_section':
        for key in ('panel_mm', 'back_mm'):
            result[key] = number(result.get(key), key)
        t = result['panel_mm']
        if min(widths) <= 2*t or result['depth_mm'] <= result['back_mm'] + t or h-result['plinth_mm'] <= 2*t:
            raise ValueError('Panel/back thickness leaves no usable interior')
    elif 'panel_mm' in result or 'back_mm' in result:
        raise ValueError('Use panel_section to declare real board thickness')
    bay = result.get('section_bay')
    if isinstance(bay, bool) or not isinstance(bay, int) or not 1 <= bay <= len(widths):
        raise ValueError('section_bay is a 1-based front module number')
    interiors = result.setdefault('interiors', [])
    if not isinstance(interiors, list):
        raise ValueError('interiors must be a list')
    seen = set()
    for item in interiors:
        if not isinstance(item, dict) or set(item) - {'bay', 'shelves_mm', 'rod_mm'}:
            raise ValueError('Interior supports bay, shelves_mm and rod_mm')
        index = item.get('bay')
        if isinstance(index, bool) or not isinstance(index, int) or not 1 <= index <= len(widths) or index in seen:
            raise ValueError('Interior bay must be unique and within the front modules')
        seen.add(index)
        shelves = item.setdefault('shelves_mm', [])
        if not isinstance(shelves, list):
            raise ValueError('shelves_mm must be a list')
        shelves[:] = [number(v, 'shelf level') for v in shelves]
        if len(set(shelves)) != len(shelves):
            raise ValueError('Duplicate shelf levels')
        levels = shelves + ([number(item['rod_mm'], 'rod level')] if 'rod_mm' in item else [])
        t = result.get('panel_mm', 0)
        if any(not result['plinth_mm'] + t < v < h - t for v in levels):
            raise ValueError('Interior levels are floor-relative and must lie inside the cabinet')
        if detail == 'panel_section':
            ordered = sorted(shelves)
            if any(b-a <= t for a, b in zip(ordered, ordered[1:])) or any(v+t >= h-t for v in shelves):
                raise ValueError('Shelf boards intersect each other or the cabinet top')
        if 'rod_mm' in item:
            item['rod_mm'] = number(item['rod_mm'], 'rod level')
    sheet = result.setdefault('sheet', {})
    if not isinstance(sheet, dict) or set(sheet) - {'paper_mm', 'scale', 'language', 'lineweights_mm'}:
        raise ValueError('Unknown casework sheet field')
    sheet['scale'] = number(sheet.get('scale', 30), 'scale')
    if not 10 <= sheet['scale'] <= 100:
        raise ValueError('Casework sheet scale must be between 10 and 100')
    paper = sheet.setdefault('paper_mm', [420, 297])
    if not isinstance(paper, list) or len(paper) != 2:
        raise ValueError('paper_mm requires width and height')
    sheet['paper_mm'] = [number(v, 'paper mm') for v in paper]
    if min(paper) < 150 or max(paper) > 2000:
        raise ValueError('Unsupported paper dimensions')
    if sheet.setdefault('language', 'en') not in {'en', 'zh'}:
        raise ValueError('language must be en or zh')
    weights = sheet.setdefault('lineweights_mm', {'outline': .25, 'hidden': .13, 'cut': .35, 'annotation': .13})
    if set(weights) != {'outline', 'hidden', 'cut', 'annotation'}:
        raise ValueError('Set outline, hidden, cut and annotation lineweights together')
    from ezdxf.lldxf.const import VALID_DXF_LINEWEIGHTS
    for key, value in weights.items():
        value = number(value, 'lineweight')
        if round(value*100) not in VALID_DXF_LINEWEIGHTS or abs(value*100-round(value*100)) > 1e-6:
            raise ValueError('Lineweight must be an exact supported DXF paper-mm value')
    notes = result.setdefault('notes', [])
    if not isinstance(notes, list) or len(notes) > 12 or any(not isinstance(n, str) or not n.strip() or len(n) > 100 for n in notes):
        raise ValueError('Use at most 12 short, nonempty source/project notes')
    return result


def draw(spec):
    """Construct three dimensioned views from one dimensional model."""
    model = normalize(spec)
    w, d, h = (model[k] for k in ('width_mm', 'depth_mm', 'body_height_mm'))
    z, p = model['overall_height_mm'], model['plinth_mm']
    scale = model['sheet']['scale']
    gap = scale*24
    origin = [scale*25, d+scale*52]
    views = {'front': {'origin': origin, 'axes': ['X', 'Z'], 'size': [w, z]},
             'plan': {'origin': [origin[0], scale*22], 'axes': ['X', 'Y'], 'size': [w, d]},
             'section': {'origin': [origin[0]+w+gap, origin[1]], 'axes': ['Y', 'Z'], 'size': [d, z]}}
    # Independent labelled view panels: not an implicit first-/third-angle symbol.
    paper_w, paper_h = model['sheet']['paper_mm']
    if origin[0]+w+gap+d+scale*24 > paper_w*scale or origin[1]+z+scale*26 > paper_h*scale:
        raise ValueError('Views do not fit the specified paper and scale; choose a larger sheet')
    doc = ezdxf.new('R2018', setup=True)
    doc.units = 4
    doc.header['$MEASUREMENT'] = 1
    doc.header['$LWDISPLAY'] = False
    doc.header['$LTSCALE'] = 1
    font = configure_cjk_style(doc, 'LUOMU')
    if model['sheet']['language'] == 'zh' and not font['available']:
        raise ValueError('Chinese casework drawings require an available CJK font')
    style = 'LUOMU' if font['available'] else 'Standard'
    for name, weight in model['sheet']['lineweights_mm'].items():
        doc.layers.new('CW-'+name.upper(), dxfattribs={'color': 7, 'lineweight': round(weight*100),
            'linetype': 'DASHED' if name == 'hidden' else 'CONTINUOUS'})
    doc.layers.new('CW-SHEET', dxfattribs={'color': 7, 'lineweight': 13})
    doc.appids.new('LUOMU-CASEWORK')
    m = doc.modelspace()
    expected = []
    dimensions = {}

    def register(entity, key, view, role):
        entity.set_xdata('LUOMU-CASEWORK', [(1000, key), (1000, view), (1000, role)])
        return entity

    def line(key, view, a, b, role='outline'):
        offset = views[view]['origin'] if view in views else [0, 0]
        a, b = [[pt[i]+offset[i] for i in range(2)] for pt in (a, b)]
        e = register(m.add_line(a, b, dxfattribs={'layer': 'CW-'+role.upper(),
                     'ltscale': scale if role == 'hidden' else 1}), key, view, role)
        expected.append({'key': key, 'view': view, 'role': role, 'handle': e.dxf.handle,
                         'kind': 'LINE', 'start': a, 'end': b})
        return e

    def box(key, view, bounds, role='outline'):
        a, b, c, e = bounds
        points = [(a, b), (c, b), (c, e), (a, e)]
        for i in range(4):
            line(key+':'+str(i), view, points[i], points[(i+1) % 4], role)

    def label(text, at, size=2.5, layer='CW-ANNOTATION'):
        entity = m.add_text(text, dxfattribs={'insert': at, 'height': size*scale, 'style': style, 'layer': layer})
        expected.append({'kind': 'TEXT', 'handle': entity.dxf.handle, 'text': text, 'at': list(at), 'height': size*scale})
        return entity

    def dimension(key, view, a, b, at, angle=0):
        offset = views[view]['origin']
        a, b, at = [[point[i]+offset[i] for i in range(2)] for point in (a, b, at)]
        override = {**short_extensions(scale, gap=1), 'dimtxt': 2.5*scale, 'dimasz': 2*scale,
                    'dimgap': .8*scale, 'dimtad': 1, 'dimlfac': 1, 'dimdec': 2, 'dimzin': 8,
                    'dimtxsty': style, 'dimlwd': round(model['sheet']['lineweights_mm']['annotation']*100),
                    'dimlwe': round(model['sheet']['lineweights_mm']['annotation']*100)}
        dim = m.add_linear_dim(base=at, p1=a, p2=b, angle=angle, dimstyle='EZDXF',
                               override=override, dxfattribs={'layer': 'CW-ANNOTATION'})
        dim.render()
        e = register(dim.dimension, key, view, 'dimension')
        dimensions[key] = {'handle': e.dxf.handle, 'view': view,
                           'expected_mm': math.dist(a, b), 'start': a, 'end': b, 'angle': angle}

    for name, view in views.items():
        box('envelope', name, [0, 0, *view['size']])
        if name != 'plan':
            if model['top_closure_mm']:
                line('body_top', name, [0, h], [view['size'][0], h])
            if p:
                line('plinth', name, [0, p], [view['size'][0], p])
    x = 0
    for i, width in enumerate(model['front_widths_mm'], 1):
        if i > 1:
            line('front_division:'+str(i-1), 'front', [x, p], [x, h])
            line('front_division:'+str(i-1), 'plan', [x, 0], [x, d], 'hidden')
        dimension('front.module.'+str(i), 'front', [x, 0], [x+width, 0], [x, -scale*6])
        x += width
    t = model.get('panel_mm', 0)
    back = model.get('back_mm', 0)
    if model['detail_level'] == 'panel_section':
        # Section through the selected module, looking along X; explicit board edges.
        for name, bounds in [('bottom', [0, p, d, p+t]), ('top', [0, h-t, d, h]),
                             ('back', [d-back, p+t, d, h-t])]:
            box('panel:'+name, 'section', bounds, 'cut')
        line('back_inner', 'plan', [0, d-back], [w, d-back], 'hidden')
    cursor = [0]
    for width in model['front_widths_mm']:
        cursor.append(cursor[-1]+width)
    for item in model['interiors']:
        left, right = cursor[item['bay']-1], cursor[item['bay']]
        for i, level in enumerate(item['shelves_mm'], 1):
            line('shelf:'+str(item['bay'])+':'+str(i), 'front', [left+t, level], [right-t, level], 'hidden')
            if item['bay'] == model['section_bay']:
                key = 'shelf:'+str(i)
                if t:
                    box(key, 'section', [0, level, d-back, level+t], 'cut')
                else:
                    line(key, 'section', [0, level], [d, level], 'hidden')
        if 'rod_mm' in item:
            level = item['rod_mm']
            line('rod:'+str(item['bay']), 'front', [left+t, level], [right-t, level], 'hidden')
            if item['bay'] == model['section_bay']:
                line('rod', 'section', [d*.45, level], [d*.55, level], 'hidden')
    dimension('front.width', 'front', [0, 0], [w, 0], [0, -scale*13])
    dimension('front.body_height', 'front', [0, 0], [0, h], [-scale*7, 0], 90)
    dimension('front.overall_height', 'front', [0, 0], [0, z], [-scale*17, 0], 90)
    dimension('plan.width', 'plan', [0, 0], [w, 0], [0, -scale*7])
    dimension('plan.depth', 'plan', [0, 0], [0, d], [-scale*7, 0], 90)
    dimension('section.depth', 'section', [0, 0], [d, 0], [0, -scale*7])
    dimension('section.body_height', 'section', [d, 0], [d, h], [d+scale*7, 0], 90)
    dimension('section.overall_height', 'section', [d, 0], [d, z], [d+scale*17, 0], 90)
    if p:
        dimension('front.plinth', 'front', [w, 0], [w, p], [w+scale*5, 0], 90)
    if model['top_closure_mm']:
        dimension('front.closure', 'front', [w, h], [w, z], [w+scale*5, h], 90)
    # Explicit section position in the plan, matching the selected module.
    cut_x = (cursor[model['section_bay']-1]+cursor[model['section_bay']])/2
    line('section_cut', 'plan', [cut_x, -scale*2], [cut_x, d+scale*2], 'annotation')
    for yy in (-scale*2, d+scale*2):
        line('section_arrow:'+str(yy), 'plan', [cut_x, yy], [cut_x+scale*4, yy], 'annotation')
        for direction in (-1, 1):
            line('section_arrowhead:'+str(yy)+':'+str(direction), 'plan',
                 [cut_x+scale*4, yy], [cut_x+scale*2.5, yy+direction*scale*.7], 'annotation')
        label('A', [views['plan']['origin'][0]+cut_x-scale*3, views['plan']['origin'][1]+yy-scale], 2)
    zh = model['sheet']['language'] == 'zh'
    side_title = ('A-A侧剖' if zh else 'SECTION A-A') if t else ('A-A侧向轮廓' if zh else 'SIDE OUTLINE A-A')
    titles = {'front': '正立面' if zh else 'FRONT ELEVATION', 'plan': '柜体平面 / A-A定位' if zh else 'PLAN / A-A LOCATION',
              'section': side_title+' / '+('第'+str(model['section_bay'])+'格' if zh else 'BAY '+str(model['section_bay']))}
    for name, view in views.items():
        label(titles[name], [view['origin'][0], view['origin'][1]+view['size'][1]+scale*7])
    label(('柜体多视图' if zh else 'CASEWORK MULTIVIEW')+' / '+model['id'], [scale*12, paper_h*scale-scale*10], 4)
    label(('单位 mm / 比例 1:' if zh else 'UNITS mm / SCALE 1:')+f'{scale:g}', [scale*12, paper_h*scale-scale*17])
    label('luomufanye-cloud / Luomu CAD', [paper_w*scale-scale*95, scale*7], 2)
    # Notes use a separate right-hand column, never in the section geometry.
    note_x = origin[0]+w+gap+d+scale*25
    mode_label = ('板厚已明确的柜体剖面' if t else '参考尺寸与侧向轮廓') if zh else ('EXPLICIT PANEL SECTION' if t else 'REFERENCE SIZES / SIDE OUTLINE')
    basis_label = ('柜身（不含顶部收口）' if model['height_basis']=='body' else '总高（含顶部收口）') if zh else model['height_basis'].upper()
    notes = [mode_label, ('柜高基准：' if zh else 'HEIGHT BASIS: ')+basis_label, *model['notes']]
    if 'opening_mm' in model:
        notes.append(('净宽/左右安装缝：' if zh else 'OPENING / GAPS: ')+f"{model['opening_mm']:g} / {model['install_gaps_mm'][0]:g}, {model['install_gaps_mm'][1]:g}")
    # If no side note column fits, put short notes below the title in unused top margin.
    if note_x + scale*70 > paper_w*scale:
        note_x = max(origin[0]+w+gap, paper_w*scale-scale*125)
        note_y = paper_h*scale-scale*28
        if note_y-len(notes)*scale*5 < origin[1]+z+scale*12:
            raise ValueError('Notes do not fit the sheet; use larger paper or scale')
    else:
        note_y = origin[1]+z
    for i, text in enumerate(notes):
        label(text, [note_x, note_y-i*scale*5], 2)
    for i, (a, b) in enumerate([([scale*5, scale*5], [paper_w*scale-scale*5, scale*5]),
                              ([paper_w*scale-scale*5, scale*5], [paper_w*scale-scale*5, paper_h*scale-scale*5]),
                              ([paper_w*scale-scale*5, paper_h*scale-scale*5], [scale*5, paper_h*scale-scale*5]),
                              ([scale*5, paper_h*scale-scale*5], [scale*5, scale*5])]):
        line('border:'+str(i), 'sheet', a, b, 'sheet')
    manifest = {'schema_version': 1, 'model': model, 'model_hash': digest(model), 'views': views,
                'geometry': expected, 'dimensions': dimensions, 'font': font,
                'modelspace_handles': [e.dxf.handle for e in m],
                'scope': 'Cabinet reference/explicit-panel drawings; not hardware drilling, cut-list or construction approval'}
    return doc, manifest


def display_signature(doc, entity):
    """Include actual anonymous-block graphics, not just the dimension definition."""
    from ezdxf.lldxf.tagwriter import TagCollector
    if entity.dxf.geometry not in doc.blocks:
        return None
    return digest([str(TagCollector.dxftags(item)) for item in doc.blocks[entity.dxf.geometry]])


def review(path, manifest, requirements=None, source=None):
    """Read actual entities, dimensions and cross-view spans; do not trust report ok."""
    doc = ezdxf.readfile(path)
    findings = []

    def fail(kind, **data):
        findings.append({'kind': kind, **data})

    if doc.units != 4:
        fail('units_not_mm')
    if doc.header.get('$LTSCALE', 1) != 1:
        fail('global_linetype_scale_changed')
    if digest(manifest['model']) != manifest['model_hash']:
        fail('model_hash_mismatch')
    if set(manifest['modelspace_handles']) != {e.dxf.handle for e in doc.modelspace()}:
        fail('entity_inventory_changed')
    if manifest.get('drawing_sha256') and file_hash(path) != manifest['drawing_sha256']:
        fail('saved_artifact_changed')
    for row in manifest['geometry']:
        e = doc.entitydb.get(row['handle'])
        if e is None or not e.is_alive or e.dxftype() != row['kind']:
            fail('missing_or_changed_entity', handle=row['handle'])
            continue
        if row['kind'] == 'LINE':
            if math.dist(e.dxf.start, (*row['start'], 0)) > 1e-6 or math.dist(e.dxf.end, (*row['end'], 0)) > 1e-6:
                fail('projected_geometry_changed', key=row['key'], view=row['view'])
            layer = 'CW-'+row['role'].upper()
            weight = 13 if row['role'] == 'sheet' else round(manifest['model']['sheet']['lineweights_mm'][row['role']]*100)
            if e.dxf.layer != layer or e.dxf.lineweight != -1 or doc.layers.get(layer).dxf.lineweight != weight:
                fail('lineweight_changed', handle=row['handle'])
            expected_type = 'DASHED' if row['role'] == 'hidden' else 'CONTINUOUS'
            if e.dxf.linetype.upper() != 'BYLAYER' or doc.layers.get(layer).dxf.linetype.upper() != expected_type:
                fail('linetype_changed', handle=row['handle'])
            expected_scale = manifest['model']['sheet']['scale'] if row['role'] == 'hidden' else 1
            if abs(e.dxf.ltscale-expected_scale) > 1e-6:
                fail('linetype_scale_changed', handle=row['handle'])
        else:
            if e.dxf.text != row['text'] or math.dist(e.dxf.insert, (*row['at'], 0)) > 1e-6 or abs(e.dxf.height-row['height']) > 1e-6:
                fail('annotation_changed', handle=row['handle'])
    measured = {}
    for key, row in manifest['dimensions'].items():
        e = doc.entitydb.get(row['handle'])
        if e is None or not e.is_alive or e.dxftype() != 'DIMENSION':
            fail('native_dimension_missing', dimension=key)
            continue
        value = float(e.get_measurement())
        measured[key] = value
        overrides = e.override()
        expected_weight = round(manifest['model']['sheet']['lineweights_mm']['annotation']*100)
        if overrides.get('dimlwd') != expected_weight or overrides.get('dimlwe') != expected_weight:
            fail('dimension_lineweight_changed', dimension=key)
        if e.dxf.get('text', '<>') not in ('', '<>') or overrides.get('dimlfac', 1) != 1:
            fail('dimension_text_or_factor_override', dimension=key)
        if abs(value-row['expected_mm']) > 1e-6 or math.dist(e.dxf.defpoint2, (*row['start'], 0)) > 1e-6 or math.dist(e.dxf.defpoint3, (*row['end'], 0)) > 1e-6:
            fail('dimension_definition_changed', dimension=key)
        if e.dxf.geometry not in doc.blocks:
            fail('dimension_display_block_missing', dimension=key)
        else:
            if row.get('display_hash') and display_signature(doc, e) != row['display_hash']:
                fail('dimension_display_geometry_changed', dimension=key)
            texts = [v.plain_text() for v in doc.blocks[e.dxf.geometry] if v.dxftype() in ('TEXT', 'MTEXT')]
            if not texts or any(text.strip() != f'{value:.2f}'.rstrip('0').rstrip('.') for text in texts):
                fail('dimension_display_stale', dimension=key, texts=texts, measured=value)
    pairs = [('front.width', 'plan.width'), ('front.body_height', 'section.body_height'),
             ('front.overall_height', 'section.overall_height'), ('plan.depth', 'section.depth')]
    for a, b in pairs:
        if a not in measured or b not in measured or abs(measured[a]-measured[b]) > 1e-6:
            fail('cross_view_dimension_mismatch', dimensions=[a, b])
    module_values = [v for k, v in measured.items() if k.startswith('front.module.')]
    if abs(sum(module_values)-measured.get('front.width', -1)) > 1e-6:
        fail('front_dimension_chain_mismatch')
    # A separately transcribed source contract supplies expected sizes, not output-derived targets.
    source_result = None
    if requirements is not None:
        if not isinstance(requirements, dict) or set(requirements) != {'source', 'dimensions_mm', 'tolerance_mm'}:
            raise ValueError('Requirements need source, dimensions_mm and tolerance_mm')
        if not isinstance(requirements['source'], dict) or not requirements['source'].get('locator') or not re.fullmatch('[a-fA-F0-9]{64}', str(requirements['source'].get('sha256', ''))):
            raise ValueError('Independent requirements need source SHA256 and locator')
        if source is None:
            raise ValueError('Pass the original source file for independent requirement verification')
        source_verified = file_hash(source) == requirements['source']['sha256']
        if not source_verified:
            fail('independent_source_hash_mismatch')
        expected = requirements['dimensions_mm']
        required = {'front.width', 'front.body_height', 'front.overall_height', 'plan.depth', 'section.depth'}
        if not isinstance(expected, dict) or not required <= expected.keys():
            raise ValueError('Requirements must cover width, body/overall height and both depths')
        tolerance = number(requirements['tolerance_mm'], 'source tolerance')
        comparisons = []
        for key, target in expected.items():
            target = number(target, key)
            actual = measured.get(key)
            passed = actual is not None and abs(actual-target) <= tolerance
            comparisons.append({'dimension': key, 'expected_mm': target, 'actual_mm': actual, 'passed': passed})
            if not passed:
                fail('independent_source_dimension_mismatch', dimension=key, expected_mm=target, actual_mm=actual)
        source_result = {'source': requirements['source'], 'source_hash_verified': source_verified,
                         'comparisons': comparisons, 'passed': source_verified and all(c['passed'] for c in comparisons)}
    auditor = doc.audit()
    if auditor.errors or auditor.fixes:
        fail('dxf_audit_required', errors=len(auditor.errors), fixes=len(auditor.fixes))
    findings.extend(text_style_findings(doc))
    return {'ok': not findings, 'drawing_sha256': file_hash(path), 'findings': findings,
            'dimensions_mm': measured, 'cross_view_pairs_checked': len(pairs),
            'independent_source_check': source_result,
            'image_recognition_accuracy_tested': False, 'manufacturing_approved': False}


def build(spec, output, requirements=None, source=None):
    """Publish a new bundle; preserve existing outputs and interrupted writes."""
    doc, manifest = draw(spec)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with workspace_lock(output):
        # Lock is the only file that may pre-exist; never overwrite an earlier bundle.
        if any(p.name != 'workspace.lock' for p in output.iterdir()):
            raise ValueError('Casework output must be empty; use a new directory')
        drawing = output/'casework.dxf'
        doc.saveas(drawing)
        saved = ezdxf.readfile(drawing)
        for row in manifest['dimensions'].values():
            row['display_hash'] = display_signature(saved, saved.entitydb[row['handle']])
        manifest['drawing_sha256'] = file_hash(drawing)
        atomic_json(output/'casework-manifest.json', manifest)
        check = review(drawing, manifest, requirements, source)
        atomic_json(output/'casework-review.json', check)
        result = {'ok': check['ok'], 'model_hash': manifest['model_hash'], 'review': check,
                  'artifacts': {key: {'path': str(output/name), 'sha256': file_hash(output/name)}
                                for key, name in [('dxf', 'casework.dxf'), ('manifest', 'casework-manifest.json'),
                                                  ('review', 'casework-review.json')]}}
        atomic_json(output/'result.json', result)
        return result
