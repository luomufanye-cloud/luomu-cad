"""Source-derived raster representation checks, separate from pixel matching.

Budgets and component bounds belong to the reviewed source inventory. They are
not universal CAD limits or proof that a raster has been understood correctly.
"""
import math

from ezdxf import bbox


def finite(value, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Finite numeric source value required')
    if positive and value <= 0:
        raise ValueError('Positive source value required')
    return value


def source_point(value):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError('Source point must contain three coordinates')
    return tuple(finite(v) for v in value)


def coordinate_basis(inventory):
    units = inventory.get('units')
    if type(units) is not int or units not in (0, 4):
        raise ValueError('Redraw requires explicit mm units=4 or unscaled source units=0')
    scale = inventory.get('scale', {})
    if units == 0:
        if (not isinstance(scale, dict) or scale.get('status') != 'unscaled'
                or not isinstance(scale.get('basis'), str) or not scale['basis'].strip()):
            raise ValueError('Unscaled redraw requires scale.status=unscaled and a source coordinate basis')
        if any(o.get('kind') == 'DIMENSION' for o in inventory.get('objects', [])):
            raise ValueError('Unscaled source coordinates cannot establish native measured dimensions')
        return {'status': 'unscaled', 'dimension_accuracy_accepted': False}
    if scale and (not isinstance(scale, dict) or scale.get('status') != 'calibrated'):
        raise ValueError('Millimetre redraw cannot carry an unscaled coordinate declaration')
    return {'status': 'millimetres', 'dimension_accuracy_accepted': False}


def _vertices(entity):
    kind = entity.dxftype()
    if kind == 'LWPOLYLINE':
        return len(entity)
    if kind == 'SPLINE':
        return len(entity.control_points) + len(entity.fit_points)
    if kind == 'HATCH':
        return sum(len(p.vertices) if hasattr(p, 'vertices') else len(p.edges) for p in entity.paths)
    return 2 if kind == 'LINE' else 1


def _boundary_points(entity):
    if entity.dxftype() == 'LINE':
        return [tuple(entity.dxf.start), tuple(entity.dxf.end)]
    if entity.dxftype() == 'LWPOLYLINE':
        return [tuple(p) for p in entity.vertices_in_wcs()]
    raise ValueError('Door leaf requires native LINE or LWPOLYLINE boundaries')


def raster_findings(doc, inventory, mapping):
    """Check saved native geometry against independently declared components."""
    quality = inventory.get('raster_quality')
    if not isinstance(quality, dict):
        return {'errors': ['RASTER_COMPONENT_INVENTORY_REQUIRED'], 'components': []}
    components = quality.get('components')
    if not isinstance(components, list) or not components:
        raise ValueError('Nonempty raster component inventory required')
    source_ids = {o['id'] for o in inventory['objects']}
    by_handle = {e.dxf.handle: e for e in doc.modelspace()}
    covered = set()
    errors, reports, component_ids = [], [], set()
    for component in components:
        cid = component.get('id')
        if not isinstance(cid, str) or not cid.strip() or cid in component_ids:
            raise ValueError('Unique raster component IDs required')
        component_ids.add(cid)
        ids = component.get('object_ids')
        if (not isinstance(ids, list) or not ids or any(not isinstance(x, str) for x in ids)
                or len(ids) != len(set(ids)) or set(ids) - source_ids):
            raise ValueError('Component must identify distinct known source objects')
        if covered.intersection(ids):
            raise ValueError('Raster object cannot be hidden in overlapping component budgets')
        covered.update(ids)
        depiction = component.get('depiction')
        if depiction not in ('linework', 'solid_fill'):
            raise ValueError('Component depiction must be linework or solid_fill')
        if not component.get('source_locator') or not component.get('budget_basis'):
            raise ValueError('Component source locator and representation budget basis required')
        for key in ('max_entities', 'max_vertices'):
            if type(component.get(key)) is not int or component[key] <= 0:
                raise ValueError('Positive component representation budgets required')
        entities = [by_handle[mapping[x]] for x in ids if mapping.get(x) in by_handle]
        if len(entities) != len(ids):
            errors.append('RASTER_COMPONENT_MISSING:' + cid)
        allowed = ({'LINE', 'ARC', 'CIRCLE', 'ELLIPSE', 'LWPOLYLINE', 'SPLINE', 'TEXT', 'MTEXT', 'DIMENSION'}
                   if depiction == 'linework' else {'HATCH', 'SOLID', 'TRACE'})
        if any(e.dxftype() not in allowed for e in entities):
            errors.append('RASTER_REPRESENTATION:' + cid)
        if depiction == 'solid_fill' and any(e.dxftype() == 'HATCH' and not e.dxf.solid_fill for e in entities):
            errors.append('RASTER_FILL_NOT_SOLID:' + cid)
        vertices = sum(_vertices(e) for e in entities)
        if len(entities) > component['max_entities'] or vertices > component['max_vertices']:
            errors.append('RASTER_COMPLEXITY:' + cid)
        bounds = component.get('source_bounds')
        tolerance = finite(component.get('tolerance'), positive=True)
        if not isinstance(bounds, list) or len(bounds) != 4:
            raise ValueError('Source bounds require xmin/ymin/xmax/ymax')
        bounds = [finite(v) for v in bounds]
        if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
            raise ValueError('Nonempty source bounds required')
        extent = bbox.extents(entities)
        if not extent.has_data:
            errors.append('RASTER_BOUNDS_UNAVAILABLE:' + cid)
        else:
            actual = [extent.extmin.x, extent.extmin.y, extent.extmax.x, extent.extmax.y]
            if any(abs(a - b) > tolerance for a, b in zip(actual, bounds)):
                errors.append('RASTER_SOURCE_BOUNDS:' + cid)
        reports.append({'id': cid, 'entities': len(entities), 'vertices': vertices})
    if covered != source_ids:
        errors.append('RASTER_COMPONENT_COVERAGE')
    doors = quality.get('doors')
    if not isinstance(doors, list):
        raise ValueError('Explicit raster door relationships required; use [] when source has no doors')
    door_ids = set()
    for door in doors:
        did = door.get('id')
        if not isinstance(did, str) or not did.strip() or did in door_ids or not door.get('source_locator'):
            raise ValueError('Unique source-located door IDs required')
        door_ids.add(did)
        hinge, closed, opened = [source_point(door[k]) for k in ('hinge', 'closed_tip', 'open_tip')]
        tolerance = finite(door.get('tolerance'), positive=True)
        sweep = finite(door.get('sweep_degrees'), positive=True)
        if sweep >= 360:
            raise ValueError('Door opening sweep must be below a full circle')
        radius = math.dist(hinge, closed)
        if radius <= tolerance or abs(math.dist(hinge, opened) - radius) > tolerance:
            raise ValueError('Source door tips must share a nonzero hinge radius')
        arc = by_handle.get(mapping.get(door.get('arc_id')))
        if arc is None or arc.dxftype() != 'ARC':
            errors.append('DOOR_NATIVE_ARC:' + did)
            continue
        endpoints = [tuple(arc.start_point), tuple(arc.end_point)]
        if (math.dist(arc.dxf.center, hinge) > tolerance or abs(arc.dxf.radius - radius) > tolerance
                or not any(math.dist(endpoints[i], closed) <= tolerance and
                           math.dist(endpoints[1-i], opened) <= tolerance for i in (0, 1))
                or abs((arc.dxf.end_angle - arc.dxf.start_angle) % 360 - sweep) > 1e-6):
            errors.append('DOOR_HINGE_SWEEP:' + did)
        leaf_ids = door.get('leaf_ids')
        if not isinstance(leaf_ids, list) or not leaf_ids or any(x not in source_ids for x in leaf_ids):
            raise ValueError('Door must reference its native leaf source objects')
        leaves = [by_handle.get(mapping.get(x)) for x in leaf_ids]
        if any(e is None for e in leaves):
            errors.append('DOOR_LEAF_MISSING:' + did)
        else:
            points = [p for e in leaves for p in _boundary_points(e)]
            if any(min(math.dist(p, q) for q in points) > tolerance for p in (hinge, opened)):
                errors.append('DOOR_LEAF_HINGE:' + did)
    return {'errors': errors, 'components': reports,
            'scope': 'Declared component bounds, representation budgets and door hinge/leaf/arc relationships; wall joints and source completeness require visual review'}
