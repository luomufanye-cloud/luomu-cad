"""Measured drawing checks against an explicit, source-bound professional brief.

Geometry uses ezdxf and Shapely. Source interpretation and engineering decisions
remain review inputs. This module neither operates AutoCAD nor infers design.
"""
import hashlib
import json
import math
from pathlib import Path

import ezdxf
from ezdxf.addons.drawing import RenderContext
from ezdxf.path import make_path
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from .standards import text
from .storage import ROOT


def profiles():
    candidates = [ROOT, Path(__file__).resolve().parents[2], Path(__file__).resolve().parents[1]]
    for root in candidates:
        path = root / 'references/professional-profiles.json'
        if path.is_file():
            return json.loads(path.read_text(encoding='utf-8'))
    raise ValueError('Professional profiles resource missing')


def template(profile_ids):
    library = profiles()
    known = {p['id']: p for p in library['profiles']}
    if not profile_ids or len(set(profile_ids)) != len(profile_ids) or set(profile_ids) - known.keys():
        raise ValueError('Select distinct, registered professional profiles')
    categories = dict.fromkeys(c for pid in profile_ids for c in known[pid]['categories'])
    return {'schema_version': 1, 'profile_ids': profile_ids,
            'guidance': [known[pid] for pid in profile_ids],
            'drawing_sha256': '', 'source': {'path': '', 'sha256': '', 'locator': ''},
            'units': 4, 'coordinate_basis': '', 'drawing_type': '', 'stage': '', 'expected_handles': [],
            'categories': {c: {'status': 'pending', 'source_locator': '', 'checks': []} for c in categories},
            'style': {'basis': '', 'layers': {}}, 'checks': [],
            'reviews': {k: {'status': 'pending', 'evidence': ''}
                        for k in ('source_coverage', 'professional_semantics', 'sheet_delivery')}}


