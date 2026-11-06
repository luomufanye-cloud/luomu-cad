import copy
import importlib.util
import json
from pathlib import Path

import ezdxf
import pytest

ROOT = Path(__file__).resolve().parents[1]
module_spec = importlib.util.spec_from_file_location('pipe_node_training', ROOT / 'scripts/train_pipe_node.py')
training = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(training)


@pytest.fixture
def given():
    return json.loads((ROOT / 'examples/pipe-node-training.json').read_text(encoding='utf-8'))


def test_saved_sections_detect_missing_and_buried_connections(tmp_path, given):
    normal = training.draw(tmp_path / 'normal.dxf', given)
    assert training.inspect(normal, given)['ok']
    for defect in ('missing_upper_connection', 'buried_connection'):
        path = training.draw(tmp_path / (defect + '.dxf'), given, defect)
        r = training.inspect(path, given)
        assert not r['ok'] and 'MEMBRANE_CONNECTION' in r['issues']


@pytest.mark.parametrize('changes,code,measured', [
    ({'pipe_offset_mm': 3}, 'ANNULUS_BELOW_ASSIGNED_MINIMUM', ('annuli_mm', [9, 3])),
    ({'tile_mm': 18}, 'PROJECTION_BELOW_ASSIGNED_MINIMUM', ('projection_mm', 18.7968)),
    ({'band_offset_mm': 12}, 'LAP_BELOW_ASSIGNED_MINIMUM', ('laps_mm', [46.5, 70.5])),
])
def test_condition_changes_are_measured_from_saved_dxf(tmp_path, given, changes, code, measured):
    given['geometry'].update(changes)
    path = training.draw(tmp_path / 'changed.dxf', given)
    r = training.inspect(path, given)
    assert code in r['issues'] and not r['ok']
    assert r['measurements'][measured[0]] == pytest.approx(measured[1])


@pytest.mark.parametrize('changes,key,wanted', [
    ({'pipe_offset_mm': 3, 'opening_mm': 46}, 'annuli_mm', [10, 4]),
    ({'tile_mm': 18, 'pipe_end_x_mm': 65}, 'projection_mm', 28.7968),
    ({'band_offset_mm': 12, 'band_width_mm': 150}, 'laps_mm', [59, 83]),
])
def test_revised_inputs_resolve_measured_failure(tmp_path, given, changes, key, wanted):
    given['geometry'].update(changes)
    result = training.inspect(training.draw(tmp_path / 'corrected.dxf', given), given)
    assert result['ok'], result
    assert result['measurements'][key] == pytest.approx(wanted)
    assert result['engineering_approval'] is False


def test_saved_entities_and_dimension_scale_cannot_be_forged(tmp_path, given):
    path = training.draw(tmp_path / 'tampered.dxf', given)
    doc = ezdxf.readfile(path)
    dim = next(iter(doc.modelspace().query('DIMENSION')))
    style = dim.override()
    style.update({'dimlfac': 100})
    style.commit()
    # Independent edit after generation: turn the pipe plan into a different OD.
    doc.modelspace().query('CIRCLE[layer=="PLAN_PIPE"]')[0].dxf.radius += 2
    doc.saveas(path)
    result = training.inspect(path, given)
    assert not result['ok']
    assert 'PLAN_SECTION_MISMATCH' in result['issues']
    assert 'DIMENSION_SCALE' in result['issues']


def test_saved_finish_move_is_rejected_without_changing_input(tmp_path, given):
    path = training.draw(tmp_path / 'tampered.dxf', given)
    doc = ezdxf.readfile(path)
    for e in doc.modelspace().query('LINE[layer=="FINISH"]'):
        e.translate(9, 0, 0)
    doc.saveas(path)
    result = training.inspect(path, given)
    assert 'ASSIGNED_GEOMETRY_CHANGED' in result['issues']
    assert 'PROJECTION_BELOW_ASSIGNED_MINIMUM' in result['issues']


@pytest.mark.parametrize('value', [float('nan'), float('inf'), 0, -2, True])
def test_invalid_geometry_fails_before_drawing(given, value):
    given['geometry']['pipe_od_mm'] = value
    with pytest.raises(ValueError): training.calculate(given)


def test_missing_provenance_and_unknown_geometry_rejected(given):
    changed = copy.deepcopy(given)
    changed['geometry']['nominal_dn'] = 20
    with pytest.raises(ValueError): training.validate(changed)
    given['parameter_provenance'] = {}
    with pytest.raises(ValueError): training.validate(given)


@pytest.mark.parametrize('layer,code', [
    ('MEMBRANE', 'SECTION_ENDPOINTS_MEMBRANE'),
    ('BACKING', 'SECTION_ENDPOINTS_BACKING'),
    ('OPENING_EDGE', 'OPENING_ENDPOINTS'),
])
def test_translated_sections_are_not_connected_by_matching_x_only(tmp_path, given, layer, code):
    path = training.draw(tmp_path / 'disconnected.dxf', given)
    doc = ezdxf.readfile(path)
    for entity in doc.modelspace().query(f'LINE[layer=="{layer}"]'):
        entity.translate(0, 100, 0)
    doc.saveas(path)
    result = training.inspect(path, given)
    assert not result['ok'] and code in result['issues']


@pytest.mark.parametrize('mutation', ['translate', 'bowtie', 'skew', 'bulge'])
def test_band_requires_real_rectangular_two_dimensional_coverage(tmp_path, given, mutation):
    path = training.draw(tmp_path / 'bad-band.dxf', given)
    doc = ezdxf.readfile(path)
    band = doc.modelspace().query('LWPOLYLINE[layer=="BAND"]')[0]
    points = list(band.get_points('xyseb'))
    if mutation == 'translate':
        band.translate(0, 200, 0)
    elif mutation == 'bowtie':
        band.set_points([points[0], points[2], points[1], points[3]], format='xyseb')
    elif mutation == 'skew':
        points[0] = (points[0][0], -10, *points[0][2:])
        band.set_points(points, format='xyseb')
    else:
        points[0] = (*points[0][:4], 0.5)
        band.set_points(points, format='xyseb')
    doc.saveas(path)
    result = training.inspect(path, given)
    assert not result['ok'] and 'BAND_SHAPE_AND_POSITION' in result['issues']
    if mutation == 'translate': assert 'BAND_DOES_NOT_COVER_SEAM' in result['issues']


@pytest.mark.parametrize('mutation,code', [
    ('translate', 'DIMENSION_FEATURE_BINDING'),
    ('angle', 'DIMENSION_FEATURE_BINDING'),
    ('role', 'DIMENSION_ROLE'),
    ('display_text', 'DIMENSION_DISPLAY_TEXT'),
    ('display_position', 'DIMENSION_DISPLAY_POSITION'),
])
def test_dimensions_bind_features_and_actual_anonymous_display(tmp_path, given, mutation, code):
    path = training.draw(tmp_path / 'bad-dimension.dxf', given)
    doc = ezdxf.readfile(path)
    dim = doc.modelspace().query('DIMENSION')[0]
    if mutation == 'translate':
        dim.translate(0, 200, 0)  # Measurement stays 32, but endpoints leave the pipe.
    elif mutation == 'angle':
        dim.dxf.angle = 270
    elif mutation == 'role':
        dim.set_xdata('LUOMU_PIPE_DIM', [(1000, 'projection')])
    else:
        text = doc.blocks[dim.dxf.geometry].query('MTEXT')[0]
        if mutation == 'display_text': text.text = '9999'
        else: text.translate(0, 100, 0)
    doc.saveas(path)
    result = training.inspect(path, given)
    assert not result['ok'] and code in result['issues']
