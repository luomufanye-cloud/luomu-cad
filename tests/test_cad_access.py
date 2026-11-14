"""Cooperative process locks and task boundaries; no AutoCAD access."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from luomu_cad import server
from luomu_cad.cad_access import CadAccess,compare_states,ACTIONS,PASSIVE
from luomu_cad.storage import ROOT


def test_ownership_excludes_other_tasks_and_readonly_observation_stays_available(tmp_path):
    first=CadAccess(tmp_path);second=CadAccess(tmp_path)
    first.claim('first',{'edit':True},'Original edit-only task')
    assert second.status()['busy'] and not second.status()['owned_by_this_service']
    with pytest.raises(RuntimeError,match='WORKSPACE_BUSY'):
        second.claim('second',{'open':True},'Different drawing task')
    with pytest.raises(RuntimeError,match='WORKSPACE_BUSY'):
        with second.guard('activate_document'):pytest.fail('Must not switch another task drawing')
    with second.guard('list_documents'):pass
    first.release('first')
    assert not second.status()['busy']
    second.claim('second',{'open':True},'Different drawing task')
    second.release('second')


def test_permissions_are_independent_and_latest_authorization_preserves_other_fields(tmp_path):
    access=CadAccess(tmp_path)
    claimed=access.claim('design',{'edit':True},'Edit unsaved drawing, no file delivery')
    with access.guard('mutate'):pass
    for method in ['save_as','close_document','open_document']:
        with pytest.raises(ValueError,match='NOT_AUTHORIZED'):
            with access.guard(method):pass
    with pytest.raises(ValueError,match='NOT_AUTHORIZED'):
        with access.file_export():pass
    access.amend('design',{'save':True},'User now explicitly authorizes SaveAs',1)
    with access.guard('save_as'):pass
    with access.guard('mutate'):pass
    assert not access.status()['owner']['permissions']['export']
    with pytest.raises(ValueError,match='STALE'):
        access.amend('design',{'export':True},'Outdated pending amendment',1)
    assert len(access.status()['owner']['authorization_history'])==2
    claimed['owner']['permissions']['export']=True
    assert not access.status()['owner']['permissions']['export']
    access.release('design')


def test_same_request_is_idempotent_conflicting_claim_does_not_change_owner(tmp_path):
    access=CadAccess(tmp_path)
    first=access.claim('task',{'edit':True},'Original task')
    assert access.claim('task',{'edit':True},'Original task')['owner']==first['owner']
    with pytest.raises(ValueError,match='CONFLICT'):
        access.claim('task',{'save':True},'Implicitly expanded scope')
    with pytest.raises(ValueError,match='OWNER_MISMATCH'):access.release('other')
    assert access.status()['owner']==first['owner']
    access.release('task')


@pytest.mark.parametrize('permissions',[{'save':1},{'unknown':True},None])
def test_invalid_permissions_never_claim(tmp_path,permissions):
    access=CadAccess(tmp_path)
    with pytest.raises(ValueError):access.claim('task',permissions,'Original task')
    assert not access.status()['busy']


def test_process_exit_releases_os_lock_without_forced_takeover(tmp_path):
    code="""import sys,os
sys.path.insert(0,sys.argv[1])
from luomu_cad.cad_access import CadAccess
access=CadAccess(sys.argv[2]);access.claim('old-task',{'edit':True},'Old process task')
os._exit(0)
"""
    result=subprocess.run([sys.executable,'-I','-c',code,str(ROOT/'src'),str(tmp_path)],capture_output=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert json.loads((tmp_path/'owner.json').read_text())['status']=='claimed'
    access=CadAccess(tmp_path)
    assert not access.status()['busy']  # Leftover JSON is not a live lock.
    access.claim('new-task',{'edit':True},'New process task')
    access.release('new-task')


def test_another_running_process_cannot_be_claimed_over(tmp_path):
    code="""import sys
