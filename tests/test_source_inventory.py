import copy
import hashlib

import ezdxf
import pytest

from luomu_cad.source_inventory import inventory, check_dimension_chains


def test_nested_mirror_nonzero_base_units_layer_and_immutability(tmp_path):
    doc = ezdxf.new('R2018'); doc.units = 6
    leaf = doc.blocks.new('leaf', base_point=(1, 2))
    leaf.add_line((1, 2), (3, 2))
    assembly = doc.blocks.new('assembly')
    assembly.add_blockref('leaf', (4, 5), dxfattribs={'xscale':-1, 'rotation':90})
    outer = doc.modelspace().add_blockref('assembly', (10, 20), dxfattribs={'layer':'FURN'})
    path = tmp_path/'nested.dxf'; doc.saveas(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = inventory(path)
    assert result['ok'] and result['source_sha256'] == before
    row = result['entities'][0]
    assert row['id'].startswith(outer.dxf.handle+'/')
    assert row['layer'] == 'FURN' and row['semantic_class'] == 'unclassified'
    assert row['bounds_mm'] == pytest.approx([14000, 23000, 14000, 25000])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_crop_keeps_crossing_lines_and_offscreen_insertion(tmp_path):
    doc = ezdxf.new(); doc.units = 4
    doc.modelspace().add_line((-100, 5), (100, 5))
    block = doc.blocks.new('offscreen_base'); block.add_line((100, 2), (110, 2))
    doc.modelspace().add_blockref('offscreen_base', (-100, 0))
    doc.modelspace().add_line((20, 20), (30, 30))
    path = tmp_path/'crop.dxf'; doc.saveas(path)
    result = inventory(path, [0, 0, 10, 10])
    assert result['ok'] and result['selected_count'] == 2
    assert result['blocks'][0]['selected']
    assert len(result['entities']) == 3  # Outside content remains accounted for.


def test_array_close_instances_and_attributes_are_not_deduplicated(tmp_path):
    doc = ezdxf.new(); doc.units = 4
    block = doc.blocks.new('symbol'); block.add_line((0, 0), (1, 0))
    ref = doc.modelspace().add_blockref('symbol', (0, 0))
    ref.add_attrib('ID', '原始文字', (0, 1))
    ref.add_attrib('CODE', 'A-01', (0, 2))
    ref.grid((1, 2), (0, 20))
    path = tmp_path/'array.dxf'; doc.saveas(path)
    result = inventory(path)
    assert result['ok'] and len(result['blocks']) == 2
    assert len({r['id'] for r in result['entities']}) == 6
    lines = [r for r in result['entities'] if r['type'] == 'LINE']
    assert sorted(r['bounds_mm'][0] for r in lines) == [0, 20]
    assert [r['text'] for r in result['entities'] if r['type'] == 'ATTRIB'] == ['原始文字','A-01']*2


def test_nonuniform_arc_is_reported_as_ellipse(tmp_path):
    doc = ezdxf.new(); doc.units = 4
    block = doc.blocks.new('curve'); block.add_circle((0, 0), 10)
    doc.modelspace().add_blockref('curve', (0, 0), dxfattribs={'xscale':2})
    path = tmp_path/'curve.dxf'; doc.saveas(path)
    result = inventory(path)
    assert result['ok']
    assert result['entities'][0]['transformed_types'] == ['ELLIPSE']
    assert result['entities'][0]['bounds_mm'] == pytest.approx([-20, -10, 20, 10])


def test_cycles_unknown_and_empty_do_not_pass(tmp_path):
    doc = ezdxf.new(); doc.units = 4
    block = doc.blocks.new('cycle'); block.add_blockref('cycle', (0, 0))
    doc.modelspace().add_blockref('cycle', (0, 0))
    doc.modelspace().add_ray((0, 0), (1, 0))
    path = tmp_path/'cycle.dxf'; doc.saveas(path)
    result = inventory(path)
    assert not result['ok'] and any('Cyclic' in i['message'] for i in result['issues'])
    assert any('RAY' in i['message'] for i in result['issues'])
    with pytest.raises(ValueError, match='budget'):
        inventory(path, max_entities=1)


def test_unknown_units_need_evidence(tmp_path):
    doc = ezdxf.new(); doc.units = 0
    doc.modelspace().add_line((0, 0), (3, 0))
    path = tmp_path/'unitless.dxf'; doc.saveas(path)
    with pytest.raises(ValueError, match='Unitless'):
        inventory(path)
    with pytest.raises(ValueError, match='evidence'):
        inventory(path, unit_mm=1000)
    result = inventory(path, unit_mm=1000, unit_reason='Synthetic 3-unit line represents 3000 mm')
    assert result['ok'] and result['entities'][0]['bounds_mm'][2] == 3000
    with pytest.raises(ValueError, match='finite'):
        inventory(path, unit_mm=float('nan'), unit_reason='invalid')


def chains():
    features = [{'id':name, 'kind':'axis', 'axis':'x', 'coordinate_mm':at}
                for name, at in [('A', 0), ('B', 3000), ('C', 7000)]]
    values = [{'id':'segments', 'kind':'axis', 'axis':'x', 'features':['A','B','C'],
               'segments_mm':[3000,4000], 'tolerance_mm':0.01},
              {'id':'total', 'kind':'axis', 'axis':'x', 'features':['A','C'],
               'segments_mm':[7000], 'tolerance_mm':0.01}]
    return features, values


def test_dimension_reference_semantics_and_total_conflict():
    features, values = chains()
    assert check_dimension_chains(features, values)['ok']
    wrong = copy.deepcopy(features); wrong[1]['kind'] = 'face'
    result = check_dimension_chains(wrong, values)
    assert any(f['error'] == 'semantic_reference_mismatch' for f in result['findings'])
    values[1]['segments_mm'] = [7100]
    result = check_dimension_chains(features, values)
    assert any(f['error'] == 'source_dimension_conflict' for f in result['findings'])
    assert features[1]['coordinate_mm'] == 3000


def test_shifted_axis_and_decreasing_chain():
    features, values = chains()
    features[1]['coordinate_mm'] += 120
    result = check_dimension_chains(features, values)
    assert [m['actual_mm'] for m in result['measurements']] == [3120,3880,7000]
    assert not result['ok']
    features, values = chains()
    values[0]['features'].reverse(); values[0]['segments_mm'].reverse()
    assert check_dimension_chains(features, values)['ok']


@pytest.mark.parametrize('problem', ['empty', 'duplicate', 'missing', 'nan', 'wrong_axis', 'nonmonotonic'])
def test_bad_chain_contracts(problem):
    features, values = chains()
    if problem == 'empty': features = []
    if problem == 'duplicate': features.append(features[0])
    if problem == 'missing': values[0]['features'][1] = 'absent'
    if problem == 'nan': values[0]['tolerance_mm'] = float('nan')
    if problem == 'wrong_axis': features[1]['axis'] = 'y'
    if problem == 'nonmonotonic': features[1]['coordinate_mm'] = 8000
    if problem in {'empty', 'duplicate', 'nan'}:
        with pytest.raises(ValueError): check_dimension_chains(features, values)
    else:
        assert not check_dimension_chains(features, values)['ok']
