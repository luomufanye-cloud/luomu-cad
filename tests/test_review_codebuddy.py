"""Transport fixtures verify evidence binding, not live model capability."""
import copy
import json
from pathlib import Path

import pytest

from luomu_cad import review_codebuddy, review_runner, server, review_jobs
from luomu_cad.review_evidence_server import Evidence, encoded
from luomu_cad.reviewer_install import install, verify, install_codebuddy_home, verify_codebuddy_home
from luomu_cad.storage import ROOT
from test_review_runner import task, response
from test_review_jobs import hold_launch


def stream(tmp_path):
    packet, drawing, home=task(tmp_path)
    out=tmp_path/'out';out.mkdir()
    previews=review_runner._previews({'native':drawing},out)
    _,lock=review_runner._evidence_lock(packet,previews,out,'evidence-test')
    evidence=Evidence(packet,out/'evidence-lock.json',out)
    rows=[{'type':'system','subtype':'init','session_id':'actual-session'}]
    rows+=copy.deepcopy(rows)  # MCP discovery emits a second snapshot.
    def tool(name,args,value,image=None):
        cid='id-'+str(len(rows))
        rows.append({'type':'assistant','message':{'content':[{'type':'tool_use','id':cid,
            'name':'mcp__evidence_test__'+name,'input':args}]}})
        blocks=[{'type':'text','text':encoded(value)}]
        if image:
            blocks.append({'type':'image','image':'data:'+image.mimeType+';base64,'+image.data})
        rows.append({'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':cid,
            'content':[{'type':'text','text':json.dumps(blocks)}],'is_error':False}]}})
    for fid,record in evidence.records.items():
        tool('review_read',{'file_id':fid},evidence.read(fid))
        for index in range(len(record['previews'])):
            value,image=evidence.view(fid,index)
            tool('review_view',{'file_id':fid,'preview_index':index},value,image)
    evidence.close()
    rows.append({'type':'assistant','message':{'content':[{'type':'text','text':json.dumps(response())}]}})
    rows.append({'type':'result','subtype':'success','session_id':'actual-session',
                 'is_error':False,'permission_denials':[],'structured_output':response()})
    return rows,lock,out


def test_native_pairs_images_and_real_read_ledger_are_required(tmp_path):
    rows,lock,out=stream(tmp_path)
    normalized=review_codebuddy.normalize(rows,lock,out/'final.json')
    checked=review_runner._mcp_evidence(normalized,lock,out)
    assert len(checked)==3
    assert [r['thread_id'] for r in normalized if r['type']=='thread.started']==['actual-session']
    # Event content without its actual evidence-server access ledger is rejected.
    (out/'evidence-access.jsonl').rename(out/'original-ledger.jsonl')
    with pytest.raises(ValueError,match='REAL_READ_RECORD'):
        review_runner._mcp_evidence(normalized,lock,out)


@pytest.mark.parametrize('fault',['command','orphan','wrong_session','refusal','unfinished','reused','missing_image','nested'])
def test_invalid_codebuddy_transcripts_cannot_become_ready(tmp_path,fault):
    rows,lock,out=stream(tmp_path)
    if fault=='command':rows[2]['message']['content'][0]['name']='PowerShell'
    elif fault=='orphan':rows[3]['message']['content'][0]['tool_use_id']='absent'
    elif fault=='wrong_session':rows[-1]['session_id']='other'
    elif fault=='refusal':rows[-1]['permission_denials']=[{'tool_name':'review_read'}]
    elif fault=='unfinished':rows.pop(3)
    elif fault=='reused':rows.insert(4,copy.deepcopy(rows[2]))
    elif fault=='nested':rows[2]['parent_tool_use_id']='nested'
    elif fault=='missing_image':
        block=rows[-3]['message']['content'][0]['content'][0]
        block['text']=json.dumps(json.loads(block['text'])[:1])
    with pytest.raises(ValueError):
        normalized=review_codebuddy.normalize(rows,lock,out/'final.json')
        review_runner._mcp_evidence(normalized,lock,out)


def test_codebuddy_role_is_owned_idempotent_and_inherits_model(tmp_path):
    result=install(ROOT,tmp_path,'codebuddy')
    role=tmp_path/'.codebuddy/agents/luomu-cad-reviewer.md'
    assert result['files_changed']==1 and verify(tmp_path,'codebuddy')['ok']
    assert 'model: inherit\n' in role.read_text(encoding='utf8')
    assert install(ROOT,tmp_path,'codebuddy')['files_changed']==0
    assert not (tmp_path/'.codebuddy/settings.json').exists()


def test_codebuddy_home_is_cross_project_and_keeps_user_configuration(tmp_path):
    home=tmp_path/'profile';home.mkdir()
    settings=home/'settings.json';settings.write_text('{"model":"existing-model"}')
    before=settings.read_bytes()
    result=install_codebuddy_home(ROOT,home)
    assert result['scope']=='codebuddy_home' and result['files_changed']==1
    assert (home/'agents/luomu-cad-reviewer.md').is_file()
    assert not (home/'.codebuddy').exists()
    assert settings.read_bytes()==before and verify_codebuddy_home(home)['ok']
    assert install_codebuddy_home(ROOT,home)['files_changed']==0
    role=home/'agents/luomu-cad-reviewer.md';role.write_bytes(role.read_bytes()+b'\nUser edit\n')
    assert not verify_codebuddy_home(home)['ok']
    with pytest.raises(ValueError,match='AGENT_CONFLICT'):install_codebuddy_home(ROOT,home)


