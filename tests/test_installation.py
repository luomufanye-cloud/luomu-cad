import copy
import asyncio
import importlib.util
import json
import shutil
import ezdxf
import pytest
from luomu_cad.jobs import Jobs
from luomu_cad.qa import file_hash
from luomu_cad.storage import ROOT

module_spec=importlib.util.spec_from_file_location('installation_check',ROOT/'scripts/verify_install.py')
verification=importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(verification)


@pytest.fixture
def generated(tmp_path):
    spec=json.loads((ROOT/'examples/two-room.json').read_text(encoding='utf-8'))
    result=Jobs(tmp_path/'outputs').generate('install-fixture',spec)
    return tmp_path,spec,result


def test_installation_checks_saved_geometry_preview_and_paths(generated):
    root,spec,result=generated
    checked=verification.validate_generated_result(result,root,spec)
    assert checked['dxf_readback']=='PASS' and checked['preview_file']=='PASS'
    assert checked['professional_design']=='not_reviewed'


def test_modified_artifact_cannot_reuse_a_pass_flag(generated):
    root,spec,result=generated
    with open(result['artifacts']['dxf']['path'],'ab') as f:f.write(b'\n')
    with pytest.raises(ValueError,match='hash mismatch'):verification.validate_generated_result(result,root,spec)


def test_another_installation_output_is_rejected(generated,tmp_path):
    root,spec,result=generated;result=copy.deepcopy(result)
    other=tmp_path/'borrowed.dxf';shutil.copyfile(result['artifacts']['dxf']['path'],other)
    result['artifacts']['dxf']['path']=str(other)
    with pytest.raises(ValueError,match='inside this installation'):verification.validate_generated_result(result,root,spec)


def test_wrong_dxf_units_fail_even_if_hash_and_pass_flag_are_updated(generated):
    root,spec,result=generated;p=result['artifacts']['dxf']['path']
    d=ezdxf.readfile(p);d.units=0;d.saveas(p);result['artifacts']['dxf']['sha256']=file_hash(p)
    with pytest.raises(ValueError,match='geometry failed'):verification.validate_generated_result(result,root,spec)


def test_corrupt_preview_fails_even_if_hash_is_updated(generated):
    root,spec,result=generated;p=result['artifacts']['preview']['path']
    with open(p,'wb') as f:f.write(b'\x89PNG\r\n\x1a\n')
    result['artifacts']['preview']['sha256']=file_hash(p)
    with pytest.raises(ValueError,match='valid PNG'):verification.validate_generated_result(result,root,spec)


def test_verifier_rejects_environment_pointing_at_another_skill_folder(tmp_path,monkeypatch):
    monkeypatch.setattr(verification,'ROOT',tmp_path)
    with pytest.raises(ValueError,match='another Skill folder'):
        asyncio.run(verification.verify_installation())
