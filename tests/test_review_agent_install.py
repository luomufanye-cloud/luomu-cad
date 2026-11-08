import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

import pytest

from luomu_cad.reviewer_install import AGENT_NAME, definitions, install, verify, install_codex_home, verify_codex_home
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


def test_personal_scope_is_explicit_and_keeps_other_settings_unchanged(tmp_path):
    home=tmp_path/'home';home.mkdir()
    settings=b'model="preserved-model"\nmodel_provider="preserved-provider"\n'
    (home/'config.toml').write_bytes(settings)
    result=install_codex_home(ROOT,home)
    assert result['scope']=='codex_home'
    role=home/'agents/luomu-cad-reviewer.toml'
    assert role.is_file() and not (home/'.codex/agents').exists()
    assert (home/'config.toml').read_bytes()==settings
    prompt=tomllib.loads(role.read_text(encoding='utf8'))['developer_instructions']
    assert ROOT.resolve().as_posix() in prompt and '这是绝对路径' in prompt
    assert install_codex_home(ROOT,home)['files_changed']==0
    assert verify_codex_home(home)['ok']


def test_personal_owned_upgrade_and_user_edit_protection(tmp_path):
    home=tmp_path/'home';home.mkdir()
    bundle=tmp_path/'bundle';(bundle/'agents').mkdir(parents=True)
    prompt=b'Original role definition';(bundle/'agents/luomu-cad-reviewer.md').write_bytes(prompt)
    assert install_codex_home(bundle,home)['files_changed']==1
    (bundle/'agents/luomu-cad-reviewer.md').write_bytes(prompt+b' updated')
    assert install_codex_home(bundle,home)['files_changed']==1
    role=home/'agents/luomu-cad-reviewer.toml';role.write_bytes(role.read_bytes()+b'\n# user change\n')
    assert not verify_codex_home(home)['ok']
    with pytest.raises(ValueError,match='AGENT_CONFLICT'):install_codex_home(bundle,home)


def test_personal_unowned_collision_does_not_overwrite(tmp_path):
    path=tmp_path/'agents/luomu-cad-reviewer.toml';path.parent.mkdir()
    path.write_bytes(b'name="user-owned"\n')
    with pytest.raises(ValueError,match='AGENT_CONFLICT'):install_codex_home(ROOT,tmp_path)
    assert path.read_bytes()==b'name="user-owned"\n'
    assert not (tmp_path/'.luomu-cad/reviewer-personal-install.json').exists()


def test_personal_cli_install_verify_and_exclusive_scope_arguments(tmp_path):
    command=[sys.executable,str(ROOT/'scripts/install_review_agent.py'),'--codex-home',str(tmp_path)]
    result=subprocess.run(command,capture_output=True,text=True,encoding='utf8')
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['scope']=='codex_home'
    result=subprocess.run([*command,'--verify'],capture_output=True,text=True,encoding='utf8')
    assert result.returncode==0,result.stderr
    result=subprocess.run([*command,'--project-root',str(tmp_path)],capture_output=True,text=True,encoding='utf8')
    assert result.returncode!=0


def test_personal_scope_rejects_symlink_escape(tmp_path):
    outside=tmp_path/'outside';outside.mkdir()
    home=tmp_path/'home';home.mkdir()
    try:(home/'agents').symlink_to(outside,target_is_directory=True)
    except OSError:pytest.skip('Host does not allow directory symlinks')
    with pytest.raises(ValueError,match='inside'):install_codex_home(ROOT,home)
    assert not (outside/'luomu-cad-reviewer.toml').exists()


def test_personal_native_discovery_from_two_projects_when_codex_available(tmp_path):
    cli=shutil.which('codex')
    if cli is None:pytest.skip('Codex CLI is not installed')
    if os.name=='nt' and Path(cli).suffix.lower() in {'.cmd','.ps1'}:
        package=Path(cli).parent/'node_modules/@openai/codex'
        executables=list(package.rglob('codex.exe')) if package.is_dir() else []
        if not executables:pytest.skip('Native Codex executable unavailable')
        cli=str(executables[0])
    home=tmp_path/'isolated-personal-home';home.mkdir()
    first=tmp_path/'first-project';first.mkdir()
    second=tmp_path/'other-project';second.mkdir()
    install_codex_home(ROOT,home)
    trust=''
    for project in [first,second]:
        name=str(project).lower() if os.name=='nt' else str(project)
        trust+='[projects.'+json.dumps(name)+']\ntrust_level="trusted"\n'
    settings=(trust+'[features]\nmulti_agent=true\n').encode('utf8')
    (home/'config.toml').write_bytes(settings)
    for project in [first,second]:
        result=subprocess.run([cli,'-C',str(project),'debug','prompt-input','Inspect personal agent discovery only; do not call a model.'],
            env=dict(os.environ,CODEX_HOME=str(home)),stdin=subprocess.DEVNULL,capture_output=True,timeout=60)
        assert result.returncode==0,result.stderr.decode('utf8',errors='replace')
        assert AGENT_NAME.encode() in result.stdout
        assert not (project/'.codex').exists()
    assert (home/'config.toml').read_bytes()==settings