@pytest.mark.asyncio
async def test_mcp_codebuddy_does_not_require_codex_and_preserves_model(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'ROOT',tmp_path)
    calls=[]
    def start(*args,**kwargs):calls.append((args,kwargs));return {'status':'queued'}
    monkeypatch.setattr(review_jobs,'start',start)
    args=dict(operation='start',operation_id='hy4',packet_path='packet',output='out',
              host='codebuddy',codebuddy_home=str(tmp_path),model='hy4free')
    with pytest.raises(ValueError,match='OPT_IN'):await server.workbench_review_agent(**args)
    assert not calls
    value=await server.workbench_review_agent(**args,use_personal_codebuddy_home=True)
    assert calls[0][0][3] is None
    assert calls[0][1]=={'base':tmp_path,'host':'codebuddy','codebuddy_home':str(tmp_path),'model':'hy4free'}
    assert value['accepted_for_delivery'] is False


def test_launch_uses_only_packet_mcp_and_no_permission_bypass(tmp_path,monkeypatch):
    monkeypatch.setattr(review_codebuddy,'command',lambda:['installed-codebuddy'])
    schema=tmp_path/'schema.json';schema.write_text('{}')
    args,env=review_codebuddy.launch(tmp_path,'hy4free',tmp_path,'role','task',schema,
        'evidence-test',Path('server.py'),Path('packet'),Path('lock'),'python')
    assert '--strict-mcp-config' in args and args[args.index('--tools')+1]==''
    assert args[args.index('--model')+1]=='hy4free'
    assert not any(s in args for s in ['-y','--dangerously-skip-permissions','--fallback-model'])
    assert env['CODEBUDDY_CONFIG_DIR']==str(tmp_path)
    config=json.loads((tmp_path/'codebuddy-mcp.json').read_text())
    assert list(config['mcpServers'])==['evidence-test']


@pytest.mark.asyncio
@pytest.mark.parametrize('model',['hy3','deepseek-v4.1-flash','glm-5.3-flash','kimi-k3.1-pro','custom-model'])
async def test_model_ids_are_forwarded_without_a_family_allowlist(tmp_path,monkeypatch,model):
    monkeypatch.setattr(server,'ROOT',tmp_path)
    calls=[]
    def start(*args,**kwargs):calls.append(kwargs);return {'status':'queued'}
    monkeypatch.setattr(review_jobs,'start',start)
    await server.workbench_review_agent('start',operation_id='model',packet_path='packet',output='out',
        host='codebuddy',codebuddy_home=str(tmp_path),model=model,use_personal_codebuddy_home=True)
    assert calls[0]['model']==model


@pytest.mark.asyncio
async def test_codex_can_use_main_runtime_model_without_changing_profile(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'ROOT',tmp_path)
    calls=[]
    def start(*args,**kwargs):calls.append(kwargs);return {'status':'queued'}
    monkeypatch.setattr(review_jobs,'start',start)
    await server.workbench_review_agent('start',operation_id='model',packet_path='packet',output='out',
        codex_home=str(tmp_path),model='runtime-selected-model',use_personal_codex_home=True)
    assert calls==[{'base':tmp_path,'model':'runtime-selected-model'}]


def test_job_id_binds_model_and_does_not_relaunch_after_a_model_switch(tmp_path,monkeypatch):
    packet,_,home=task(tmp_path)
    calls=hold_launch(monkeypatch)
    args=dict(host='codebuddy',codebuddy_home=home,model='glm-5.3-flash',base=tmp_path)
    first=review_jobs.start('same-job',packet,tmp_path/'out',**args)
    again=review_jobs.start('same-job',packet,tmp_path/'out',**args)
    assert first['request_hash']==again['request_hash'] and len(calls)==1
    args['model']='deepseek-v4.1-flash'
    with pytest.raises(ValueError,match='JOB_CONFLICT'):
        review_jobs.start('same-job',packet,tmp_path/'out',**args)
    assert len(calls)==1


def test_transport_verifies_actual_host_model_and_model_output(tmp_path):
    rows,lock,out=stream(tmp_path)
    for row in rows:
        if row.get('type')=='system':row['model']='actual-model'
    with pytest.raises(ValueError,match='MODEL_MISMATCH'):
        review_codebuddy.normalize(rows,lock,out/'wrong-model.json',expected_model='other-model')
    rows[-1]['structured_output']=dict(response(),inventory_observation='Not the model message')
    with pytest.raises(ValueError,match='NOT_BOUND_TO_MODEL'):
        review_codebuddy.normalize(rows,lock,out/'unbound.json',expected_model='actual-model')
