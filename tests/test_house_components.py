import copy
import math
from pathlib import Path

import ezdxf
import pytest

from luomu_cad.components import catalogue, build, validate, review_single_door


@pytest.fixture(scope='module')
def library():
    return catalogue()


def plan(kind='door', angle=0, side=1, hinge=False):
    return {'units': 'mm',
            'nodes': [{'id': 'a', 'x': 100, 'y': 200},
                      {'id': 'b', 'x': 100 + 6000 * math.cos(angle),
                       'y': 200 + 6000 * math.sin(angle)}],
            'walls': [{'id': 'wall', 'a': 'a', 'b': 'b', 't': 200, 'exterior_side': 1}],
            'openings': [{'id': 'door', 'wall': 'wall', 'pos': 3000, 'width': 900,
                          'type': kind, 'side': side, 'hinge': hinge}], 'furniture': []}


@pytest.mark.parametrize('kind', ['door', 'double', 'unequal', 'sliding', 'folding', 'pocket',
                                  'hole', 'window', 'slideWindow', 'floorWindow', 'highWindow',
                                  'bay', 'garage', 'glassWall'])
def test_all_openings_native_readback(tmp_path, kind):
    result = build(plan(kind, angle=.6), tmp_path)
    assert result['geometry_passed']
    assert max(result['opening_checks'][0]['jamb_gaps']) < 1e-7
    assert result['opening_checks'][0]['wall_overlap_area'] < 1e-7


@pytest.mark.parametrize('angle', [0, math.pi / 2, .73])
@pytest.mark.parametrize('side', [-1, 1])
@pytest.mark.parametrize('hinge', [False, True])
def test_door_hinge_arc_and_leaf_meet_real_jamb(tmp_path, angle, side, hinge):
    result = build(plan(angle=angle, side=side, hinge=hinge), tmp_path)
    drawing = ezdxf.readfile(result['dxf'])
    arcs = list(drawing.modelspace().query('ARC[layer=="A-DOOR"]'))
    assert len(arcs) == 1
    arc = arcs[0]
    assert arc.dxf.radius == pytest.approx(900)
    wall_vertices = [point[:2] for entity in drawing.modelspace().query('LWPOLYLINE[layer=="A-WALL"]')
                     for point in entity.get_points()]
    assert min(math.dist(tuple(arc.dxf.center)[:2], point) for point in wall_vertices) < 1e-7
    lines = list(drawing.modelspace().query('LINE[layer=="A-DOOR"]'))
    # The thick open leaf has a centreline 900 long and two edges 20 away.
    axis = (math.cos(angle), math.sin(angle))
    leaf_edges = [line for line in lines if abs((line.dxf.end - line.dxf.start).magnitude - 900) < 1e-6]
    assert len(leaf_edges) >= 2
    for line in leaf_edges:
        vector = line.dxf.end - line.dxf.start
        assert abs(vector.x * axis[0] + vector.y * axis[1]) < 1e-6
    endpoints = [arc.start_point, arc.end_point]
    assert min(abs((point - arc.dxf.center).dot((axis[0], axis[1], 0))) for point in endpoints) < 1e-6


def test_catalogue_and_curves(tmp_path, library):
    assert len(library['furniture']) == 317
    assert sum(row['native_geometry'] for row in library['furniture']) == 306
    spec = plan()
    spec['furniture'] = [{'id': key, 'key': key, 'x': index * 2000, 'y': 3000, 'rot': 27}
                         for index, key in enumerate(['sofa', 'bed18', 'toilet', 'ovalTable'])]
    result = build(spec, tmp_path)
    drawing = ezdxf.readfile(result['dxf'])
    assert len(drawing.modelspace().query('SPLINE')) > 0
    assert len(drawing.modelspace().query('ELLIPSE')) > 0
    for entity in drawing.modelspace().query('LWPOLYLINE'):
        assert entity.dxf.const_width == 0
    assert drawing.layers.get('A-DOOR').dxf.lineweight == 13


@pytest.mark.parametrize('change', ['host', 'overlap', 'end', 'side', 'hinge', 'units'])
def test_invalid_relationships_rejected(library, change):
    spec = plan()
    if change == 'host':
        spec['openings'][0]['wall'] = 'missing'
    elif change == 'overlap':
        spec['openings'].append({**spec['openings'][0], 'id': 'second'})
    elif change == 'end':
        spec['openings'][0]['pos'] = 100
    elif change == 'units':
        del spec['units']
    else:
        del spec['openings'][0][change]
    with pytest.raises(ValueError):
        validate(spec, library)


def test_source_coordinate_mode(tmp_path):
    spec = plan()
    spec.update(units='source', library_scale=.05, scale_basis='Uncalibrated symbol width ratio')
    for node in spec['nodes']:
        node['x'] *= .05
        node['y'] *= .05
    spec['walls'][0]['t'] *= .05
    spec['openings'][0]['pos'] *= .05
    spec['openings'][0]['width'] *= .05
    result = build(spec, tmp_path)
    drawing = ezdxf.readfile(result['dxf'])
    assert drawing.units == 0
    assert next(iter(drawing.modelspace().query('ARC'))).dxf.radius == pytest.approx(45)


def test_corner_and_intersecting_wall(tmp_path):
    spec = plan()
    spec['nodes'].append({'id': 'c', 'x': 6100, 'y': 3200})
    spec['walls'].append({'id': 'return', 'a': 'b', 'b': 'c', 't': 200})
    assert build(spec, tmp_path / 'corner')['geometry_passed']
    blocked = copy.deepcopy(spec)
    blocked['nodes'] += [{'id': 'd', 'x': 3100, 'y': -800}, {'id': 'e', 'x': 3100, 'y': 1200}]
    blocked['walls'].append({'id': 'crossing', 'a': 'd', 'b': 'e', 't': 200})
    with pytest.raises(ValueError, match='crosses opening'):
        build(blocked, tmp_path / 'blocked')


@pytest.mark.parametrize('defect', ['hinge_gap', 'wrong_radius', 'closed_leaf'])
def test_actual_saved_door_regressions_rejected(tmp_path, defect):
    result = build(plan(), tmp_path)
    drawing = ezdxf.readfile(result['dxf'])
    handles = result['source_to_entities'][0]['handles']
    arc = next(iter(drawing.modelspace().query('ARC')))
    if defect == 'hinge_gap':
        arc.dxf.center += (5, 0, 0)
    elif defect == 'wrong_radius':
        arc.dxf.radius -= 1
    else:
        for line in drawing.modelspace().query('LINE[layer=="A-DOOR"]'):
            if abs((line.dxf.end - line.dxf.start).magnitude - 900) < 1e-6:
                line.dxf.end = line.dxf.start + (900, 0, 0)
    with pytest.raises(ValueError):
        review_single_door(drawing, handles, [[2650, 300], [3550, 300]], 900, 40)


def test_all_supported_catalogue_entries_export(tmp_path, library):
    spec = {'units': 'mm', 'nodes': [], 'walls': [], 'openings': [],
            'furniture': [{'id': item['key'], 'key': item['key'], 'x': index * 6000, 'y': 0}
                          for index, item in enumerate(library['furniture']) if item['native_geometry']]}
    result = build(spec, tmp_path)
    assert len(result['source_to_entities']) == 306
    assert result['entity_count'] > 5000
