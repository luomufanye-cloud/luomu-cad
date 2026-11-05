import importlib.util
import json
import sys
import zipfile
from pathlib import Path
import pytest
from luomu_cad.storage import ROOT

sys.path.insert(0,str(ROOT/'scripts'))
from preflight import inspect_environment, MODULES
from build_workbuddy import marketplace_skill, validate_archive, market_files
from build_release import files


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


@pytest.mark.parametrize('entry',['luomu-cad/src/luomu_cad/server.py',
    'luomu-cad/references/technical/card.json','luomu-cad/references/learned/method.md'])
def test_marketplace_rejects_third_directory_level(tmp_path,entry):
    p=tmp_path/'deep.zip'
    with zipfile.ZipFile(p,'w') as z:z.writestr(entry,'data')
    with pytest.raises(ValueError,match='directory depth'):validate_archive(p)


def test_flat_market_layout_imports_and_reads_relocated_resources(tmp_path):
    import os
    import subprocess
    content=market_files(ROOT,files())
    assert all(len(Path(name).parts)<=2 for name in content)
    assert 'luomu_cad/server.py' in content and 'technical/pipe-root-interface-training.json' in content
    assert 'learned/index.md' in content
    for name,data in content.items():
        path=tmp_path/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
    env=dict(os.environ)
    env.pop('LUOMU_CAD_ROOT',None)
    env.pop('PYTHONPATH',None)
    # No root override or original project on sys.path: packaging must locate itself.
    code="import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); from luomu_cad.storage import ROOT; from luomu_cad.technical import TechnicalLibrary; assert ROOT==Path(sys.argv[1]); assert TechnicalLibrary().get('pipe-root-interface-training')['id']=='pipe-root-interface-training'"
    result=subprocess.run([sys.executable,'-I','-c',code,str(tmp_path)],env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