sys.path.insert(0,sys.argv[1])
from luomu_cad.cad_access import CadAccess
access=CadAccess(sys.argv[2]);access.claim('held-task',{'edit':True},'Other live process')
print('claimed',flush=True)
sys.stdin.readline()
access.release('held-task')
"""
    process=subprocess.Popen([sys.executable,'-I','-c',code,str(ROOT/'src'),str(tmp_path)],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert process.stdout.readline().strip()=='claimed'
        access=CadAccess(tmp_path)
        assert access.status()['busy']
        with pytest.raises(RuntimeError,match='WORKSPACE_BUSY'):
            access.claim('new-task',{'open':True},'New task must wait')
        process.communicate('\n',timeout=10)
        assert process.returncode==0
        access.claim('new-task',{'open':True},'Prior process has released')
        access.release('new-task')
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=10)


def test_exceptions_release_implicit_per_call_lock(tmp_path):
    access=CadAccess(tmp_path)
    with pytest.raises(RuntimeError,match='Fake failure'):
        with access.guard('mutate'):raise RuntimeError('Fake failure')
    other=CadAccess(tmp_path)
    other.claim('next',{},'Read only')
    other.release('next')


@pytest.mark.asyncio
async def test_main_mcp_guard_rejects_before_cad_is_called(tmp_path,monkeypatch):
    owner=CadAccess(tmp_path);owner.claim('first',{'edit':True},'Other task')
    monkeypatch.setattr(server,'cad_access',CadAccess(tmp_path))
    class Fake:
        def mutate(self):raise AssertionError('CAD must not be called')
        def list_documents(self):return {'ok':True,'documents':[]}
    monkeypatch.setattr(server,'cad',Fake())
    result=await server._cad('mutate')
    assert not result['ok'] and 'WORKSPACE_BUSY' in result['error']
    assert (await server._cad('list_documents'))['ok']
    owner.release('first')


@pytest.mark.asyncio
async def test_mcp_scope_changes_need_a_new_user_source_and_current_revision(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'cad_access',CadAccess(tmp_path))
    await server.workbench_cad_access('claim','task',{'edit':True},'Edit-only task')
    with pytest.raises(ValueError,match='Latest user'):
        await server.workbench_cad_access('amend','task',{'save':True},expected_revision=1)
    state=await server.workbench_cad_access('amend','task',{'save':True},'New explicit save instruction',1)
    assert state['owner']['permissions']['save'] and state['owner']['permissions']['edit']
    await server.workbench_cad_access('release','task')


@pytest.mark.asyncio
async def test_no_export_task_blocks_offline_pdf_before_exporter_runs(tmp_path,monkeypatch):
    access=CadAccess(tmp_path);access.claim('task',{'edit':True},'No saved or exported drawing')
    monkeypatch.setattr(server,'cad_access',access)
    def forbidden(*args):raise AssertionError('Exporter must not be called')
    monkeypatch.setattr(server.jobs,'export_pdf',forbidden)
    with pytest.raises(ValueError,match='NOT_AUTHORIZED'):
        await server.workbench_export_pdf('job','source',[420,297],[0,0,1,1],1)
    access.release('task')


def test_all_current_cad_gateway_methods_have_a_deliberate_access_classification():
    tree=ast.parse((ROOT/'src/luomu_cad/server.py').read_text(encoding='utf8'))
    methods={n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call)
        and isinstance(n.func,ast.Name) and n.func.id=='_cad' and n.args
        and isinstance(n.args[0],ast.Constant)}
    assert methods<=set(ACTIONS)|PASSIVE


@pytest.mark.parametrize('changed',[{'entity_count':2161},{'snapshot_sha256':'b'*64},
    {'document_id':'different-document'},{'saved':True,'dbmod':0}])
def test_actual_recent_stale_review_patterns_require_new_evidence(changed):
    recorded={'document_id':'same-live-document','entity_count':2166,
              'snapshot_sha256':'a'*64,'saved':False,'dbmod':21}
    result=compare_states(recorded,{**recorded,**changed})
    assert result['status']=='stale' and result['needs_new_snapshot_and_review']
    assert not result['accepted_for_delivery'] and not result['live_cad_verified']


def test_matching_counters_without_raw_snapshot_fingerprint_are_insufficient():
    state={'document_id':'drawing','entity_count':1473,'saved':False,'dbmod':21}
    result=compare_states(state,state)
    assert result['status']=='insufficient_evidence' and result['needs_new_snapshot_and_review']


def test_matching_strong_recorded_state_is_still_not_a_live_or_delivery_verdict():
    state={'document_id':'drawing','entity_count':1473,'snapshot_sha256':'a'*64}
    result=server.workbench_compare_states(state,state)
    assert result['status']=='matching_recorded_state'
    assert not result['live_cad_verified'] and result['live_recheck_required']
    assert not result['accepted_for_delivery']
