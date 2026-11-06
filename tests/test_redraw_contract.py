import importlib.util
import hashlib
from pathlib import Path

import ezdxf
import pytest

spec = importlib.util.spec_from_file_location('verify_redraw', Path(__file__).parents[1]/'scripts/verify_redraw.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def fixture(tmp_path):
    doc = ezdxf.new('R2018', setup=True)
    doc.units = 4
    m = doc.modelspace()
    m.add_line((0, 0), (3000, 0))
    dim = m.add_linear_dim(base=(0, 500), p1=(0, 0), p2=(3000, 0),
                           override={'dimlfac': 1})
    dim.render()
    m.add_text('Plan')
    path = tmp_path/'drawing.dxf'
    contract = {'units': 4, 'source': 'Original synthetic reference: 3000 mm segment',
                'dimensions': [{'handle': dim.dimension.dxf.handle, 'start': [0, 0, 0],
                                'end': [3000, 0, 0], 'measurement': 3000,
                                'tolerance': 0.01, 'dimlfac': 1}], 'texts': ['Plan']}
    return doc, path, contract, dim.dimension


def test_native_pass_does_not_claim_visual_or_engineering(tmp_path):
    doc, path, contract, _ = fixture(tmp_path)
    doc.saveas(path)
    result = gate.audit(path, contract)
    assert result['checks_passed']
    assert not result['complete_redraw_accepted']


@pytest.mark.parametrize('failure', ['exploded', 'override', 'endpoints', 'scale', 'text', 'units', 'display'])
def test_rejects_independent_faults(tmp_path, failure):
    doc, path, contract, dim = fixture(tmp_path)
    if failure == 'exploded':
        doc.modelspace().delete_entity(dim)
        doc.modelspace().add_text('3000')
    if failure == 'override': dim.dxf.text = '3000'
    if failure == 'endpoints': dim.dxf.defpoint2 = (1, 0, 0)
    if failure == 'scale':
        override = dim.override(); override['dimlfac'] = 2; override.commit()
    if failure == 'text': contract['texts'].append('Title that was cropped away')
    if failure == 'units': doc.units = 0
    if failure == 'display': dim.dxf.geometry = 'missing'
    doc.saveas(path)
    assert not gate.audit(path, contract)['checks_passed']


def test_scope_preserves_geometry_and_shared_styles(tmp_path):
    doc, path, contract, dim = fixture(tmp_path)
    doc.saveas(path)
    baseline = gate.fingerprints(ezdxf.readfile(path))
    baseline.pop(dim.dxf.handle)
    contract['preserve'] = baseline
    dim.dxf.text = '<>'
    doc.saveas(path)
    assert gate.audit(path, contract)['checks_passed']
    doc.layers.get('0').dxf.lineweight = 50
    doc.saveas(path)
    assert any(e.startswith('OUTSIDE_SCOPE_CHANGED:layers:0') for e in gate.audit(path, contract)['errors'])


def test_malformed_inventory_cannot_silently_pass(tmp_path):
    doc, path, contract, _ = fixture(tmp_path)
    doc.saveas(path)
    contract['dimensions'][0]['tolerance'] = float('nan')
    with pytest.raises(ValueError): gate.audit(path, contract)


def test_empty_inventories_require_explanation(tmp_path):
    doc, path, contract, _ = fixture(tmp_path)
    doc.saveas(path)
    contract['dimensions'] = []
    with pytest.raises(ValueError, match='absence reason'): gate.audit(path, contract)
    contract['dimensions_absent_reason'] = 'This scoped fixture checks title only'
    assert gate.audit(path, contract)['checks_passed']


def test_unexpected_geometry_and_missing_inventory(tmp_path):
    doc, path, contract, _ = fixture(tmp_path)
    contract['expected_handles'] = [e.dxf.handle for e in doc.modelspace()]
    doc.modelspace().add_circle((100, 200), 25)
    doc.saveas(path)
    assert any(e.startswith('UNEXPECTED_ENTITY') for e in gate.audit(path, contract)['errors'])
    contract['expected_handles'].append('DEADBEEF')
    assert 'EXPECTED_ENTITY_MISSING:DEADBEEF' in gate.audit(path, contract)['errors']


def test_empty_dimension_block_and_style_drift(tmp_path):
    doc, path, contract, dim = fixture(tmp_path)
    contract['dimensions'][0]['style'] = {'dimdec': dim.override().get('dimdec')}
    doc.saveas(path)
    assert gate.audit(path, contract)['checks_passed']
    contract['dimensions'][0]['style']['dimdec'] += 1
    assert any(e.startswith('DIMENSION_STYLE') for e in gate.audit(path, contract)['errors'])
    block = doc.blocks[dim.dxf.geometry]
    for entity in list(block): block.delete_entity(entity)
    doc.saveas(path)
    assert any(e.startswith('DIMENSION_DISPLAY_EMPTY') for e in gate.audit(path, contract)['errors'])


@pytest.mark.parametrize('field,value,code', [('insert',(50,0,0),'POSITION'),('height',50,'HEIGHT'),('rotation',90,'ROTATION'),('text','Other','CONTENT')])
def test_text_geometry_not_only_string(tmp_path, field, value, code):
    doc, path, contract, _ = fixture(tmp_path)
    text = doc.modelspace().query('TEXT')[0]
    contract['text_entities'] = [{'handle':text.dxf.handle,'text':'Plan','at':list(text.dxf.insert),
        'height':text.dxf.height,'rotation':0,'tolerance':0.01}]
    doc.saveas(path)
    assert gate.audit(path, contract)['checks_passed']
    setattr(text.dxf, field, value)
    doc.saveas(path)
    assert any(e.startswith('TEXT_'+code) for e in gate.audit(path, contract)['errors'])


def test_patch_allows_only_explicit_edits_and_new_objects(tmp_path):
    doc, path, _, _ = fixture(tmp_path)
    doc.saveas(path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    text = doc.modelspace().query('TEXT')[0]
    text.dxf.text = 'Plan B'
    revised = tmp_path/'revised.dxf'
    doc.saveas(revised)
    assert gate.compare_patch(path, revised, sha, [text.dxf.handle])['checks_passed']
    extra = doc.modelspace().add_line((0, 50), (3000, 50))
    doc.saveas(revised)
    assert not gate.compare_patch(path, revised, sha, [text.dxf.handle])['checks_passed']
    assert gate.compare_patch(path, revised, sha, [text.dxf.handle], [extra.dxf.handle])['checks_passed']
    with pytest.raises(ValueError, match='HASH_MISMATCH'):
        gate.compare_patch(path, revised, '0'*64)


def test_anonymous_display_and_shared_line_pattern_are_protected(tmp_path):
    doc, path, _, dim = fixture(tmp_path)
    doc.saveas(path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    revised = tmp_path/'revised.dxf'
    doc.blocks[dim.dxf.geometry].add_line((0,0),(3000,3000))
    doc.saveas(revised)
    result = gate.compare_patch(path, revised, sha)
    assert f'OUTSIDE_SCOPE_CHANGED:block:{dim.dxf.geometry}' in result['errors']


def test_second_edit_cannot_undo_first_accepted_edit(tmp_path):
    doc, path, _, _ = fixture(tmp_path)
    texts = doc.modelspace().query('TEXT')
    first = texts[0]
    second = doc.modelspace().add_text('Second')
    first.dxf.text = 'Accepted first change'
    doc.saveas(path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    second.dxf.insert = (100,0,0)
    revised = tmp_path/'second.dxf'
    doc.saveas(revised)
    assert gate.compare_patch(path, revised, sha, [second.dxf.handle])['checks_passed']
    first.dxf.text = 'Plan'
    doc.saveas(revised)
    assert f'OUTSIDE_SCOPE_CHANGED:{first.dxf.handle}' in gate.compare_patch(path, revised, sha, [second.dxf.handle])['errors']


def test_stale_dimension_picture_is_not_correct_measurement(tmp_path):
    doc, path, contract, dim = fixture(tmp_path)
    contract['dimensions'][0]['display_text'] = '3000'
    doc.saveas(path)
    assert gate.audit(path, contract)['checks_passed']
    # Geometric definition and expected value change, but the display has not regenerated.
    dim.dxf.defpoint3 = (3500,0,0)
    contract['dimensions'][0].update(end=[3500,0,0], measurement=3500, display_text='3500')
    doc.saveas(path)
    assert f'DIMENSION_DISPLAY_TEXT:{dim.dxf.handle}' in gate.audit(path, contract)['errors']


def test_patch_cannot_compare_output_to_itself(tmp_path):
    doc, path, _, _ = fixture(tmp_path)
    doc.saveas(path)
    with pytest.raises(ValueError, match='BASELINE_IS_OUTPUT'):
        gate.compare_patch(path, path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_nonfinite_saved_text_rotation_is_rejected(tmp_path):
    doc, path, contract, _ = fixture(tmp_path)
    text = doc.modelspace().query('TEXT')[0]
    contract['text_entities'] = [{'handle':text.dxf.handle,'text':'Plan','at':list(text.dxf.insert),
        'height':text.dxf.height,'rotation':0,'tolerance':0.01}]
    text.dxf.rotation = float('nan')
    doc.saveas(path)
    assert not gate.audit(path, contract)['checks_passed']
