import importlib.util
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
