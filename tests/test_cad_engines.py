"""Real optional kernel tests; no image-recognition assertion is made."""
import json
from pathlib import Path

import pytest

from luomu_cad.cad_engines import build, check_contract

ROOT = Path(__file__).resolve().parents[1]


def test_contract_detects_wrong_scale():
    result = check_contract({'bbox_mm': [8, 5, .8]}, {'bbox_mm': [[79, 81], [49, 51], [7.9, 8.1]]})
    assert len(result) == 3


@pytest.mark.parametrize('expression,volume', [
    ("cq.Workplane('XY').box(10,20,30)", 6000),
    ("cq.Workplane('XY').circle(10).circle(5).extrude(20)", 4712.38898038469),
    ("cq.Workplane('XY').rect(10,10).workplane(offset=20).circle(3).loft()", None),
])
def test_cadquery_roundtrip(tmp_path, expression, volume):
    pytest.importorskip('cadquery')
    script = tmp_path / 'input.py'
    script.write_text('import cadquery as cq\nresult = ' + expression)
    contract = {'solid_count': [1, 1]}
    if volume is not None:
        contract['volume_mm3'] = [volume - .001, volume + .001]
    report = build('cadquery', script, tmp_path / 'output', contract)
    assert report['geometry_passed']
    assert set(report['artifacts']) == {'model.step', 'model.py', 'front.svg', 'top.svg', 'right.svg'}
    assert build('cadquery', script, tmp_path / 'output', contract) == report
    (tmp_path / 'output' / 'model.step').write_text('corrupted')
    with pytest.raises(ValueError): build('cadquery', script, tmp_path / 'output', contract)


def test_ifc_actual_void_volume_and_relations(tmp_path):
    pytest.importorskip('ifcopenshell')
    report = build('ifcopenshell', ROOT / 'examples/ifc-openings.py', tmp_path / 'output')
    assert report['geometry_passed'], report
    wall = next(e for e in report['measurements']['elements'] if e['name'] == 'host_wall')
    assert wall['net_volume_m3'] == pytest.approx(5 * .2 * 3 - .9 * .2 * 2.1)
    assert len(report['measurements']['voids']) == 1
    assert len(report['measurements']['fills']) == 1


def test_invalid_model_has_no_committed_output(tmp_path):
    pytest.importorskip('cadquery')
    script = tmp_path / 'input.py'
    script.write_text('result = 3')
    with pytest.raises(ValueError): build('cadquery', script, tmp_path / 'output')
    assert not (tmp_path / 'output').exists()
