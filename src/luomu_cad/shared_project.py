"""Source-linked room drawings and revisioned atlases from one explicit mm model.

This module projects supplied geometry. It does not infer construction systems,
structural wall status, door leaves, service sizing or material specifications.
"""
from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path

import ezdxf
from shapely.geometry import LineString, Polygon, box

from .annotations import configure_cjk_style, short_extensions, text_style_findings
from .casework import display_signature, normalize as cabinet_model, number
from .qa import file_hash
from .storage import atomic_json, digest, inside, workspace_lock

KINDS = {'plan', 'floor', 'ceiling', 'elevation', 'section'}
WEIGHTS = {'outline': 25, 'cut': 35, 'hidden': 13, 'annotation': 13}


def fields(value, allowed, label):
    if not isinstance(value, dict) or set(value) - set(allowed.split()):
        raise ValueError('Unknown or invalid ' + label + ' fields')


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
        raise ValueError('IDs require 1..64 ASCII letters, digits, underscores or hyphens')
    return value


def text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 100 or any(ord(c) < 32 for c in value):
        raise ValueError(label + ' requires one nonempty line of at most 100 characters')
    return value


def finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + ' requires a finite number')
    return float(value)


def point(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('XY points require two explicit mm coordinates')
    return [finite(v, 'coordinate') for v in value]


def walls(model):
    result = {}
    for room in model['rooms']:
        pts = room['boundary_mm']
        for i, (a, b) in enumerate(zip(pts, pts[1:] + pts[:1]), 1):
            length = math.dist(a, b)
            u = [(b[j]-a[j])/length for j in range(2)]
            result[room['id'] + ':W' + str(i)] = {
                'room': room['id'], 'a': a, 'b': b, 'u': u, 'n': [u[1], -u[0]],
                'length': length, 'thickness': room['wall_thickness_mm'],
                'bottom': room['floor_z_mm'], 'top': room['ceiling_z_mm'],
            }
    return result


def world(wall, along, inward=0):
    return [wall['a'][i]+wall['u'][i]*along+wall['n'][i]*inward for i in range(2)]


def wall_shape(wall):
    return Polygon([wall['a'], wall['b'], world(wall, wall['length'], -wall['thickness']),
                    world(wall, 0, -wall['thickness'])])


def normalize(spec):
    fields(spec, 'schema_version id units revision materials rooms openings cabinets sheets references changes', 'project')
    m = copy.deepcopy(spec)
    if type(m.get('schema_version')) is not int or m['schema_version'] != 1 or m.get('units') != 'mm':
        raise ValueError('Shared projects require schema_version=1 and units=mm')
    identifier(m.get('id')); text(m.get('revision'), 'revision')
    for collection in ('materials', 'rooms', 'openings', 'cabinets', 'sheets', 'references'):
        if not isinstance(m.setdefault(collection, []), list):
            raise ValueError(collection + ' must be a list')
    if not m['rooms'] or not m['sheets'] or len(m['sheets']) > 39:
        raise ValueError('Require rooms and 1..39 sheets for the single-page catalogue')
    objects = set()
    def claim(value):
        identifier(value)
        if value in objects:
            raise ValueError('Duplicate project object ID: ' + value)
        objects.add(value)
    material_ids = set()
    for row in m['materials']:
        fields(row, 'id description source', 'material')
        claim(row.get('id')); material_ids.add(row['id'])
        text(row.get('description'), 'material description')
        text(row.get('source'), 'material source/basis')
    def material(value):
        if value not in material_ids:
            raise ValueError('Unknown material: ' + str(value))
    for room in m['rooms']:
        fields(room, 'id name boundary_mm floor_z_mm ceiling_z_mm wall_thickness_mm finishes', 'room')
        claim(room.get('id')); text(room.get('name'), 'room name')
        if not isinstance(room.get('boundary_mm'), list) or not 3 <= len(room['boundary_mm']) <= 100:
            raise ValueError('Room requires 3..100 clockwise finished-face vertices')
        room['boundary_mm'] = [point(p) for p in room['boundary_mm']]
        poly = Polygon(room['boundary_mm'])
        if not poly.is_valid or poly.area <= 1 or poly.exterior.is_ccw or len(set(map(tuple, room['boundary_mm']))) != len(room['boundary_mm']):
            raise ValueError('Room boundary must be a simple clockwise finished-face polygon without duplicate vertices')
        room['floor_z_mm'] = finite(room.get('floor_z_mm'), 'floor elevation')
        room['ceiling_z_mm'] = finite(room.get('ceiling_z_mm'), 'ceiling elevation')
        if room['ceiling_z_mm'] <= room['floor_z_mm']:
            raise ValueError('Ceiling must be above finished floor')
        room['wall_thickness_mm'] = number(room.get('wall_thickness_mm'), 'wall thickness')
        fields(room.get('finishes'), 'floor ceiling walls', 'room finishes')
        if set(room['finishes']) != {'floor', 'ceiling', 'walls'}:
            raise ValueError('Declare floor, ceiling and wall finishes explicitly')
        for value in room['finishes'].values():
            material(value)
    for i, room in enumerate(m['rooms']):
        for other in m['rooms'][i+1:]:
            if Polygon(room['boundary_mm']).intersection(Polygon(other['boundary_mm'])).area > 1e-6:
                raise ValueError('Room interiors overlap')
    hosts = walls(m)
    for opening in m['openings']:
        fields(opening, 'id host kind offset_mm width_mm sill_z_mm height_mm', 'opening')
        claim(opening.get('id'))
        if opening.get('host') not in hosts or opening.get('kind') not in {'door', 'window'}:
            raise ValueError('Opening requires a known wall host and door/window kind')
        w = hosts[opening['host']]
        opening['offset_mm'] = number(opening.get('offset_mm'), 'opening offset', zero=True)
        opening['width_mm'] = number(opening.get('width_mm'), 'opening width')
        opening['sill_z_mm'] = finite(opening.get('sill_z_mm'), 'opening sill absolute elevation')
        opening['height_mm'] = number(opening.get('height_mm'), 'opening height')
        if opening['offset_mm']+opening['width_mm'] > w['length'] or opening['sill_z_mm'] < w['bottom'] or opening['sill_z_mm']+opening['height_mm'] > w['top']:
            raise ValueError('Opening lies outside its wall host')
    for i, a in enumerate(m['openings']):
        for b in m['openings'][i+1:]:
            if a['host'] == b['host'] and box(a['offset_mm'], a['sill_z_mm'], a['offset_mm']+a['width_mm'], a['sill_z_mm']+a['height_mm']).intersection(box(b['offset_mm'], b['sill_z_mm'], b['offset_mm']+b['width_mm'], b['sill_z_mm']+b['height_mm'])).area > 1e-6:
                raise ValueError('Hosted openings overlap')
    occupied = []
    for c in m['cabinets']:
        fields(c, 'id host offset_mm base_z_mm material spec', 'hosted cabinet')
        claim(c.get('id')); material(c.get('material'))
        if c.get('host') not in hosts:
            raise ValueError('Cabinet requires a known wall host')
        w = hosts[c['host']]
        c['offset_mm'] = number(c.get('offset_mm'), 'cabinet offset', zero=True)
        c['base_z_mm'] = finite(c.get('base_z_mm'), 'cabinet base absolute elevation')
        cm = cabinet_model(c.get('spec'))
        if cm['id'] != c['id']:
            raise ValueError('Cabinet ID must equal its casework model ID')
        if c['offset_mm']+cm['width_mm'] > w['length'] or c['base_z_mm'] < w['bottom'] or c['base_z_mm']+cm['overall_height_mm'] > w['top']:
            raise ValueError('Cabinet lies outside its wall host')
        poly = Polygon([world(w, c['offset_mm']+x, y) for x, y in [(0, 0), (cm['width_mm'], 0), (cm['width_mm'], cm['depth_mm']), (0, cm['depth_mm'])]])
        room = next(r for r in m['rooms'] if r['id'] == w['room'])
        if not Polygon(room['boundary_mm']).buffer(1e-6).covers(poly):
            raise ValueError('Cabinet footprint lies outside its finished room')
        for other, z0, z1 in occupied:
            if min(z1, c['base_z_mm']+cm['overall_height_mm']) > max(z0, c['base_z_mm']) and other.intersection(poly).area > 1e-6:
                raise ValueError('Cabinets intersect')
        occupied.append((poly, c['base_z_mm'], c['base_z_mm']+cm['overall_height_mm']))
        for op in m['openings']:
            if op['host'] == c['host'] and min(op['offset_mm']+op['width_mm'], c['offset_mm']+cm['width_mm']) > max(op['offset_mm'], c['offset_mm']) and min(op['sill_z_mm']+op['height_mm'], c['base_z_mm']+cm['overall_height_mm']) > max(op['sill_z_mm'], c['base_z_mm']):
                raise ValueError('Cabinet obstructs a hosted opening')
    sheet_ids = set()
    room_ids = {r['id'] for r in m['rooms']}
    for sheet in m['sheets']:
        fields(sheet, 'id title kind room host scale paper_mm cut_z_mm axis at_mm direction', 'sheet')
        identifier(sheet.get('id')); text(sheet.get('title'), 'sheet title')
        if sheet['id'] in sheet_ids:
            raise ValueError('Duplicate sheet ID')
        sheet_ids.add(sheet['id'])
        if sheet.get('kind') not in KINDS or sheet.get('room') not in room_ids:
            raise ValueError('Sheet requires a supported kind and known room')
        sheet['scale'] = number(sheet.get('scale'), 'sheet scale')
        sheet['paper_mm'] = point(sheet.get('paper_mm'))
        if min(sheet['paper_mm']) < 150 or max(sheet['paper_mm']) > 2000:
            raise ValueError('Unsupported paper dimensions')
        if sheet['kind'] == 'elevation' and (sheet.get('host') not in hosts or hosts[sheet['host']]['room'] != sheet['room']):
            raise ValueError('Elevation requires a wall host in its room')
        if sheet['kind'] == 'plan':
            sheet['cut_z_mm'] = finite(sheet.get('cut_z_mm'), 'plan cut elevation')
            r = next(r for r in m['rooms'] if r['id'] == sheet['room'])
            if not r['floor_z_mm'] < sheet['cut_z_mm'] < r['ceiling_z_mm']:
                raise ValueError('Plan cut must be inside room height')
        if sheet['kind'] == 'section':
            if sheet.get('axis') not in {'x', 'y'} or sheet.get('direction') not in {-1, 1} or isinstance(sheet.get('direction'), bool):
                raise ValueError('Section requires axis=x/y and viewing direction=-1/+1')
            sheet['at_mm'] = finite(sheet.get('at_mm'), 'section cut coordinate')
    for ref in m['references']:
        fields(ref, 'id source_sheet target_sheet object_id', 'drawing reference')
        identifier(ref.get('id'))
        if any(r is not ref and r.get('id') == ref['id'] for r in m['references']):
            raise ValueError('Duplicate reference ID')
        if ref.get('source_sheet') not in sheet_ids or ref.get('target_sheet') not in sheet_ids or ref['source_sheet'] == ref['target_sheet']:
            raise ValueError('Drawing reference requires two distinct existing sheets')
        if ref.get('object_id') not in objects | hosts.keys():
            raise ValueError('Drawing reference object does not exist')
        src = next(s for s in m['sheets'] if s['id'] == ref['source_sheet'])
        dst = next(s for s in m['sheets'] if s['id'] == ref['target_sheet'])
        if src['kind'] not in {'plan', 'floor', 'ceiling'} or dst['kind'] not in {'elevation', 'section'} or src['room'] != dst['room']:
            raise ValueError('References currently connect a room plan to its elevation/section')
        if dst['kind'] == 'elevation' and ref['object_id'] != dst['host']:
            raise ValueError('Elevation reference must identify its actual host wall')
        if dst['kind'] == 'section' and ref['object_id'] != dst['room']:
            raise ValueError('Section reference must identify its actual room')
    changes = m.setdefault('changes', [])
    if not isinstance(changes, list) or len(changes) > 12:
        raise ValueError('Use at most 12 revision descriptions')
    for value in changes:
        text(value, 'revision description')
    return m


def _parts(geometry):
    if geometry.is_empty:
        return []
    return list(geometry.geoms) if hasattr(geometry, 'geoms') else [geometry]


def project(model, sheet):
    """Return logical primitives before paper placement; every row has an owner."""
    hosts = walls(model)
    room = next(r for r in model['rooms'] if r['id'] == sheet['room'])
    rows = []
    def line(owner, key, a, b, role='outline'):
        if math.dist(a, b) > 1e-7:
            rows.append({'kind': 'LINE', 'owner': owner, 'key': key, 'a': list(a), 'b': list(b), 'role': role})
    def rect(owner, key, bounds, role='outline'):
        x0, y0, x1, y1 = bounds
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        for i in range(4):
            line(owner, key+':'+str(i), pts[i], pts[(i+1) % 4], role)
    def outline(owner, key, geom, role='outline'):
        for i, poly in enumerate(_parts(geom)):
            if not isinstance(poly, Polygon):
                continue
            for j, ring in enumerate([poly.exterior, *poly.interiors]):
                pts = list(ring.coords)
                for k, (a, b) in enumerate(zip(pts, pts[1:])):
                    line(owner, f'{key}:{i}:{j}:{k}', a, b, role)
    def label(owner, key, value, at):
        rows.append({'kind': 'TEXT', 'owner': owner, 'key': key, 'text': value, 'a': list(at), 'role': 'annotation'})
    def dim(owner, key, a, b, angle=0, lane=1, side=None):
        rows.append({'kind': 'DIMENSION', 'owner': owner, 'key': key, 'a': list(a), 'b': list(b), 'angle': angle, 'lane': lane, 'side': side, 'role': 'annotation'})
    kind = sheet['kind']
    room_hosts = {k: v for k, v in hosts.items() if v['room'] == room['id']}
    xmin, ymin, xmax, ymax = Polygon(room['boundary_mm']).bounds
    if kind in {'plan', 'floor', 'ceiling'}:
        boundary = Polygon(room['boundary_mm'])
        # One continuous offset ring also fills convex outside corners correctly.
        wall_ring = boundary.buffer(room['wall_thickness_mm'], join_style=2).difference(boundary)
        for wid, w in room_hosts.items():
            if kind == 'plan':
                for op in model['openings']:
                    if op['host'] == wid and op['sill_z_mm'] <= sheet['cut_z_mm'] < op['sill_z_mm']+op['height_mm']:
                        a, b = op['offset_mm'], op['offset_mm']+op['width_mm']
                        hole = Polygon([world(w, a, 1), world(w, b, 1), world(w, b, -w['thickness']-1), world(w, a, -w['thickness']-1)])
                        wall_ring = wall_ring.difference(hole)
                        label(op['id'], 'id', op['id'], world(w, (a+b)/2, 150))
                        # Dimension follows the true host direction; no fixed text override.
                        angle = math.degrees(math.atan2(w['u'][1], w['u'][0])) % 180
                        dim(op['id'], 'width', world(w, a), world(w, b), angle, 2)
        outline(room['id'], 'walls', wall_ring, 'cut' if kind == 'plan' else 'outline')
        mat_key = {'floor': 'floor', 'ceiling': 'ceiling', 'plan': 'walls'}[kind]
        mat_id = room['finishes'][mat_key]
        z = room['ceiling_z_mm'] if kind == 'ceiling' else room['floor_z_mm']
        label(room['id'], 'room', room['name'], [xmin, ymax+sheet['scale']*7])
        label(room['id'], 'finish', f'{mat_id} / Z={z:g}', [xmin, ymax+sheet['scale']*12])
        # Room bbox dimensions are explicitly labelled as extents, not wall lengths.
        dim(room['id'], 'extent_x', [xmin, ymin], [xmax, ymin], lane=4)
        dim(room['id'], 'extent_y', [xmin, ymin], [xmin, ymax], 90, 4)
        if kind == 'plan':
            from .casework import draw
            for c in model['cabinets']:
                if c['host'] not in room_hosts:
                    continue
                cm = cabinet_model(c['spec']); w = hosts[c['host']]
                raw = copy.deepcopy(c['spec']); raw['sheet'] = {'scale': 100, 'paper_mm': [2000, 2000]}
                _, local = draw(raw)
                origin = local['views']['plan']['origin']
                for row in local['geometry']:
                    if row['kind'] == 'LINE' and row.get('view') == 'plan' and row['role'] != 'annotation':
                        def transform(p):
                            return world(w, c['offset_mm']+p[0]-origin[0], cm['depth_mm']-(p[1]-origin[1]))
                        line(c['id'], 'plan:'+row['key'], transform(row['start']), transform(row['end']), row['role'])
                label(c['id'], 'id', c['id']+' / '+c['material'], world(w, c['offset_mm'], cm['depth_mm']+150))
                dim(c['id'], 'width', world(w, c['offset_mm'], cm['depth_mm']), world(w, c['offset_mm']+cm['width_mm'], cm['depth_mm']), math.degrees(math.atan2(w['u'][1], w['u'][0])) % 180)
                angle = math.degrees(math.atan2(w['n'][1], w['n'][0])) % 180
                normal = [-math.sin(math.radians(angle)), math.cos(math.radians(angle))]
                side = -1 if sum(w['u'][i]*normal[i] for i in range(2)) > 0 else 1
                dim(c['id'], 'depth', world(w, c['offset_mm']), world(w, c['offset_mm'], cm['depth_mm']), angle, 1, side)
    elif kind == 'elevation':
        wid = sheet['host']; w = hosts[wid]
        rect(wid, 'finished_wall', [0, w['bottom'], w['length'], w['top']])
        label(wid, 'finish', room['finishes']['walls'], [0, w['top']+sheet['scale']*7])
        dim(wid, 'length', [0, w['bottom']], [w['length'], w['bottom']], lane=4)
        dim(wid, 'height', [0, w['bottom']], [0, w['top']], 90, 4)
        for op in model['openings']:
            if op['host'] != wid:
                continue
            x, z, width, height = (op[k] for k in ('offset_mm', 'sill_z_mm', 'width_mm', 'height_mm'))
            rect(op['id'], 'opening', [x, z, x+width, z+height])
            label(op['id'], 'id', op['id'], [x, z+height+sheet['scale']*3])
            dim(op['id'], 'width', [x, z], [x+width, z], lane=2)
            dim(op['id'], 'height', [x, z], [x, z+height], 90, 2)
        from .casework import draw
        for c in model['cabinets']:
            if c['host'] != wid:
                continue
            raw = copy.deepcopy(c['spec']); raw['sheet'] = {'scale': 100, 'paper_mm': [2000, 2000]}
            _, local = draw(raw); origin = local['views']['front']['origin']
            for row in local['geometry']:
                if row['kind'] == 'LINE' and row.get('view') == 'front':
                    def transform(p):
                        return [c['offset_mm']+p[0]-origin[0], c['base_z_mm']+p[1]-origin[1]]
                    line(c['id'], 'front:'+row['key'], transform(row['start']), transform(row['end']), row['role'])
            cm = cabinet_model(c['spec']); x, z = c['offset_mm'], c['base_z_mm']
            cursor = x
            for i, width in enumerate(cm['front_widths_mm'], 1):
                dim(c['id'], 'module.'+str(i), [cursor, z], [cursor+width, z])
                cursor += width
            dim(c['id'], 'width', [x, z], [x+cm['width_mm'], z], lane=2)
            dim(c['id'], 'height', [x, z], [x, z+cm['overall_height_mm']], 90)
            label(c['id'], 'id', c['id']+' / '+c['material'], [x, z+cm['overall_height_mm']+sheet['scale']*3])
    else:
        axis = 0 if sheet['axis'] == 'x' else 1
        span_axis = 1-axis; at = sheet['at_mm']; direction = sheet['direction']
        # x=constant looking +X: right is -Y; y=constant looking +Y: right is +X.
        sign = direction * (-1 if axis == 0 else 1)
        span_min, span_max = (ymin, ymax) if axis == 0 else (xmin, xmax)
        def cp(v):
            p = [0, 0]; p[axis] = at; p[span_axis] = v; return p
        cut = LineString([cp(span_min-10000), cp(span_max+10000)])
        inside_spans = [g for g in _parts(Polygon(room['boundary_mm']).intersection(cut)) if isinstance(g, LineString) and g.length > 1e-6]
        if not inside_spans:
            raise ValueError('Section cut does not cross its room interior')
        for i, span in enumerate(inside_spans):
            vals = [p[span_axis]*sign for p in span.coords]
            lo, hi = min(vals), max(vals)
            line(room['id'], f'floor:{i}', [lo, room['floor_z_mm']], [hi, room['floor_z_mm']], 'cut')
            line(room['id'], f'ceiling:{i}', [lo, room['ceiling_z_mm']], [hi, room['ceiling_z_mm']], 'cut')
            label(room['id'], f'floor_finish:{i}', room['finishes']['floor']+f" / Z={room['floor_z_mm']:g}", [lo, room['floor_z_mm']-sheet['scale']*8])
            label(room['id'], f'ceiling_finish:{i}', room['finishes']['ceiling']+f" / Z={room['ceiling_z_mm']:g}", [lo, room['ceiling_z_mm']+sheet['scale']*8])
            dim(room['id'], f'clear_height:{i}', [lo, room['floor_z_mm']], [lo, room['ceiling_z_mm']], 90, 4)
        for wid, w in room_hosts.items():
            for i, span in enumerate(_parts(wall_shape(w).intersection(cut))):
                if not isinstance(span, LineString) or span.length <= 1e-6:
                    continue
                lo, hi = sorted([p[span_axis]*sign for p in (span.coords[0], span.coords[-1])])
                shape = box(lo, w['bottom'], hi, w['top'])
                for op in model['openings']:
                    if op['host'] != wid:
                        continue
                    oa, ob = op['offset_mm'], op['offset_mm']+op['width_mm']
                    hole = Polygon([world(w, oa, 1), world(w, ob, 1), world(w, ob, -w['thickness']-1), world(w, oa, -w['thickness']-1)])
                    for gap in _parts(hole.intersection(cut)):
                        if isinstance(gap, LineString) and gap.length > 1e-6:
                            values = [p[span_axis]*sign for p in gap.coords]
                            shape = shape.difference(box(min(values), op['sill_z_mm'], max(values), op['sill_z_mm']+op['height_mm']))
                outline(wid, f'cut:{i}', shape, 'cut')
        for c in model['cabinets']:
            if c['host'] not in room_hosts:
                continue
            w = hosts[c['host']]; cm = cabinet_model(c['spec'])
            footprint = Polygon([world(w, c['offset_mm']+x, y) for x, y in [(0, 0), (cm['width_mm'], 0), (cm['width_mm'], cm['depth_mm']), (0, cm['depth_mm'])]])
            crossing = footprint.intersection(cut)
            if crossing.is_empty or crossing.length < 1e-6:
                continue
            if abs(w['u'][axis]) < 1-1e-6:
                raise ValueError('Cabinet section must cut across its width, perpendicular to its host; choose a separate casework section for other directions')
            along = (at-w['a'][axis])/w['u'][axis]-c['offset_mm']
            cursor = 0
            for bay, width in enumerate(cm['front_widths_mm'], 1):
                if cursor < along < cursor+width:
                    break
                cursor += width
            else:
                raise ValueError('Cabinet cut coincides with a module boundary; choose an unambiguous cut')
            raw = copy.deepcopy(c['spec']); raw['section_bay'] = bay
            raw['sheet'] = {'scale': 100, 'paper_mm': [2000, 2000]}
            from .casework import draw
            _, local = draw(raw); origin = local['views']['section']['origin']
            for row in local['geometry']:
                if row['kind'] == 'LINE' and row.get('view') == 'section':
                    def transform(p):
                        xy = world(w, c['offset_mm']+along, cm['depth_mm']-(p[0]-origin[0]))
                        return [xy[span_axis]*sign, c['base_z_mm']+p[1]-origin[1]]
                    line(c['id'], 'section:'+row['key'], transform(row['start']), transform(row['end']), row['role'])
            center = crossing.centroid.coords[0][span_axis]*sign
            dim(c['id'], 'height', [center, c['base_z_mm']], [center, c['base_z_mm']+cm['overall_height_mm']], 90)
            ends = sorted(p[span_axis]*sign for p in crossing.coords)
            dim(c['id'], 'depth', [ends[0], c['base_z_mm']], [ends[-1], c['base_z_mm']], lane=2)
    for ref in model['references']:
        if ref['source_sheet'] != sheet['id']:
            continue
        target = next(s for s in model['sheets'] if s['id'] == ref['target_sheet'])
        if target['kind'] == 'elevation':
            w = hosts[target['host']]
            depth = max([cabinet_model(c['spec'])['depth_mm'] for c in model['cabinets'] if c['host'] == target['host']] or [0])
            candidates = [w['length']*f for f in (.25, .5, .75)]
            along = next((p for p in candidates if not any(op['host'] == target['host'] and op['offset_mm']-sheet['scale']*6 <= p <= op['offset_mm']+op['width_mm']+sheet['scale']*6 for op in model['openings'])), candidates[0])
            start = world(w, along, depth+sheet['scale']*10)
            end = world(w, along, depth+sheet['scale']*2)
            value = ref['id']+' / '+target['id']
            label(ref['object_id'], 'xref:'+ref['id'], value, [start[0]-(len(value)*1.6+3)*sheet['scale'], start[1]+sheet['scale']*3])
            line(ref['object_id'], 'xref_direction:'+ref['id'], start, end, 'annotation')
            u, n = w['u'], w['n']; size = sheet['scale']*1.5
            for side in (-1, 1):
                line(ref['object_id'], 'xref_arrow:'+ref['id']+str(side), end, [end[j]+n[j]*size+u[j]*side*size for j in range(2)], 'annotation')
        else:
            ax = 0 if target['axis'] == 'x' else 1
            a, b = [xmin, ymin], [xmax, ymax]; a[ax] = b[ax] = target['at_mm']
            line(ref['object_id'], 'xref_cut:'+ref['id'], a, b, 'annotation')
            label(ref['object_id'], 'xref:'+ref['id'], ref['id']+' / '+target['id'], b)
            for index, p in enumerate((a, b)):
                end = list(p); end[ax] += target['direction']*sheet['scale']*5
                line(ref['object_id'], f'xref_direction:{ref["id"]}:{index}', p, end, 'annotation')
                for side in (-1, 1):
                    tip = list(end); tip[ax] -= target['direction']*sheet['scale']*1.5; tip[1-ax] += side*sheet['scale']*1.5
                    line(ref['object_id'], f'xref_arrow:{ref["id"]}:{index}:{side}', end, tip, 'annotation')
    # Include material descriptions and their provenance on each sheet using them.
    used = set(room['finishes'].values()) | {c['material'] for c in model['cabinets'] if c['host'] in room_hosts}
    return {'primitives': rows, 'materials': [v for v in model['materials'] if v['id'] in used]}


def draw_sheet(model, sheet, content):
    doc = ezdxf.new('R2018', setup=True); doc.units = 4
    doc.header['$MEASUREMENT'] = 1; doc.header['$LWDISPLAY'] = False
    font = configure_cjk_style(doc, 'LUOMU-PROJECT')
    style = 'LUOMU-PROJECT' if font['available'] else 'Standard'
    if not font['available'] and any('\u3400' <= c <= '\u9fff' for c in json.dumps([model, sheet], ensure_ascii=False)):
        raise ValueError('Chinese project labels require a CJK font')
    for role, weight in WEIGHTS.items():
        doc.layers.new('PR-'+role.upper(), dxfattribs={'color': 7, 'lineweight': weight, 'linetype': 'DASHED' if role == 'hidden' else 'CONTINUOUS'})
    doc.appids.new('LUOMU-PROJECT')
    space = doc.modelspace(); scale = sheet['scale']; pw, ph = sheet['paper_mm']
    pts = [r[key] for r in content['primitives'] for key in ('a', 'b') if key in r]
    xmin, ymin = min(p[0] for p in pts), min(p[1] for p in pts)
    xmax, ymax = max(p[0] for p in pts), max(p[1] for p in pts)
    # Reserve dimension lanes, title, materials and reference/revision footer.
    if (xmax-xmin)/scale > pw-90 or (ymax-ymin)/scale > ph-115:
        raise ValueError('Sheet '+sheet['id']+' does not fit paper at the requested scale')
    offset = [scale*(45+(pw-90-(xmax-xmin)/scale)/2)-xmin,
              scale*(65+(ph-115-(ymax-ymin)/scale)/2)-ymin]
    records = []
    def add(row, a=None, b=None):
        attrs = {'layer': 'PR-'+row['role'].upper()}
        if row['kind'] == 'LINE':
            e = space.add_line(a, b, dxfattribs={**attrs, 'ltscale': scale if row['role'] == 'hidden' else 1})
        elif row['kind'] == 'TEXT':
            e = space.add_text(row['text'], dxfattribs={**attrs, 'insert': a, 'height': 2.5*scale, 'style': style})
        else:
            angle = row['angle']; rad = math.radians(angle)
            lane = scale*6*row['lane']
            normal = [-math.sin(rad), math.cos(rad)]
            # Horizontal chains below their points; vertical chains left of them.
            side = row['side'] if row['side'] is not None else (-1 if abs(math.sin(rad)) < .5 else 1)
            base = [a[i]+normal[i]*lane*side for i in range(2)]
            override = {**short_extensions(scale), 'dimtxt': 2.5*scale, 'dimasz': 2*scale, 'dimgap': .8*scale, 'dimtad': 1, 'dimlfac': 1, 'dimdec': 2, 'dimzin': 8, 'dimtxsty': style, 'dimlwd': 13, 'dimlwe': 13}
            d = space.add_linear_dim(base=base, p1=a, p2=b, angle=angle, dimstyle='EZDXF', override=override, dxfattribs=attrs)
            d.render(); e = d.dimension
        e.set_xdata('LUOMU-PROJECT', [(1000, model['id']), (1000, row['owner']), (1000, sheet['id']), (1000, row['key'])])
        records.append({'handle': e.dxf.handle, **row, 'a': a, **({'b': b} if b is not None else {})})
    for row in content['primitives']:
        a = [row['a'][i]+offset[i] for i in range(2)]
        b = [row['b'][i]+offset[i] for i in range(2)] if 'b' in row else None
        add(row, a, b)
    def note(key, value, at, available=None):
        available = pw-22 if available is None else available
        if len(value) > 100 or sum(2.5 if ord(c) > 255 else 1.6 for c in value) > available:
            raise ValueError('Sheet note is too long for paper: '+value)
        add({'kind': 'TEXT', 'owner': model['id'], 'key': key, 'text': value, 'role': 'annotation'}, [v*scale for v in at])
    note('title', sheet['id']+' / '+sheet['title'], [12, ph-14])
    note('revision', model['id']+' / REV '+model['revision']+' / mm / 1:'+f'{scale:g}', [12, ph-21])
    for i, material in enumerate(content['materials']):
        if i > 3:
            raise ValueError('More than four material notes require a separate schedule layout')
        note('material:'+material['id'], material['id']+' / '+material['description'], [12, 12+i*5], pw/2-24 if model['changes'] else pw-24)
    for i, change in enumerate(model['changes']):
        if i > 2:
            raise ValueError('More than three revision notes require a separate revision schedule')
        note('change:'+str(i), change, [pw/2, 12+i*5], pw/2-12)
    for i, (a, b) in enumerate([([5, 5], [pw-5, 5]), ([pw-5, 5], [pw-5, ph-5]), ([pw-5, ph-5], [5, ph-5]), ([5, ph-5], [5, 5])]):
        add({'kind': 'LINE', 'owner': model['id'], 'key': 'border:'+str(i), 'role': 'annotation'}, [v*scale for v in a], [v*scale for v in b])
    return doc, {'content_hash': digest(content), 'offset_mm': offset, 'records': records, 'paper_mm': sheet['paper_mm'], 'scale': scale}


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def build(spec, output, previous=None, requirements=None, source=None):
    """Create a fresh complete atlas, refusing stale revisions and all overwrites."""
    model = normalize(spec)
    contents = {s['id']: project(model, s) for s in model['sheets']}
    # Preflight all sheets before creating an output directory.
    drawings = {s['id']: draw_sheet(model, s, contents[s['id']]) for s in model['sheets']}
    prior = None
    if previous:
        previous = Path(previous).resolve()
        verified = review(previous)
        if not verified['ok']:
            raise ValueError('Previous atlas failed verification')
        prior = _read(previous/'project-manifest.json')
        if prior['model']['id'] != model['id'] or prior['model']['revision'] == model['revision']:
            raise ValueError('Revision requires the same project ID and a different revision')
        if not model['changes']:
            raise ValueError('Revision requires explicit change descriptions')
    output = Path(output).resolve()
    if previous and (output == previous or output.is_relative_to(previous)):
        raise ValueError('Revision output must be separate from the previous atlas')
    with workspace_lock(output):
        if any(p.name != 'workspace.lock' for p in output.iterdir()):
            raise ValueError('Project output must be empty; use a new directory')
        from .pdf_export import render_pdf
        from pypdf import PdfReader, PdfWriter
        manifest = {'schema_version': 1, 'model': model, 'model_hash': digest(model), 'sheets': {}, 'artifacts': {},
                    'previous_model_hash': prior['model_hash'] if prior else None,
                    'previous_atlas_sha256': file_hash(previous/'atlas.pdf') if prior else None,
                    'changed_sheets': [], 'removed_sheets': sorted(set(prior['sheets'])-set(drawings)) if prior else [],
                    'scope': 'Explicit finished-face rooms, wall-hosted openings and casework; source geometry atlas, not a complete construction design'}
        merged = PdfWriter()
        # A real first-page catalogue containing the final sheet numbers and revisions.
        catalogue = ezdxf.new('R2018'); catalogue.units = 4
        cf = configure_cjk_style(catalogue, 'LUOMU-INDEX')
        cs = 'LUOMU-INDEX' if cf['available'] else 'Standard'
        catalog_space = catalogue.modelspace()
        def ct(value, x, y, height=3):
            catalog_space.add_text(value, dxfattribs={'insert': [x, y], 'height': height, 'style': cs, 'color': 7})
        ct(model['id']+' / DRAWING INDEX / REV '+model['revision'], 12, 280, 4)
        for i, sheet in enumerate(model['sheets']):
            if i >= 39:
                raise ValueError('More than 39 sheets require a multipage catalogue')
            ct(f"{i+2:02}  {sheet['id']}  {sheet['title']}  1:{sheet['scale']:g}  REV {model['revision']}", 12, 265-i*6)
            sid = sheet['id']; doc, row = drawings[sid]
            dxf = output/(sid+'.dxf'); doc.saveas(dxf)
            saved = ezdxf.readfile(dxf)
            for record in row['records']:
                if record['kind'] == 'DIMENSION':
                    record['display_hash'] = display_signature(saved, saved.entitydb[record['handle']])
            row['dxf'] = dxf.name; row['pdf'] = sid+'.pdf'; row['page'] = i+2
            manifest['sheets'][sid] = row
            if not prior or sid not in prior['sheets'] or row['content_hash'] != prior['sheets'][sid]['content_hash'] or any(sheet[k] != next(s for s in prior['model']['sheets'] if s['id'] == sid)[k] for k in ('paper_mm', 'scale', 'title')):
                manifest['changed_sheets'].append(sid)
            data, _ = render_pdf(dxf, sheet['paper_mm'], [0, 0, sheet['paper_mm'][0]*sheet['scale'], sheet['paper_mm'][1]*sheet['scale']], sheet['scale'], 0)
            (output/row['pdf']).write_bytes(data)
        catalogue.saveas(output/'drawing-index.dxf')
        data, _ = render_pdf(output/'drawing-index.dxf', [210, 297], [0, 0, 210, 297], 1, 0)
        (output/'drawing-index.pdf').write_bytes(data)
        merged.append(PdfReader(output/'drawing-index.pdf'), outline_item='DRAWING INDEX')
        for sheet in model['sheets']:
            merged.append(PdfReader(output/manifest['sheets'][sheet['id']]['pdf']), outline_item=sheet['id']+' / '+sheet['title'])
        with (output/'atlas.pdf').open('wb') as stream:
            merged.write(stream)
        merged.close()
        for path in output.iterdir():
            if path.suffix in {'.dxf', '.pdf'}:
                manifest['artifacts'][path.name] = file_hash(path)
        atomic_json(output/'project-model.json', model)
        manifest['artifacts']['project-model.json'] = file_hash(output/'project-model.json')
        atomic_json(output/'project-manifest.json', manifest)
        result = review(output, requirements, source)
        atomic_json(output/'project-review.json', result)
        return {**result, 'output': str(output), 'atlas': str(output/'atlas.pdf')}


def review(output, requirements=None, source=None):
    from pypdf.errors import PdfReadError
    try:
        return _review(output, requirements, source)
    except (OSError, ValueError, KeyError, TypeError, IndexError, ezdxf.DXFError, PdfReadError) as exc:
        return {'ok': False, 'findings': [{'kind': 'invalid_or_incomplete_bundle', 'error': str(exc)}],
                'engineering_approved': False, 'image_recognition_tested': False,
                'complete_19_type_construction_set': False}


def _review(output, requirements=None, source=None):
    """Regenerate expected projections, then read saved native entities and PDFs."""
    output = Path(output).resolve(); manifest = _read(output/'project-manifest.json')
    model = normalize(manifest['model']); findings = []; measured = {}
    def fail(kind, **data):
        findings.append({'kind': kind, **data})
    if digest(model) != manifest['model_hash'] or _read(output/'project-model.json') != model:
        fail('shared_model_mismatch')
    expected_files = {'atlas.pdf', 'drawing-index.dxf', 'drawing-index.pdf', 'project-model.json'}
    expected_files |= {s['id']+ext for s in model['sheets'] for ext in ('.dxf', '.pdf')}
    if set(manifest['artifacts']) != expected_files or set(manifest['sheets']) != {s['id'] for s in model['sheets']}:
        fail('atlas_inventory_mismatch')
    for name, sha in manifest['artifacts'].items():
        path = inside(name, output)
        if not path.is_file() or file_hash(path) != sha:
            fail('saved_artifact_changed', file=name)
    from pypdf import PdfReader
    atlas = PdfReader(output/'atlas.pdf')
    if len(atlas.pages) != len(model['sheets'])+1:
        fail('atlas_page_count_mismatch')
    index = ezdxf.readfile(output/'drawing-index.dxf')
    index_text = [e.dxf.text for e in index.modelspace() if e.dxftype() == 'TEXT']
    expected_index = [model['id']+' / DRAWING INDEX / REV '+model['revision']]
    expected_index += [f"{i+2:02}  {s['id']}  {s['title']}  1:{s['scale']:g}  REV {model['revision']}" for i, s in enumerate(model['sheets'])]
    if index_text != expected_index or len(list(index.modelspace())) != len(expected_index) or index.units != 4:
        fail('drawing_catalogue_changed')
    expected_outline = ['DRAWING INDEX']+[s['id']+' / '+s['title'] for s in model['sheets']]
    if len(atlas.outline) != len(expected_outline) or any(isinstance(v, list) or v.title != title or atlas.get_destination_page_number(v) != i for i, (v, title) in enumerate(zip(atlas.outline, expected_outline))):
        fail('atlas_bookmarks_changed')
    index_pdf = PdfReader(output/'drawing-index.pdf')
    if len(index_pdf.pages) != 1 or atlas.pages[0].get_contents().get_data() != index_pdf.pages[0].get_contents().get_data():
        fail('atlas_catalogue_page_changed')
    for sheet_num, sheet in enumerate(model['sheets'], 2):
        sid = sheet['id']; row = manifest['sheets'][sid]
        content = project(model, sheet)
        _, expected = draw_sheet(model, sheet, content)
        if row['content_hash'] != digest(content):
            fail('stale_sheet_projection', sheet=sid)
        if row['dxf'] != sid+'.dxf' or row['pdf'] != sid+'.pdf' or row['page'] != sheet_num or row['paper_mm'] != sheet['paper_mm'] or row['scale'] != sheet['scale']:
            fail('sheet_registration_changed', sheet=sid)
        expected_rows = [{k: v for k, v in r.items() if k != 'handle'} for r in expected['records']]
        manifest_rows = [{k: v for k, v in r.items() if k not in {'handle', 'display_hash'}} for r in row['records']]
        if expected_rows != manifest_rows or row['offset_mm'] != expected['offset_mm']:
            fail('sheet_manifest_not_from_shared_model', sheet=sid)
        doc = ezdxf.readfile(inside(row['dxf'], output))
        if doc.units != 4 or doc.header.get('$LTSCALE', 1) != 1:
            fail('drawing_units_or_scale_changed', sheet=sid)
        if {e.dxf.handle for e in doc.modelspace()} != {r['handle'] for r in row['records']}:
            fail('entity_inventory_changed', sheet=sid)
        for role, weight in WEIGHTS.items():
            layer = doc.layers.get('PR-'+role.upper())
            if layer.dxf.lineweight != weight or layer.dxf.color != 7 or layer.dxf.linetype.upper() != ('DASHED' if role == 'hidden' else 'CONTINUOUS'):
                fail('layer_style_changed', sheet=sid, role=role)
        for rec in row['records']:
            e = doc.entitydb.get(rec['handle'])
            if e is None or not e.is_alive or e.dxftype() != rec['kind']:
                fail('missing_entity', sheet=sid, key=rec['key']); continue
            if e.dxf.layer != 'PR-'+rec['role'].upper() or e.dxf.lineweight != -1 or e.dxf.linetype.upper() != 'BYLAYER' or e.dxf.color != 256:
                fail('entity_style_changed', sheet=sid, key=rec['key'])
            tags = [(t.code, t.value) for t in e.get_xdata('LUOMU-PROJECT')] if e.has_xdata('LUOMU-PROJECT') else []
            if tags != [(1000, model['id']), (1000, rec['owner']), (1000, sid), (1000, rec['key'])]:
                fail('entity_source_link_changed', sheet=sid, key=rec['key'])
            a = (*rec['a'], 0)
            if rec['kind'] == 'LINE':
                if math.dist(e.dxf.start, a) > 1e-6 or math.dist(e.dxf.end, (*rec['b'], 0)) > 1e-6 or e.dxf.ltscale != (sheet['scale'] if rec['role'] == 'hidden' else 1):
                    fail('projected_geometry_changed', sheet=sid, key=rec['key'])
            elif rec['kind'] == 'TEXT':
                expected_style = 'LUOMU-PROJECT' if 'LUOMU-PROJECT' in doc.styles else 'Standard'
                if e.dxf.text != rec['text'] or math.dist(e.dxf.insert, a) > 1e-6 or abs(e.dxf.height-2.5*sheet['scale']) > 1e-6 or e.dxf.style != expected_style or e.dxf.width != 1 or e.dxf.rotation != 0 or e.dxf.oblique != 0:
                    fail('text_changed', sheet=sid, key=rec['key'])
            else:
                value = float(e.get_measurement()); target = math.dist(rec['a'], rec['b'])
                key = sid+'/'+rec['owner']+'/'+rec['key']; measured[key] = value
                overrides = e.override()
                if abs(value-target) > 1e-6 or math.dist(e.dxf.defpoint2, a) > 1e-6 or math.dist(e.dxf.defpoint3, (*rec['b'], 0)) > 1e-6 or e.dxf.text not in {'', '<>'} or overrides.get('dimlfac', 1) != 1:
                    fail('native_dimension_changed', sheet=sid, key=rec['key'])
                rad = math.radians(rec['angle']); side = rec['side'] if rec['side'] is not None else (-1 if abs(math.sin(rad)) < .5 else 1)
                base = (a[0]-math.sin(rad)*sheet['scale']*6*rec['lane']*side, a[1]+math.cos(rad)*sheet['scale']*6*rec['lane']*side, 0)
                expected_overrides = {**short_extensions(sheet['scale']), 'dimtxt': 2.5*sheet['scale'], 'dimasz': 2*sheet['scale'], 'dimgap': .8*sheet['scale'], 'dimtad': 1, 'dimlfac': 1, 'dimdec': 2, 'dimzin': 8, 'dimlwd': 13, 'dimlwe': 13}
                if math.dist(e.dxf.defpoint, base) > 1e-6 or abs(e.dxf.angle-rec['angle']) > 1e-6 or any(abs(overrides.get(k, 0)-v) > 1e-6 for k, v in expected_overrides.items()):
                    fail('dimension_style_or_position_changed', sheet=sid, key=rec['key'])
                if display_signature(doc, e) != rec['display_hash']:
                    fail('dimension_display_changed', sheet=sid, key=rec['key'])
        audit = doc.audit()
        if audit.errors or audit.fixes:
            fail('dxf_audit_failed', sheet=sid)
        findings.extend(text_style_findings(doc))
        pdf = PdfReader(inside(row['pdf'], output))
        if len(pdf.pages) != 1:
            fail('sheet_pdf_page_count', sheet=sid)
        if row['page'] <= len(atlas.pages) and atlas.pages[row['page']-1].get_contents().get_data() != pdf.pages[0].get_contents().get_data():
            fail('atlas_page_does_not_match_sheet', sheet=sid)
        for page in [pdf.pages[0], *([atlas.pages[row['page']-1]] if row['page'] <= len(atlas.pages) else [])]:
            actual = [float(page.mediabox.width)*25.4/72, float(page.mediabox.height)*25.4/72]
            if any(abs(a-b) > .01 for a, b in zip(actual, sheet['paper_mm'])):
                fail('pdf_paper_changed', sheet=sid)
    # Read dimensions from every saved view, then compare shared object properties.
    cross_views = {}
    for key, value in measured.items():
        sid, owner, prop = key.split('/')
        if prop in {'width', 'depth', 'height'} and owner in {c['id'] for c in model['cabinets']} | {o['id'] for o in model['openings']}:
            cross_views.setdefault(owner+'/'+prop, []).append((sid, value))
    pairs = 0
    for key, values in cross_views.items():
        if len(values) > 1:
            pairs += len(values)-1
            if any(abs(value-values[0][1]) > 1e-6 for _, value in values[1:]):
                fail('cross_view_dimension_mismatch', object_property=key, measured=values)
    independent = None
    if requirements is not None:
        fields(requirements, 'source dimensions_mm tolerance_mm', 'independent requirements')
        src = requirements.get('source', {})
        if not isinstance(src, dict) or not re.fullmatch('[a-fA-F0-9]{64}', str(src.get('sha256', ''))) or not src.get('locator') or source is None:
            raise ValueError('Independent requirements need original source file, SHA256 and locator')
        source_ok = file_hash(source) == src['sha256']
        tolerance = number(requirements.get('tolerance_mm'), 'independent tolerance')
        expected = requirements.get('dimensions_mm')
        if not isinstance(expected, dict) or not expected:
            raise ValueError('Independent requirements need measured dimension targets')
        comparisons = []
        for key, value in expected.items():
            target = number(value, 'independent target'); actual = measured.get(key)
            passed = actual is not None and abs(actual-target) <= tolerance
            comparisons.append({'dimension': key, 'target_mm': target, 'actual_mm': actual, 'passed': passed})
            if not passed:
                fail('independent_dimension_mismatch', dimension=key, expected_mm=target, actual_mm=actual)
        if not source_ok:
            fail('independent_source_hash_mismatch')
        independent = {'source': src, 'source_hash_verified': source_ok, 'comparisons': comparisons,
                       'passed': source_ok and all(c['passed'] for c in comparisons)}
    return {'ok': not findings, 'findings': findings, 'model_hash': manifest['model_hash'],
            'dimensions_mm': measured, 'sheets_checked': len(model['sheets']), 'atlas_pages': len(atlas.pages),
            'references_checked': len(model['references']), 'changed_sheets': manifest['changed_sheets'],
            'cross_view_pairs_checked': pairs, 'independent_source_check': independent,
            'engineering_approved': False, 'image_recognition_tested': False,
            'complete_19_type_construction_set': False}