def finite(value, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Finite numeric contract value required')
    if positive and value <= 0:
        raise ValueError('Positive contract value required')
    return float(value)


def interval(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('A [minimum, maximum] interval is required')
    low, high = map(finite, value)
    if low > high:
        raise ValueError('Reversed measurement interval')
    return low, high


def building_line_group(base_mm):
    """GB/T 50001-2017 table 4.0.1, selected explicitly for building drawings."""
    groups = {1.4: [1.4, 1.0, .7, .35], 1.0: [1.0, .7, .5, .25],
              .7: [.7, .5, .35, .18], .5: [.5, .35, .25, .13]}
    base = finite(base_mm, positive=True)
    if base not in groups:
        raise ValueError('Building base width must be one of 1.4, 1.0, 0.7, 0.5 mm')
    return groups[base]


def artifact(record, directory):
    if not isinstance(record, dict) or not text(record.get('path')):
        raise ValueError('Evidence file and SHA256 required')
    path = (Path(directory) / record['path']).resolve()
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != record.get('sha256'):
        raise ValueError('Missing or changed evidence file')
    return path


def _entities(doc, handles):
    if not isinstance(handles, list) or not handles or len(set(handles)) != len(handles):
        raise ValueError('Distinct modelspace handles required')
    model = {e.dxf.handle: e for e in doc.modelspace()}
    if set(handles) - model.keys():
        raise ValueError('Missing modelspace geometry handles')
    return [model[h] for h in handles]


def _geometry(entities, tolerance):
    curves = []
    for entity in entities:
        if entity.dxftype() not in {'LINE', 'LWPOLYLINE', 'POLYLINE', 'ARC', 'CIRCLE', 'ELLIPSE', 'SPLINE'}:
            raise ValueError('Geometry check requires native planar curves, received ' + entity.dxftype())
        points = list(make_path(entity).flattening(tolerance / 4))
        if len(points) < 2 or any(not all(math.isfinite(v) for v in p) or abs(p.z) > tolerance / 4 for p in points):
            raise ValueError('Finite XY-plane geometry required')
        curves.append(LineString([(p.x, p.y) for p in points]))
    return unary_union(curves)


def measure(doc, check):
    """Return measured values, retaining the actual objects and expected bounds."""
    kind = check['kind']
    entities = _entities(doc, check['handles'])
    if kind == 'count':
        allowed = check.get('types', [])
        value = len(entities)
        passed = all(e.dxftype() in allowed for e in entities)
    elif kind == 'dimension':
        if len(entities) != 1 or entities[0].dxftype() != 'DIMENSION':
            raise ValueError('Dimension check requires one native DIMENSION')
        value = float(entities[0].get_measurement())
        passed = entities[0].dxf.get('text', '<>') in ('', '<>')
    elif kind == 'text':
        if any(e.dxftype() not in {'TEXT', 'MTEXT'} for e in entities):
            raise ValueError('Text check requires native TEXT/MTEXT')
        value = [e.plain_text() for e in entities]
        return {'actual': value, 'passed': value == check['expected']}
    else:
        tolerance = finite(check['tolerance'], positive=True)
        geometry = _geometry(entities, tolerance)
        passed = True
        if kind == 'contour':
            points = check['expected_points']
            if not isinstance(points, list) or len(points) < 2 or any(len(p) != 2 for p in points):
                raise ValueError('Independent reference contour points required')
            expected = LineString([[finite(v) for v in p] for p in points])
            value = geometry.hausdorff_distance(expected)
            return {'actual': value, 'passed': value <= tolerance, 'metric': 'symmetric_hausdorff'}
        if kind == 'distance':
            other = _geometry(_entities(doc, check['other_handles']), tolerance)
            value = geometry.distance(other)
        elif kind == 'length':
            value = geometry.length
        elif kind == 'closed':
            value = geometry.is_ring
            return {'actual': bool(value), 'passed': bool(value) == check['expected']}
        elif kind == 'area':
            if geometry.geom_type != 'LineString' or not geometry.is_ring:
                raise ValueError('Area requires one simple closed contour')
            polygon = Polygon(geometry.coords)
            if not polygon.is_valid:
                raise ValueError('Self-intersecting area boundary')
            value = polygon.area
        elif kind == 'angle':
            if len(entities) != 1 or entities[0].dxftype() != 'LINE':
                raise ValueError('Direction requires one native LINE')
            delta = entities[0].dxf.end - entities[0].dxf.start
            value = math.degrees(math.atan2(delta.y, delta.x)) % 360
            difference = abs((value - finite(check['expected']) + 180) % 360 - 180)
            return {'actual': value, 'passed': difference <= finite(check['angle_tolerance'], positive=True)}
        else:
            raise ValueError('Unsupported measurement kind ' + str(kind))
    low, high = interval(check['range'])
    return {'actual': value, 'passed': passed and low <= value <= high}


def style_findings(doc, spec):
    """Resolve ByLayer/ByBlock with ezdxf, inspect polyline width separately.

    This is object-style inspection. CTB/STB and native plot output need their own
    reviewed evidence. Invisible/off/frozen objects remain in the audit.
    """
    if not isinstance(spec, dict) or not text(spec.get('basis')) or not spec.get('layers'):
        raise ValueError('Project-selected layer style and its basis required')
    from .annotations import drawing_context
    context = drawing_context(doc)
    errors, measured = [], []
    count = 0

    rules = {name.casefold(): rule for name, rule in spec['layers'].items()}
    group = building_line_group(spec['building_base_mm']) if 'building_base_mm' in spec else None

    def visit(entity, ancestry=(), names=(), width_scale=1):
        nonlocal count
        count += 1
        if count > 100000 or len(names) > 16:
            raise ValueError('Style inspection entity/depth limit exceeded')
        identifier = '/'.join((*ancestry, entity.dxf.handle or '?'))
        properties = context.resolve_all(entity)
        layer = properties.layer
        rule = rules.get(layer.casefold())
        if rule is None:
            errors.append('STYLE_LAYER_UNSPECIFIED:' + layer)
        else:
            low, high = interval(rule['lineweight_mm'])
            if not low <= properties.lineweight <= high:
                errors.append('LINEWEIGHT:' + identifier)
            if group and not any(abs(properties.lineweight - width) < .001 for width in group):
                errors.append('BUILDING_LINE_GROUP:' + identifier)
            if properties.linetype_name.casefold() not in {v.casefold() for v in rule['linetypes']}:
                errors.append('LINETYPE:' + identifier)
        widths = []
        if entity.dxftype() == 'LWPOLYLINE':
            widths = [entity.dxf.get('const_width', 0)]
            widths.extend(v for p in entity.get_points('se') for v in p)
        elif entity.dxftype() == 'POLYLINE':
            widths = [entity.dxf.get('default_start_width', 0), entity.dxf.get('default_end_width', 0)]
            widths.extend(v.dxf.get(k, 0) for v in entity.vertices for k in ('start_width', 'end_width'))
        widths = [w * width_scale for w in widths]
        if rule and widths:
            low, high = interval(rule['polyline_width'])
            if any(not math.isfinite(w) or not low <= w <= high for w in widths):
                errors.append('POLYLINE_WIDTH:' + identifier)
        measured.append({'id': identifier, 'layer': layer, 'lineweight_mm': properties.lineweight,
                         'linetype': properties.linetype_name, 'polyline_widths': widths})
        if entity.dxftype() == 'INSERT':
            name = entity.dxf.name.casefold()
            block = entity.block()
            if name in names or block is None or block.block.is_xref:
                errors.append('UNRESOLVED_BLOCK:' + identifier)
                return
            context.push_state(properties)
            try:
                sx, sy = abs(entity.dxf.xscale), abs(entity.dxf.yscale)
                if not math.isclose(sx, sy):
                    errors.append('NONUNIFORM_BLOCK_WIDTH_REVIEW:' + identifier)
                for child in block:
                    visit(child, (*ancestry, entity.dxf.handle), (*names, name), width_scale * sx)
                for attribute in entity.attribs:
                    visit(attribute, (*ancestry, entity.dxf.handle), (*names, name))
            finally:
                context.pop_state()

    for entity in doc.modelspace():
        visit(entity)
    from .annotations import dimension_stroke_findings
    dimensions=dimension_stroke_findings(doc,spec)
    errors.extend(dimensions['errors'])
    if not measured:
        errors.append('EMPTY_DRAWING')
    return {'errors': sorted(set(errors)), 'entities': measured,'dimension_strokes':dimensions['dimensions'],
            'variables': {k: doc.header.get(k) for k in ('$LWDISPLAY', '$LWDEFAULT', '$PLINEWID', '$LTSCALE', '$PSLTSCALE')},
            'plot_style_verified': False}


def audit(drawing, manifest, directory):
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
        raise ValueError('Professional manifest schema_version=1 required')
    expected = template(manifest['profile_ids'])
    path = Path(drawing)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    errors = []
    if before != manifest.get('drawing_sha256'):
        errors.append('PROFESSIONAL_STALE_DRAWING')
    source = artifact(manifest.get('source'), directory)
    if source == path.resolve() or not text(manifest['source'].get('locator')):
        errors.append('INDEPENDENT_SOURCE_REQUIRED')
    for field in ('coordinate_basis', 'drawing_type', 'stage'):
        if not text(manifest.get(field)):
            errors.append('PROJECT_FIELD_REQUIRED:' + field)
    doc = ezdxf.readfile(path)
    expected_handles = manifest.get('expected_handles')
    if (not isinstance(expected_handles, list) or not expected_handles
            or len(expected_handles) != len(set(expected_handles))
            or set(expected_handles) != {e.dxf.handle for e in doc.modelspace()}):
        errors.append('MODEL_INVENTORY_MISMATCH')
    if type(manifest.get('units')) is not int or doc.units != manifest['units']:
        errors.append('PROFESSIONAL_UNITS_MISMATCH')
    checks = manifest.get('checks')
    if not isinstance(checks, list) or not checks:
        raise ValueError('At least one actual measurement required')
    by_id, results = {}, []
    for check in checks:
        cid = check.get('id')
        if not text(cid) or cid in by_id or not text(check.get('source_locator')):
            raise ValueError('Unique measurement IDs and source locators required')
        by_id[cid] = check
        try:
            result = measure(doc, check)
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            result = {'passed': False, 'error': str(exc)}
        results.append({'id': cid, 'kind': check.get('kind'), **result})
        if not result['passed']:
            errors.append('MEASUREMENT_FAILED:' + cid)
    used = set()
    categories = manifest.get('categories', {})
    category_kinds = profiles()['category_measurements']
    present_count = 0
    for category in expected['categories']:
        row = categories.get(category, {})
        if not text(row.get('source_locator')):
            errors.append('CATEGORY_SOURCE_REQUIRED:' + category)
        if row.get('status') == 'not_applicable' and text(row.get('reason')):
            continue
        present_count += 1
        ids = row.get('checks', [])
        if row.get('status') != 'present' or not ids or set(ids) - by_id.keys():
            errors.append('CATEGORY_MEASUREMENTS_REQUIRED:' + category)
        elif not {by_id[cid]['kind'] for cid in ids}.intersection(category_kinds[category]):
            errors.append('CATEGORY_MEASUREMENT_KIND:' + category)
        used.update(ids)
    if not present_count:
        errors.append('NO_APPLICABLE_CONTENT')
    if used != by_id.keys():
        errors.append('UNASSIGNED_MEASUREMENTS')
    styles = style_findings(doc, manifest.get('style'))
    errors.extend(styles['errors'])
    pending = []
    for name in expected['reviews']:
        row = manifest.get('reviews', {}).get(name, {})
        try:
            if row.get('status') != 'reviewed' or row.get('drawing_sha256') != before or not text(row.get('finding')):
                raise ValueError('Current drawing review and findings required')
            artifact(row.get('evidence'), directory)
        except (ValueError, OSError):
            pending.append(name)
    if hashlib.sha256(path.read_bytes()).hexdigest() != before:
        errors.append('DRAWING_CHANGED_DURING_REVIEW')
    return {'technical_checks_passed': not errors, 'review_record_complete': not pending,
            'profile_ids': manifest['profile_ids'], 'drawing_sha256': before,
            'errors': errors, 'pending_reviews': pending, 'measurements': results, 'style': styles,
            'engineering_approval': False, 'recognition_accuracy_proven': False,
            'scope': 'Source-contract measurements and evidence binding; independent source reading and professional review required'}
