import importlib.util
import json
import sys
import zipfile
from pathlib import Path
import pytest
from luomu_cad.storage import ROOT

sys.path.insert(0,str(ROOT/'scripts'))
from preflight import inspect_environment, MODULES
from build_workbuddy import marketplace_skill, validate_archive


def test_reference_mode_without_dependencies_and_linux_live_boundary():
    result=inspect_environment(ROOT,system='Linux',python_version=(3,10),modules={})
    assert result['reference_ready'] and not result['offline_runtime_ready']
    assert not result['live_platform_supported'] and not result['cad_connection_verified']
    assert not result['network_accessed'] and not result['configuration_changed']


def test_offline_runtime_readiness_is_not_live_cad_connection():
    result=inspect_environment(ROOT,system='Windows',python_version=(3,11),modules={n:True for n in MODULES})
    assert result['offline_runtime_ready'] and result['live_platform_supported']
    assert not result['cad_connection_verified']


def test_incomplete_skill_folder_rejected(tmp_path):
    result=inspect_environment(tmp_path,modules={n:True for n in MODULES})
    assert not result['package_complete'] and 'scripts/entry.py' in result['missing_files']


def test_marketplace_metadata_keeps_same_body_and_explicit_requirements():
    text,meta=marketplace_skill(ROOT)
    assert text.split('---',2)[2]==(ROOT/'SKILL.md').read_text(encoding='utf-8').split('---',2)[2]
    assert meta['author']=='luomufanye-cloud' and len(meta['examples_zh'])>=2
    assert 'Windows' in meta['description_en'] and 'sandbox' in meta['description_en']


@pytest.mark.parametrize('bad',['../escape','/absolute','other/SKILL.md','luomu-cad/../escape'])
def test_unsafe_upload_archives_rejected(tmp_path,bad):
    p=tmp_path/'bad.zip'
    with zipfile.ZipFile(p,'w') as z:z.writestr(bad,'x')
    with pytest.raises(ValueError):validate_archive(p)


def test_truncated_marketplace_runtime_rejected(tmp_path):
    p=tmp_path/'missing.zip'
    text,_=marketplace_skill(ROOT)
    with zipfile.ZipFile(p,'w') as z:z.writestr('luomu-cad/SKILL.md',text)
    with pytest.raises(ValueError,match='Incomplete runtime'):validate_archive(p)


@pytest.mark.parametrize('field,value',[('author',True),('name','different-skill'),('version','0.0.0')])
def test_malformed_marketplace_metadata_rejected(tmp_path,field,value):
    _,meta=marketplace_skill(ROOT)
    meta[field]=value
    header='---\n'+'\n'.join(k+': '+json.dumps(v,ensure_ascii=False) for k,v in meta.items())+'\n---\nBody'
    p=tmp_path/'metadata.zip'
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('luomu-cad/SKILL.md',header)
        z.writestr('luomu-cad/pyproject.toml',(ROOT/'pyproject.toml').read_bytes())
    with pytest.raises(ValueError):validate_archive(p)
