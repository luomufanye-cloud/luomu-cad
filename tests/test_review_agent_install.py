import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

import pytest

from luomu_cad.reviewer_install import AGENT_NAME, definitions, install, verify
from luomu_cad.storage import ROOT


def test_real_project_native_files_share_instructions_and_inherit_settings(tmp_path):
    result = install(ROOT, tmp_path)
    assert result['ok'] and len(result['files_installed']) == 2
    codex = tomllib.loads((tmp_path/'.codex/agents/luomu-cad-reviewer.toml').read_text(encoding='utf8'))
    claude = (tmp_path/'.claude/agents/luomu-cad-reviewer.md').read_text(encoding='utf8')
    assert codex['name'] == AGENT_NAME
    assert codex['developer_instructions'].strip() in claude
    assert set(codex) == {'name', 'description', 'developer_instructions'}
    assert not (tmp_path/'.codex/config.toml').exists()
    assert verify(tmp_path)['ok']
    assert not result['runtime_discovery_verified']


def test_idempotency_and_own_agent_upgrade_preserve_user_settings(tmp_path):
    project=tmp_path/'project';project.mkdir()
    bundle=tmp_path/'bundle';(bundle/'agents').mkdir(parents=True)
    source=(ROOT/'agents/luomu-cad-reviewer.md').read_bytes()
    (bundle/'agents/luomu-cad-reviewer.md').write_bytes(source)
    assert install(bundle, project)['files_changed']==2
    assert install(bundle, project)['files_changed']==0
    (bundle/'agents/luomu-cad-reviewer.md').write_bytes(source+b'\nAdditional original review criterion.\n')
    assert install(bundle, project)['files_changed']==2
    assert verify(project)['ok']


def test_user_agent_conflict_does_not_partially_install_other_host(tmp_path):
    path=tmp_path/'.claude/agents/luomu-cad-reviewer.md';path.parent.mkdir(parents=True)
    original=b'---\nname: user-custom\n---\nUser role';path.write_bytes(original)
    with pytest.raises(ValueError,match='AGENT_CONFLICT'):
        install(ROOT,tmp_path)
    assert path.read_bytes()==original
    assert not (tmp_path/'.codex/agents/luomu-cad-reviewer.toml').exists()
    assert not (tmp_path/'.luomu-cad/reviewer-install.json').exists()


def test_edited_installed_agent_is_not_silently_replaced(tmp_path):
    install(ROOT,tmp_path)
    path=tmp_path/'.codex/agents/luomu-cad-reviewer.toml'
    path.write_text(path.read_text(encoding='utf8')+'\n# user change\n',encoding='utf8')
    assert not verify(tmp_path)['ok']
    with pytest.raises(ValueError,match='AGENT_CONFLICT'):
        install(ROOT,tmp_path)


def test_source_bundle_path_is_relative_when_cloned_at_project_root(tmp_path):
    (tmp_path/'agents').mkdir()
    (tmp_path/'agents/luomu-cad-reviewer.md').write_bytes((ROOT/'agents/luomu-cad-reviewer.md').read_bytes())
    data=tomllib.loads(definitions(tmp_path,tmp_path)['codex'].decode('utf8'))
    assert '资源目录：。' not in data['developer_instructions']
    assert '资源目录：.' in data['developer_instructions']


def test_cli_and_native_schema_validation(tmp_path):
    command=[sys.executable,str(ROOT/'scripts/install_review_agent.py'),'--project-root',str(tmp_path),'--host','codex']
    first=subprocess.run(command,capture_output=True,text=True,encoding='utf8')
    assert first.returncode==0,first.stderr
    assert json.loads(first.stdout)['agent_name']==AGENT_NAME
    checked=subprocess.run([*command,'--verify'],capture_output=True,text=True,encoding='utf8')
    assert checked.returncode==0,checked.stderr


def test_t3_installs_codex_provider_file_without_claiming_t3_ui_delegation(tmp_path):
    result=install(ROOT,tmp_path,'t3')
    assert len(result['files_installed'])==1 and '.codex' in result['files_installed'][0]
    assert not result['runtime_discovery_verified'] and 'not tested' in result['t3_support']


def test_missing_project_and_bundle_refused(tmp_path):
    with pytest.raises(FileNotFoundError):install(ROOT,tmp_path/'missing')
    with pytest.raises(ValueError,match='Complete Skill'):
        install(tmp_path,tmp_path)


def test_junction_or_symlink_destination_outside_project_is_refused(tmp_path):
    outside=tmp_path/'outside';outside.mkdir()
    project=tmp_path/'project';project.mkdir()
    try:(project/'.codex').symlink_to(outside,target_is_directory=True)
    except OSError:pytest.skip('Host does not allow directory symlinks')
    with pytest.raises(ValueError,match='inside'):
        install(ROOT,project,'codex')
    assert not (outside/'agents').exists()


def test_installed_role_is_discovered_by_native_codex_when_available(tmp_path):
    cli=shutil.which('codex')
    if cli is None:
        pytest.skip('Codex CLI is not installed; file/schema tests do not assert runtime discovery')
    if os.name=='nt' and Path(cli).suffix.lower() in {'.cmd','.ps1'}:
        package=Path(cli).parent/'node_modules/@openai/codex'
        executables=list(package.rglob('codex.exe')) if package.is_dir() else []
        if not executables:
            pytest.skip('Native Codex executable not available for the isolated offline probe')
        cli=str(executables[0])
    project=tmp_path/'project';project.mkdir()
    home=tmp_path/'isolated-home';home.mkdir()
    install(ROOT,project,'codex')
    # Trust is confined to this isolated test home, never the user's real config.
    trust_path=str(project).lower() if os.name=='nt' else str(project)
    (home/'config.toml').write_text('[projects.'+json.dumps(trust_path)+']\ntrust_level="trusted"\n[features]\nmulti_agent=true\n',encoding='utf8')
    result=subprocess.run([cli,'-C',str(project),'debug','prompt-input','Inspect native agent discovery only; do not call a model.'],
        env=dict(os.environ,CODEX_HOME=str(home)),stdin=subprocess.DEVNULL,capture_output=True,timeout=60)
    assert result.returncode==0,result.stderr.decode('utf8',errors='replace')
    assert AGENT_NAME.encode() in result.stdout
    assert not (project/'.codex/config.toml').exists()
