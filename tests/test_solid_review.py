"""Prevent command-success and tolerance-based reports being treated as acceptance."""
import pytest
from luomu_cad.solid_review import evaluate_review, decode_response


def test_uniform_png_is_not_a_valid_model_preview(tmp_path):
    from PIL import Image, ImageDraw
    from luomu_cad.solid_render import image_has_content
    path=tmp_path/'view.png'
    image=Image.new('RGB',(80,60),'gray');image.save(path)
    assert not image_has_content(path)
    ImageDraw.Draw(image).rectangle((10,20,70,30),fill='white');image.save(path)
    assert image_has_content(path)


def reports():
    return {'measure': {'status':'success','metrics':{'is_valid':True,'volume':1000,
            'dimensions':{'x':20,'y':10,'z':5}}}, 'inspect':{'status':'success'},
            'check_spec':{'status':'success','passed':True}, 'render':{'status':'success'}}


def test_feature_failure_overrides_successful_execution():
    data=reports(); data['check_spec']['passed']=False
    result=evaluate_review(data,{},dict.fromkeys(('front','right','top','iso')))
    assert not result['checks_passed']
    assert 'FEATURE_REQUIREMENTS_NOT_PASSED' in result['failures']


def test_missing_dimension_or_view_cannot_pass():
    data=reports(); del data['measure']['metrics']['dimensions']['z']
    result=evaluate_review(data,{'bbox_mm':[[20,20],[10,10],[5,5]]},{'iso':{}})
    assert not result['checks_passed']
    assert 'FOUR_VIEWS_MISSING' in result['failures']
    assert 'bbox_mm[2]_OUT_OF_RANGE' in result['failures']


def test_numerical_acceptance_does_not_imply_visual_or_engineering_acceptance():
    result=evaluate_review(reports(),{'volume_mm3':[999,1001]},dict.fromkeys(('front','right','top','iso')))
    assert result['checks_passed']
    assert not result['visual_review_passed'] and not result['source_fidelity_verified']
    assert not result['engineering_approval']


@pytest.mark.parametrize('bounds',[[False,1],[float('nan'),1],[2,1],['1',2]])
def test_invalid_tolerances_are_rejected(bounds):
    with pytest.raises(ValueError):evaluate_review(reports(),{'volume_mm3':bounds},{})


def test_unavailable_comparison_is_not_reported_as_preserved_geometry():
    data=reports();data['diff']={'status':'success','comparison_3d':{'status':'timeout'}}
    result=evaluate_review(data,{},dict.fromkeys(('front','right','top','iso')),True)
    assert not result['checks_passed']


def test_same_volume_with_wrong_position_fails_directional_change_contract():
    data=reports();data['diff']={'status':'success','comparison_3d':{
        'status':'success','method':'source_frame_boolean_volume',
        'alignment':{'mode':'source_frame','transform_applied':False},
        'volumes':{'reference_only':500,'candidate_only':500}}}
    result=evaluate_review(data,{'removed_volume_mm3':[0,.001],'added_volume_mm3':[0,.001]},
                           dict.fromkeys(('front','right','top','iso')),True)
    assert not result['checks_passed']
    assert len(result['failures'])==2


def test_approximate_comparison_cannot_satisfy_exact_change_contract():
    data=reports();data['diff']={'status':'success','comparison_3d':{
        'status':'success','method':'voxel_approximation','volumes':{'reference_only':0}}}
    result=evaluate_review(data,{'removed_volume_mm3':[0,.001]},dict.fromkeys(('front','right','top','iso')),True)
    assert 'EXACT_COMPARISON_UNAVAILABLE' in result['failures']


def test_nonzero_exit_cannot_look_successful_and_stderr_is_not_json():
    data=decode_response(b'{"status":"success","passed":true}', b'progress\n', 1)
    assert data['status']=='error'


def test_native_graphics_diagnostic_is_preserved_without_corrupting_json():
    result=decode_response(b'OpenGL driver warning\n{"status":"success"}\n',b'',0)
    assert result['status']=='success'
    assert 'OpenGL' in result['native_stdout_diagnostics']
    assert decode_response(b'{"status":"success"}\n{"status":"error"}',b'',0)['status']=='error'
