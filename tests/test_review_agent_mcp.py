"""Main-MCP routing/schema tests; no model API and no AutoCAD interaction."""
import json
from pathlib import Path

import pytest

from luomu_cad import review_jobs, server
from test_review_jobs import contract_fixture, save


@pytest.fixture
def scoped(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'ROOT',tmp_path)
    monkeypatch.delenv('CODEX_HOME',raising=False)
    async def no_cad(*args,**kwargs):raise AssertionError('No CAD calls are allowed from this review tool')
    monkeypatch.setattr(server,'_cad',no_cad)
    return tmp_path


@pytest.mark.asyncio
async def test_prepare_real_factory_uses_root_record_base_and_keeps_original_task(scoped):
    path,contract,_=contract_fixture(scoped)
    nested=scoped/'nested';nested.mkdir();new=nested/'contract.json';save(new,contract)
    brief=(scoped/'customer.json').read_bytes();task=(scoped/'task.txt').read_bytes()
    result=await server.workbench_review_agent('prepare',contract_path='nested/contract.json',packet_path='packet.json')
    assert result['packet']['sha256']==review_jobs._hash(scoped/'packet.json')
    assert not result['accepted_for_delivery'] and result['delivery_review_required']
    assert result['review_agent_tool']=='workbench_review_agent' and result['delivery_review_tool']=='workbench_delivery'
    packet=review_jobs._load(scoped/'packet.json')
    assert packet['raw_sources'][0]['path']=='task.txt'
    assert (scoped/'customer.json').read_bytes()==brief and (scoped/'task.txt').read_bytes()==task
    assert set(packet['artifacts'][0])=={'id','path','sha256','sheet_id'}


@pytest.mark.asyncio
async def test_start_explicit_account_opt_in_routes_to_background_api(scoped,monkeypatch):
    home=scoped/'explicit-home';home.mkdir()
    calls=[]
    def fake(*args,**kwargs):
        calls.append((args,kwargs));return {'status':'queued','independent_review_ready':False,'accepted_for_delivery':True}
    monkeypatch.setattr(review_jobs,'start',fake)
    result=await server.workbench_review_agent('start',operation_id='one',packet_path='packet.json',output='output',
        codex_home=str(home),project_root='.',use_personal_codex_home=True)
    assert calls==[(('one',scoped/'packet.json',scoped/'output',str(home),scoped,600),{'base':scoped})]
    assert result['accepted_for_delivery'] is False and result['review_agent_tool']=='workbench_review_agent'


@pytest.mark.asyncio
async def test_start_can_use_only_explicit_server_home(scoped,monkeypatch):
    home=scoped/'server-home';home.mkdir();monkeypatch.setenv('CODEX_HOME',str(home))
    calls=[]
    def fake(*args,**kwargs):calls.append(args);return {'status':'queued'}
    monkeypatch.setattr(review_jobs,'start',fake)
    await server.workbench_review_agent('start',operation_id='one',packet_path='p',output='out',use_personal_codex_home=True)
    assert calls[0][3]==str(home)


@pytest.mark.asyncio
async def test_prepare_passes_native_bindings_only_to_factory_not_executor(scoped,monkeypatch):
    evidence={'native':{'snapshot':{'path':'snapshot.json','sha256':'a'*64},'source_artifact_id':'source'}}
    seen=[]
    def prepare(*args,**kwargs):seen.append((args,kwargs));return {'accepted_for_delivery':False}
    monkeypatch.setattr(review_jobs,'packet_from_contract',prepare)
    result=await server.workbench_review_agent('prepare',contract_path='contract.json',packet_path='packet.json',
                                              contract_base='.',native_evidence=evidence)
    assert seen==[((scoped/'contract.json',scoped/'packet.json'),
                   {'base':scoped,'source_base':scoped,'native_evidence':evidence})]
    assert not result['accepted_for_delivery']


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['no_opt_in','no_home','relative_home','packet_escape','output_escape','project_escape',
    'prepare_missing','prepare_escape','source_base_escape','start_contract','status_missing','status_paths','unknown'])
