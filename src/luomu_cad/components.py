"""Luomu CAD components with explicit host-wall geometry.

Pure offline generation. Live AutoCAD insertion remains a CAD MCP operation.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import ezdxf
from ezdxf.lldxf.const import VALID_DXF_LINEWEIGHTS
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union

from .storage import ROOT, atomic_json

WINDOW_TYPES = {'window', 'slideWindow', 'floorWindow', 'highWindow', 'bay', 'glassWall'}


def layer_styles(spec: dict) -> tuple[str, dict]:
    mode = spec.get('opening_layer_mode', 'combined')
    if not isinstance(mode, str) or mode not in {'combined', 'by_type'}:
        raise ValueError('opening_layer_mode requires combined or by_type')
    values = {'wall': .25, 'door': .13, 'window': .13, 'furniture': .09}
    requested = spec.get('lineweights_mm', {})
    if not isinstance(requested, dict) or set(requested) - values.keys():
        raise ValueError('lineweights_mm accepts wall, door, window and furniture')
    values.update(requested)
    if mode == 'combined' and 'window' not in requested:
        values['window'] = values['door']
    units = {}
    for name, value in values.items():
        value = _number(value, f'{name} lineweight')
        if not 0 <= value <= 2.11:
            raise ValueError(f'{name} lineweight must be within the DXF range in mm')
        number = round(value * 100)
        if not math.isclose(value * 100, number, abs_tol=1e-8) or number not in VALID_DXF_LINEWEIGHTS:
            raise ValueError(f'{name} lineweight must be an available DXF lineweight in mm')
        units[name] = number
    if mode == 'combined' and units['window'] != units['door']:
        raise ValueError('Different door and window lineweights require by_type layers')
    layers = {'A-WALL': units['wall'], 'A-DOOR': units['door'], 'A-FURN': units['furniture']}
    if mode == 'by_type':
        layers['A-WINDOW'] = units['window']
    return mode, layers


def _node(action: str, plan: dict | None = None) -> dict:
    from .component_library import assemble, catalogue
    if action == 'catalog':
        return catalogue()
    if action == 'build':
        return assemble(plan)
    raise ValueError('Unknown component operation')


def catalogue(query: str = '') -> dict:
    value = _node('catalog')
    if query:
        value['furniture'] = [item for item in value['furniture']
                              if query.casefold() in json.dumps(item, ensure_ascii=False).casefold()]
    return value


def _number(value, label: str, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} requires a finite number')
    if positive and value <= 0:
        raise ValueError(f'{label} must be positive')
    return float(value)


def _ids(rows: list, label: str) -> dict:
    result = {}
    for row in rows:
        identity = row.get('id')
        if not isinstance(identity, str) or not identity or identity in result:
            raise ValueError(f'{label} requires unique nonempty string IDs')
        result[identity] = row
    return result


def validate(spec: dict, library: dict) -> tuple[dict, float]:
    plan = copy.deepcopy(spec)
    units = plan.get('units')
    if units == 'mm':
        scale = 1.0
    elif units == 'source':
        scale = _number(plan.get('library_scale'), 'library_scale', True)
        if not plan.get('scale_basis'):
            raise ValueError('Source coordinates require scale_basis for symbol sizing')
    else:
        raise ValueError('Explicit units mm or source required')
    nodes = _ids(plan.get('nodes', []), 'nodes')
    walls = _ids(plan.get('walls', []), 'walls')
    openings = _ids(plan.get('openings', []), 'openings')
    furniture = _ids(plan.get('furniture', []), 'furniture')
    for row in nodes.values():
        for name in ('x', 'y'):
            row[name] = _number(row.get(name), f'node {name}') / scale
    lengths = {}
    for identity, wall in walls.items():
        if wall.get('a') not in nodes or wall.get('b') not in nodes:
            raise ValueError(f'Wall {identity} references an unknown node')
        if wall.get('status', 'existing') == 'removed':
            raise ValueError('Removed walls require a separate demolition drawing')
        wall['t'] = _number(wall.get('t'), 'wall thickness', True) / scale
        a, b = nodes[wall['a']], nodes[wall['b']]
        length = math.hypot(b['x'] - a['x'], b['y'] - a['y'])
        if length < 1:
            raise ValueError('Wall is shorter than the component library 1 mm resolution')
        lengths[identity] = length
    opening_types = set(library['openings'])
    occupied = {}
    for identity, opening in openings.items():
        host = opening.get('wall')
        if host not in walls:
            raise ValueError(f'Opening {identity} requires an existing host wall')
        if opening.get('type') not in opening_types:
            raise ValueError('Unknown opening type')
        if type(opening.get('side')) is not int or opening['side'] not in (-1, 1):
            raise ValueError('Opening side must be explicitly +1 or -1')
        if type(opening.get('hinge')) is not bool:
            raise ValueError('Opening hinge must be explicitly true or false')
        if opening['type'] in ('bay', 'garage') and walls[host].get('exterior_side') not in (-1, 1):
            raise ValueError('Bay/garage requires explicit exterior_side on its wall')
        for name in ('pos', 'width'):
            opening[name] = _number(opening.get(name), name, name == 'width') / scale
        start = opening['pos'] - opening['width'] / 2
        end = opening['pos'] + opening['width'] / 2
        if start < 1 or end > lengths[host] - 1:
            raise ValueError('Opening must fit within host wall with a positive jamb at each end')
        for previous_start, previous_end in occupied.setdefault(host, []):
            if min(end, previous_end) - max(start, previous_start) >= -1:
                raise ValueError('Overlapping or touching openings require an explicit combined component')
        occupied[host].append((start, end))
    templates = {item['key']: item for item in library['furniture']}
    for item in furniture.values():
        template = templates.get(item.get('key'))
        if template is None or not template['native_geometry']:
            raise ValueError(f'Unsupported native component {item.get("key")}')
        if 'type' in item and item['type'] != template['type']:
            raise ValueError('Component type must match its catalogue key')
        for name in ('x', 'y', 'w', 'd', 'h'):
            if name in item:
                item[name] = _number(item[name], name, name in ('w', 'd', 'h')) / scale
        if 'rot' in item:
            _number(item['rot'], 'rot')
    plan.setdefault('nodes', [])
    plan.setdefault('walls', [])
    plan.setdefault('openings', [])
    plan.setdefault('furniture', [])
    return plan, scale


def _entity(space, geometry: dict, layer: str, scale: float):
    attributes = {'layer': layer, 'lineweight': -1,
                  'linetype': 'DASHED' if geometry.get('dashed') else 'BYLAYER'}
    def xy(point):
        return tuple(value * scale for value in point)
    kind = geometry['type']
    if kind == 'line':
        return space.add_line(xy(geometry['start']), xy(geometry['end']), dxfattribs=attributes)
    if kind == 'bezier':
        controls = [xy(point) for point in geometry['controls']]
        degree = len(controls) - 1
        return space.add_open_spline(controls, degree=degree,
                                     knots=[0] * (degree + 1) + [1] * (degree + 1), dxfattribs=attributes)
    if kind == 'text':
        attributes.update(insert=xy(geometry['point']), height=10 * scale)
        return space.add_text(geometry['text'], dxfattribs=attributes)
    if kind != 'ellipse_arc':
        raise ValueError(f'Unsupported native primitive {kind}')
    center = xy(geometry['center'])
    rx, ry = geometry['rx'] * scale, geometry['ry'] * scale
    angle, start, sweep = geometry['rotation'], geometry['start'], geometry['sweep']
    end = start + sweep
    if sweep < 0:
        start, end = end, start
    full = abs(sweep) >= math.tau - 1e-9
    if abs(rx - ry) < 1e-8:
        if full:
            return space.add_circle(center, rx, dxfattribs=attributes)
        return space.add_arc(center, rx, math.degrees(start + angle), math.degrees(end + angle),
                             dxfattribs=attributes)
    if ry > rx:
        rx, ry = ry, rx
        angle += math.pi / 2
        start -= math.pi / 2
        end -= math.pi / 2
    if full:
        start, end = 0, math.tau
    return space.add_ellipse(center, major_axis=(rx * math.cos(angle), rx * math.sin(angle)),
                             ratio=ry / rx, start_param=start % math.tau,
                             end_param=math.tau if full else end % math.tau, dxfattribs=attributes)


def review_single_door(document, handles: list[str], jambs: list, width: float,
                       leaf_thickness: float) -> dict:
    """Measure a saved single door against independent jamb/width requirements."""
    entities = [document.entitydb[handle] for handle in handles]
    arcs = [entity for entity in entities if entity.dxftype() == 'ARC']
    if len(arcs) != 1:
        raise ValueError('Single door requires exactly one native opening arc')
    arc = arcs[0]
    center = tuple(arc.dxf.center)[:2]
    gap = min(math.dist(center, point) for point in jambs)
    radius_error = abs(arc.dxf.radius - width)
    if gap > 1e-6 or radius_error > 1e-6:
        raise ValueError('Door hinge or arc radius disagrees with its measured opening')
    axis = ((jambs[1][0] - jambs[0][0]) / width, (jambs[1][1] - jambs[0][1]) / width)
    lines = [entity for entity in entities if entity.dxftype() == 'LINE']
    leaf_edges = [line for line in lines if abs((line.dxf.end - line.dxf.start).magnitude - width) < 1e-6]
    if len(leaf_edges) < 2:
        raise ValueError('Door requires native open-leaf edges')
    half = leaf_thickness / 2
    arc_endpoints = [tuple(arc.start_point)[:2], tuple(arc.end_point)[:2]]
    for line in leaf_edges:
        vector = line.dxf.end - line.dxf.start
        if abs(vector.x * axis[0] + vector.y * axis[1]) > 1e-6:
            raise ValueError('Door leaf lies along its wall instead of at the opening angle')
        points = [tuple(line.dxf.start)[:2], tuple(line.dxf.end)[:2]]
        near, far = sorted(points, key=lambda point: math.dist(point, center))
        if abs(math.dist(near, center) - half) > 1e-6:
            raise ValueError('Open leaf is detached from its hinge')
        if min(abs(math.dist(far, point) - half) for point in arc_endpoints) > 1e-6:
            raise ValueError('Open leaf and swing arc do not meet')
    return {'hinge_gap': gap, 'radius_error': radius_error, 'open_leaf_edges': len(leaf_edges)}


def build(spec: dict, directory: Path) -> dict:
    """Write a new component bundle and read its DXF back. No AutoCAD contact."""
    layer_mode, layers = layer_styles(spec)
    plan, scale = validate(spec, catalogue())
    geometry = _node('build', plan)
    regions = unary_union([Polygon(row['polygon']) for row in geometry['walls']])
    checks = []
    for opening in geometry['openings']:
        jambs = opening['jambs']
        # A small interior strip through the complete opening catches walls/joints
        # left across a void while excluding the intentional jamb boundaries.
        host = next(wall for wall in plan['walls'] if wall['id'] == opening['wall'])
        spec_opening = next(row for row in plan['openings'] if row['id'] == opening['id'])
        side = spec_opening['side']
        dx, dy = jambs[1][0] - jambs[0][0], jambs[1][1] - jambs[0][1]
        width = math.hypot(dx, dy)
        normal = (-dy / width * side, dx / width * side)
        inner = [[point[0] - normal[0] * host['t'] / 2,
                  point[1] - normal[1] * host['t'] / 2] for point in jambs]
        void = LineString(inner).buffer(host['t'] / 2 - 1e-5, cap_style='flat')
        collision = regions.intersection(void).area
        if collision > 1e-5:
            raise ValueError(f'Wall material crosses opening {opening["id"]}')
        distances = [regions.boundary.distance(Point(point)) for point in jambs]
        if max(distances) > 1e-5:
            raise ValueError(f'Opening {opening["id"]} is detached from its jambs')
        checks.append({'id': opening['id'], 'wall_overlap_area': collision * scale ** 2,
                       'jamb_gaps': [distance * scale for distance in distances]})
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / 'components.dxf'
    if target.exists():
        raise FileExistsError('Use a new output directory to preserve an existing component bundle')
    document = ezdxf.new('R2013')
    document.units = 4 if spec['units'] == 'mm' else 0
    document.header['$LWDISPLAY'] = False
    document.linetypes.new('DASHED', dxfattribs={'pattern': [12, 8, -4]})
    for layer, weight in layers.items():
        document.layers.new(layer, dxfattribs={'lineweight': weight})
    space = document.modelspace()
    polygons = list(regions.geoms) if hasattr(regions, 'geoms') else [regions]
    for polygon in polygons:
        if polygon.is_empty:
            continue
        for ring in [polygon.exterior, *polygon.interiors]:
            space.add_lwpolyline([(x * scale, y * scale) for x, y in list(ring.coords)[:-1]],
                                 close=True, dxfattribs={'layer': 'A-WALL', 'const_width': 0})
    mappings = []
    for category in ('openings', 'furniture'):
        for component in geometry[category]:
            layer = 'A-FURN' if category == 'furniture' else 'A-DOOR'
            if category == 'openings' and layer_mode == 'by_type' and component['type'] in WINDOW_TYPES:
                layer = 'A-WINDOW'
            handles = [_entity(space, entity, layer, scale).dxf.handle for entity in component['entities']]
            mappings.append({'id': component['id'], 'category': category, 'layer': layer, 'handles': handles})
    document.saveas(target)
    restored = ezdxf.readfile(target)
    auditor = restored.audit()
    if auditor.errors or auditor.fixes:
        raise ValueError('Saved component DXF failed native readback audit')
    from .professional import style_findings
    style_rules = {
        layer: {'lineweight_mm': [max(.01, weight / 100), max(.01, weight / 100)],
                'linetypes': ['CONTINUOUS', 'DASHED'], 'polyline_width': [0, 0]}
        for layer, weight in layers.items()
    }
    styles = style_findings(restored, {'basis': 'Component layer settings', 'layers': style_rules})
    if styles['errors'] and styles['errors'] != ['EMPTY_DRAWING']:
        raise ValueError('Saved component line style check failed: ' + ', '.join(styles['errors']))
    for mapping in mappings:
        if any(restored.entitydb[handle].dxf.layer != mapping['layer'] for handle in mapping['handles']):
            raise ValueError('Saved component layer differs from its source mapping')
    restored_regions = Polygon()
    for entity in restored.modelspace().query('LWPOLYLINE[layer=="A-WALL"]'):
        restored_regions = restored_regions.symmetric_difference(Polygon(
            [(x / scale, y / scale) for x, y in entity.get_points('xy')]))
    if regions.symmetric_difference(restored_regions).area > 1e-5:
        raise ValueError('Saved wall contours disagree with the cut host-wall geometry')
    door_checks = []
    for opening in geometry['openings']:
        if opening['type'] != 'door':
            continue
        mapping = next(row for row in mappings if row['category'] == 'openings' and row['id'] == opening['id'])
        jambs = [[value * scale for value in point] for point in opening['jambs']]
        width = math.dist(*jambs)
        measurement = review_single_door(restored, mapping['handles'], jambs, width, 40 * scale)
        door_checks.append({'id': opening['id'], **measurement})
    result = {'schema_version': 1, 'units': spec['units'], 'library_scale': scale,
              'dxf': str(target), 'entity_count': len(restored.modelspace()),
              'opening_checks': checks, 'single_door_readback': door_checks, 'source_to_entities': mappings,
              'style_readback': {'layer_lineweights_hundredths_mm': layers,
                                 'checked_entities': len(styles['entities']), 'errors': styles['errors'],
                                 'plot_style_verified': False},
              'geometry_passed': True, 'reference_similarity_verified': False,
              'component_library': 'luomu-cad', 'component_revision': '0.11.0'}
    atomic_json(directory / 'native-geometry.json', {'coordinate_units': 'library_mm',
                'drawing_units_per_library_mm': scale, **geometry})
    atomic_json(directory / 'component-report.json', result)
    return result
