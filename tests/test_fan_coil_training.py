import importlib.util
import math
import ezdxf
import pytest
from luomu_cad.storage import ROOT

spec=importlib.util.spec_from_file_location('fan_coil_training',ROOT/'scripts/train_fan_coil.py')
training=importlib.util.module_from_spec(spec)
spec.loader.exec_module(training)


def test_source_datum_and_changed_model_are_not_scaled_or_assumed_at_corners(tmp_path):
    good=training.draw(tmp_path/'normal.dxf',render=False)
    assert good['ok'] and good['support_points_mm']['T']==[420,830]
    assert good['drain']['vertices'][0][1]==300
    assert good['drain']['vertices'][1][1]==800
    assert math.isclose(good['drain']['slope'],.02)
    assert 830 in good['native_dimension_measurements']
    assert not training.draw(tmp_path/'corner.dxf','corner_supports',render=False)['ok']
    assert not training.draw(tmp_path/'half.dxf','centred_supports',render=False)['ok']
    changed=training.draw(tmp_path/'small.dxf',model='FWH02AFN',render=False)
    assert changed['ok'] and changed['support_points_mm']['TR']==[240,614]


@pytest.mark.parametrize('variant,issue',[('excess_lift','drain lift'),('flat_drain','downstream slope'),('tilted_unit','unit must be level'),('ceiling_collision','collides')])
def test_installation_wrong_cases_are_detected_from_saved_geometry(tmp_path,variant,issue):
    result=training.draw(tmp_path/(variant+'.dxf'),variant,render=False)
    assert not result['ok'] and any(issue in i for i in result['issues'])


@pytest.mark.parametrize('edit',['x','z'])
def test_readback_detects_external_edits_even_if_dimensions_and_labels_remain(tmp_path,edit):
    path=tmp_path/'edited.dxf';training.draw(path,render=False)
    doc=ezdxf.readfile(path);e=next(e for e in doc.modelspace().query('POINT') if e.dxf.layer=='SUPPORT')
    e.dxf.location=(e.dxf.location.x+(5 if edit=='x' else 0),e.dxf.location.y,20 if edit=='z' else 0);doc.saveas(path)
    result=training.readback(path,'FWH06AFN')
    assert not result['ok'] and any('support' in i for i in result['issues'])


def test_heat_balance_unit_conversion_kv_and_head_have_independent_hand_answers():
    r=training.hydraulic_case(5.8,5,1000,4.18,20,4,20)
    assert r['mass_kg_s']==pytest.approx(0.2775119617)
    assert r['flow_m3_h']==pytest.approx(0.9990430622)
    assert r['velocity_m_s']==pytest.approx(0.8833480095)
    assert r['valve_loss_kpa']==pytest.approx(6.238044,rel=1e-5)
    assert r['required_head_m_for_given_losses']==pytest.approx(2.674622,rel=1e-5)
    smaller_delta=training.hydraulic_case(5.8,3,1000,4.18,20,4,20*(5/3)**2)
    assert smaller_delta['flow_m3_h']/r['flow_m3_h']==pytest.approx(5/3)
    assert smaller_delta['required_head_m_for_given_losses']/r['required_head_m_for_given_losses']==pytest.approx(25/9)
    bypass=training.hydraulic_case(5.8,5,1000,4.18,20,1.6,20)
    assert bypass['valve_loss_kpa']/r['valve_loss_kpa']==pytest.approx(6.25)
    assert not r['engineering_approval']


@pytest.mark.parametrize('dt',[0,-1,float('nan'),True])
def test_invalid_temperature_difference_cannot_produce_a_training_result(dt):
    with pytest.raises(ValueError):training.hydraulic_case(5.8,dt,1000,4.18,20,4,20)