async def test_review_tool_rejects_unsafe_or_ambiguous_requests(scoped,monkeypatch,fault):
    called=[]
    def forbidden(*args,**kwargs):called.append(1);raise AssertionError('No backend or model launch expected')
    for name in ('start','status','packet_from_contract'):monkeypatch.setattr(review_jobs,name,forbidden)
    args={'operation':'start','operation_id':'one','packet_path':'p','output':'out',
          'codex_home':str(scoped/'home'),'use_personal_codex_home':True}
    if fault=='no_opt_in':args['use_personal_codex_home']=False
    elif fault=='no_home':args.pop('codex_home')
    elif fault=='relative_home':args['codex_home']='home'
    elif fault=='packet_escape':args['packet_path']='../p'
    elif fault=='output_escape':args['output']='../out'
    elif fault=='project_escape':args['project_root']='..'
    elif fault=='start_contract':args['contract_path']='contract.json'
    elif fault=='prepare_missing':args={'operation':'prepare','packet_path':'p'}
    elif fault=='prepare_escape':args={'operation':'prepare','contract_path':'../contract.json','packet_path':'p'}
    elif fault=='source_base_escape':args={'operation':'prepare','contract_path':'contract.json','packet_path':'p','contract_base':'..'}
    elif fault=='status_missing':args={'operation':'status'}
    elif fault=='status_paths':args={'operation':'status','operation_id':'one','packet_path':'p'}
    else:args={'operation':'shell'}
    with pytest.raises(ValueError):await server.workbench_review_agent(**args)
    assert not called


