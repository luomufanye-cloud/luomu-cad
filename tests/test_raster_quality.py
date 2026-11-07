"""Original small source exercise and independent semantic failure mutations."""
import copy
import hashlib
from pathlib import Path
import sys

import ezdxf
import pytest
from PIL import Image, ImageDraw

from luomu_cad.reference_build import build
from luomu_cad.redraw_quality import coordinate_basis
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from redraw_delivery import audit_reference


def source_exercise(tmp_path):
    # Source coordinates are the independently authored exercise, not DXF readback.
    image = Image.new('RGB', (140, 140), 'white')
    draw = ImageDraw.Draw(image)
    draw.line((20, 120, 20, 20), fill='black', width=2)
    draw.arc((-80, 20, 120, 220), 270, 360, fill='black', width=2)
    path = tmp_path / 'source.png'
    image.save(path)
    paint = {'linetype': 'CONTINUOUS', 'rgb': [0, 0, 0], 'lineweight': 0, 'opacity': 1}
    objects = [
        {'id': 'leaf', 'kind': 'LINE', 'expected': {'start': [20, 20, 0], 'end': [20, 120, 0]}},
        {'id': 'arc', 'kind': 'ARC', 'expected': {'center': [20, 20, 0], 'radius': 100,
                                              'start_angle': 0, 'end_angle': 90}},
    ]
    for item in objects:
        item.update(presentation=copy.deepcopy(paint), tolerance=.01, source_locator='original quarter door exercise')
    inventory = {'schema_version': 1, 'source_format': 'image',
                 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                 'page': 0, 'view': 'original source coordinate exercise', 'units': 0,
                 'scale': {'status': 'unscaled', 'basis': 'Original image coordinates with inverted Y; no real length supplied'},
                 'delivery_target': 'offline_dxf', 'review_regions': ['full_view', 'door'], 'objects': objects,
                 'raster_quality': {'components': [
                     {'id': 'door', 'object_ids': ['leaf', 'arc'], 'depiction': 'linework',
                      'source_locator': 'original quarter door exercise', 'budget_basis': 'One native leaf and one native opening arc',
                      'max_entities': 2, 'max_vertices': 3, 'source_bounds': [20, 20, 120, 120], 'tolerance': .01}],
                     'doors': [{'id': 'door', 'source_locator': 'original quarter door exercise',
                                'arc_id': 'arc', 'leaf_ids': ['leaf'], 'hinge': [20, 20, 0],
                                'closed_tip': [120, 20, 0], 'open_tip': [20, 120, 0],
                                'sweep_degrees': 90, 'tolerance': .01}]}}
    return path, inventory


def test_unscaled_raster_build_and_saved_readback(tmp_path):
    source, inventory = source_exercise(tmp_path)
    doc, mapping = build(inventory)
    drawing = tmp_path / 'drawing.dxf'
    doc.saveas(drawing)
    result = audit_reference(drawing, inventory, mapping, source)
    assert result['checks_passed'], result
    assert ezdxf.readfile(drawing).units == 0
    assert result['coordinate_basis'] == {'status': 'unscaled', 'dimension_accuracy_accepted': False}


@pytest.mark.parametrize('fault,expected', [
    ('fill', 'RASTER_REPRESENTATION:door'),
    ('complexity', 'RASTER_COMPLEXITY:door'),
    ('bounds', 'RASTER_SOURCE_BOUNDS:door'),
    ('hinge', 'DOOR_HINGE_SWEEP:door'),
    ('leaf', 'DOOR_LEAF_HINGE:door'),
    ('sweep', 'DOOR_HINGE_SWEEP:door'),
    ('missing_components', 'RASTER_COMPONENT_INVENTORY_REQUIRED'),
    ('coverage', 'RASTER_COMPONENT_COVERAGE'),
])
def test_self_consistent_geometry_cannot_bypass_source_component_checks(tmp_path, fault, expected):
    source, inventory = source_exercise(tmp_path)
    quality = inventory['raster_quality']
    if fault == 'fill':
        inventory['objects'][0].update(kind='HATCH', expected={
            'solid': True, 'hatch_style': 0,
            'loops': [{'points': [[20, 20, 0], [21, 20, 0], [20, 120, 0]], 'closed': True, 'external': True}]})
        quality['doors'] = []
    elif fault == 'complexity':
        inventory['objects'][0].update(kind='LWPOLYLINE', expected={
            'points': [[20, 20+i, 0] for i in range(101)], 'closed': False})
    elif fault == 'bounds':
        inventory['objects'][0]['expected']['start'] = [0, 0, 0]
    elif fault == 'hinge':
        inventory['objects'][1]['expected']['center'] = [21, 20, 0]
    elif fault == 'leaf':
        inventory['objects'][0]['expected']['start'] = [20, 30, 0]
    elif fault == 'sweep':
        inventory['objects'][1]['expected']['start_angle'] = 90
        inventory['objects'][1]['expected']['end_angle'] = 360
    elif fault == 'missing_components':
        inventory.pop('raster_quality')
        inventory.pop('source_format')  # File suffix must still trigger the raster gate.
    elif fault == 'coverage':
        quality['components'][0]['object_ids'] = ['arc']
    doc, mapping = build(inventory)
    drawing = tmp_path / 'mutated.dxf'
    doc.saveas(drawing)
    result = audit_reference(drawing, inventory, mapping, source)
    assert expected in result['errors'], result


@pytest.mark.parametrize('change', [
    {'scale': {}}, {'scale': {'status': 'calibrated', 'basis': 'not a real dimension'}},
    {'units': True}, {'units': 1}, {'units': 4},
])
def test_unsupported_or_contradictory_scale_rejected(tmp_path, change):
    _, inventory = source_exercise(tmp_path)
    inventory.update(change)
    with pytest.raises(ValueError):
        build(inventory)


def test_unscaled_native_measurement_is_rejected(tmp_path):
    _, inventory = source_exercise(tmp_path)
    inventory['objects'][0]['kind'] = 'DIMENSION'
    with pytest.raises(ValueError, match='measured dimensions'):
        coordinate_basis(inventory)


def test_valid_mm_legacy_inventory_still_supported():
    assert coordinate_basis({'units': 4})['status'] == 'millimetres'


def test_overlapping_component_budget_rejected(tmp_path):
    source, inventory = source_exercise(tmp_path)
    duplicate = copy.deepcopy(inventory['raster_quality']['components'][0])
    duplicate['id'] = 'duplicate'
    inventory['raster_quality']['components'].append(duplicate)
    doc, mapping = build(inventory)
    drawing = tmp_path / 'overlap.dxf'
    doc.saveas(drawing)
    with pytest.raises(ValueError, match='overlapping'):
        audit_reference(drawing, inventory, mapping, source)