@pytest.mark.asyncio
async def test_status_never_launches_and_ready_is_still_not_final_acceptance(scoped,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('No launch or prepare during status')
    monkeypatch.setattr(review_jobs,'start',forbidden);monkeypatch.setattr(review_jobs,'packet_from_contract',forbidden)
    calls=[]
    def query(*args,**kwargs):
        calls.append((args,kwargs));return {'status':'ready','independent_review_ready':True,
                                           'accepted_for_delivery':True,'agent_verdict':False}
    monkeypatch.setattr(review_jobs,'status',query)
    result=await server.workbench_review_agent('status',operation_id='one')
    assert calls==[(('one',),{'base':scoped})]
    assert result['independent_review_ready'] and result['agent_verdict'] is False
    assert result['accepted_for_delivery'] is False and result['delivery_review_tool']=='workbench_delivery'


@pytest.mark.asyncio
async def test_tool_schema_exposes_finite_operations_no_executor_or_base_override():
    tool=next(t for t in await server.mcp.list_tools() if t.name=='workbench_review_agent')
    properties=tool.inputSchema['properties']
    assert set(properties['operation']['enum'])=={'prepare','start','status'}
    assert properties['use_personal_codex_home']['default'] is False
    assert properties['timeout_seconds']['default']==600
    assert not {'base','command','executor','model','provider','auth','environment'} & set(properties)
    assert 'contract_base' in properties and 'native_evidence' in properties
    assert 'workbench_delivery' in tool.description and 'accepted_for_delivery always false' in tool.description
    assert 'status' in tool.description and 'SAME operation_id' in tool.description


@pytest.mark.asyncio
async def test_actual_mcp_call_returns_final_gate_requirement(scoped,monkeypatch):
    monkeypatch.setattr(review_jobs,'status',lambda *a,**k:{'operation_id':'one','status':'running','accepted_for_delivery':False})
    blocks=await server.mcp.call_tool('workbench_review_agent',{'operation':'status','operation_id':'one'})
    structured=json.loads(blocks[0].text)
    assert structured['accepted_for_delivery'] is False
    assert structured['review_agent_tool']=='workbench_review_agent'
    assert structured['delivery_review_tool']=='workbench_delivery'
    assert 'running' in blocks[0].text


@pytest.mark.asyncio
async def test_mcp_prepare_start_status_real_factory_and_journal_without_model(scoped,monkeypatch):
    _,_,home=contract_fixture(scoped)
    config=(home/'config.toml').read_bytes();launches=[]
    def controlled_no_launch(*args):
        launches.append(args);return type('ControlledNoModelProcess',(),{'pid':123456})()
    monkeypatch.setattr(review_jobs,'_launch',controlled_no_launch)
    monkeypatch.setattr(review_jobs,'_process_state',lambda pid:{'state':'unknown','pid':pid,'reason':'controlled no-process fixture'})
    async def call(arguments):
        blocks=await server.mcp.call_tool('workbench_review_agent',arguments)
        return json.loads(blocks[0].text)
    packet=await call({'operation':'prepare','contract_path':'contract.json','packet_path':'packet.json'})
    assert packet['packet']['sha256']==review_jobs._hash(scoped/'packet.json')
    request={'operation':'start','operation_id':'one','packet_path':'packet.json','output':'out',
             'codex_home':str(home),'use_personal_codex_home':True}
    first=await call(request);again=await call(request)
    queried=await call({'operation':'status','operation_id':'one'})
    assert first['status']==again['status']==queried['status']=='queued'
    assert len(launches)==1
    assert not queried['accepted_for_delivery'] and not queried['independent_review_ready']
    assert queried['review_agent_tool']=='workbench_review_agent' and queried['delivery_review_tool']=='workbench_delivery'
    assert (home/'config.toml').read_bytes()==config


def test_factory_explicit_source_base_rejects_escape_and_preserves_default(tmp_path):
    path,_,_=contract_fixture(tmp_path)
    nested=tmp_path/'nested';nested.mkdir()
    with pytest.raises(ValueError,match='within'):
        review_jobs.packet_from_contract(path,tmp_path/'packet.json',base=tmp_path,source_base=tmp_path.parent)
    assert not (tmp_path/'packet.json').exists()
    result=review_jobs.packet_from_contract(path,tmp_path/'packet.json',base=tmp_path)
    assert result['packet']['sha256']==review_jobs._hash(tmp_path/'packet.json')


@pytest.mark.parametrize('fault',['invalid_snapshot','missing_reader','unexpected_code','missing_source'])
def test_factory_native_evidence_fails_before_packet_creation_without_downgrade(tmp_path,monkeypatch,fault):
    """Real validation hook rejects controlled fake native evidence; no CAD call."""
    from luomu_cad import review_runner
    path,contract,_=contract_fixture(tmp_path)
    native=tmp_path/'native.dwg';native.write_bytes(b'AC1032CONTROLLED_NOT_A_REAL_DWG')
    brief=review_jobs._load(tmp_path/'customer.json')
    brief['required_sheets'][0]['formats'].append('dwg')
    brief['required_sheets'][0]['expected']['dwg']={'units':4}
    contract['customer_brief']=save(tmp_path/'customer.json',brief)
    contract['artifacts'].append({'id':'dwg','path':native.name,'sha256':review_jobs._hash(native),
        'format':'dwg','industry_id':'interior','drawing_type':'interior.layout','sheet_id':'drawing','expected':{'units':4}})
    save(path,contract)
    snapshot=tmp_path/'snapshot.json';record=save(snapshot,{'controlled_fake_native_snapshot':True})
    evidence={'dwg':{'snapshot':record,'source_artifact_id':'native'}}
    if fault=='missing_reader':monkeypatch.setattr(review_runner,'validate_native_evidence',None)
    elif fault=='unexpected_code':evidence['dwg']['code']='do not execute'
    elif fault=='missing_source':evidence['dwg']['source_artifact_id']='absent'
    with pytest.raises(ValueError):
        review_jobs.packet_from_contract(path,tmp_path/'packet.json',base=tmp_path,native_evidence=evidence)
    assert not (tmp_path/'packet.json').exists()
    assert review_jobs._load(tmp_path/'customer.json')['required_sheets'][0]['formats']==['dxf','dwg']
    assert native.read_bytes()==b'AC1032CONTROLLED_NOT_A_REAL_DWG'
