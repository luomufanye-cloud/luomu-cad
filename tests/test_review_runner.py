"""Controlled subprocess/event fixtures test the gate, not live model capability."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import os
import shutil
import subprocess

import ezdxf
import pytest
from pypdf import PdfWriter

from luomu_cad import review_runner
from luomu_cad.review_evidence_server import Evidence
from luomu_cad.storage import ROOT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def task(tmp_path):
    brief=tmp_path/'customer.json'
    brief.write_text(json.dumps({'scope':'reference_redraw','requirements':[
        {'id':'R1','description':'Original line from0,0 to1000,0'},
        {'id':'R2','description':'Keep explicit model millimetres'}],
        'required_sheets':[{'sheet_id':'drawing','formats':['dxf']}]}),encoding='utf8')
    drawing=tmp_path/'drawing.dxf';doc=ezdxf.new();doc.units=4;doc.modelspace().add_line((0,0),(1000,0));doc.saveas(drawing)
    packet=tmp_path/'packet.json';packet.write_text(json.dumps({'schema_version':1,'contract_id':'original-task',
        'customer_brief':{'path':brief.name,'sha256':digest(brief)},
        'artifacts':[{'id':'native','path':drawing.name,'sha256':digest(drawing)}]}),encoding='utf8')
    home=tmp_path/'home';home.mkdir();(home/'config.toml').write_text('model="existing-model"\nmodel_provider="existing-provider"\n',encoding='utf8')
    return packet,drawing,home


def response():
    return {'accepted_for_delivery':True,'requirement_inventory_checked':True,
        'inventory_observation':'The original brief contains exactly R1 and R2; both reviewed independently.',
        'requirements':[{'requirement_id':key,'verdict':'accepted','finding':'Read the native model file and measured its requested properties.',
            'observations':[{'artifact_id':'native','locator':'DXF modelspace LINE and header',
                'source_locator':'Original customer requirement '+key,'finding':'The measured native properties correspond to the original requirement.','preview_index':0}]} for key in ['R1','R2']],
        'unresolved':[]}


def native_fixture(monkeypatch,tmp_path,value=None,mode='normal'):
    """Use a real fixture subprocess; explicitly never claim this is a real model."""
    final=response() if value is None else value
    script=tmp_path/'fixture-cli.py'
    script.write_text('''import json,sys,time,hashlib
from pathlib import Path
sys.path.insert(0,'''+repr(str(ROOT/'src'))+''')
from luomu_cad.review_evidence_server import Evidence,encoded
mode='''+repr(mode)+'''
args=sys.argv[1:]
target=Path(args[args.index('--output-last-message')+1])
print(json.dumps({'type':'thread.started','thread_id':'controlled-fixture-session'}),flush=True)
if mode=='timeout':time.sleep(5)
if mode=='nonzero':raise SystemExit(9)
if mode!='no_checks':
 config=next(v for v in args if v.startswith('mcp_servers.') and '.args=' in v)
 server_name=config.split('.')[1]
 server_args=json.loads(config.split('=',1)[1]);lock=Path(server_args[server_args.index('--lock')+1]);packet=Path(server_args[server_args.index('--packet')+1])
 evidence=Evidence(packet,lock,target.parent)
 def event(tool,arguments,response,image=None):
  blocks=[{'type':'text','text':encoded(response)}]
  if image is not None:blocks.append(image.model_dump(exclude_none=True))
  print(json.dumps({'type':'item.completed','item':{'id':'call-'+response['record_id'],'type':'mcp_tool_call','server':server_name,'tool':tool,'arguments':arguments,'status':'completed','result':{'content':blocks},'error':None}}),flush=True)
 for fid,row in evidence.records.items():
  if mode=='omitted_file_read' and fid=='brief':continue
  if mode=='omitted_original_task' and fid=='source:0':continue
  read=evidence.read(fid)
  if mode=='wrong_hash':read['source_sha256']='0'*64
  event('review_read',{'file_id':fid},read)
  for index in range(len(row['previews'])):
   if mode=='omitted_image':continue
   response,image=evidence.view(fid,index)
   event('review_view',{'file_id':fid,'preview_index':index},response,None if mode=='image_bytes_missing' else image)
 if mode=='ledger_missing':evidence.close();evidence.audit.unlink()
 if mode=='echo':print(json.dumps({'type':'item.completed','item':{'type':'command_execution','exit_code':0,'command':'echo original-file','aggregated_output':'success'}}),flush=True)
 if mode=='own_pending':print(json.dumps({'type':'item.started','item':{'id':'unfinished-evidence-call','type':'mcp_tool_call','server':server_name,'tool':'review_read','arguments':{'file_id':'brief'},'status':'in_progress'}}),flush=True)
 if mode=='reused_pending':print(json.dumps({'type':'item.started','item':{'id':'call-'+read['record_id'],'type':'mcp_tool_call','server':server_name,'tool':'review_read','arguments':{'file_id':fid},'status':'in_progress'}}),flush=True)
 if mode=='own_failed':print(json.dumps({'type':'item.completed','item':{'id':'failed-evidence-call','type':'mcp_tool_call','server':server_name,'tool':'review_read','arguments':{'file_id':'brief'},'status':'failed','error':{'message':'tool approval rejected'}}}),flush=True)
 if mode=='policy_refusal':print('CreateProcess rejected: blocked by policy',file=sys.stderr,flush=True)
if mode=='mcp':
 print(json.dumps({'type':'item.completed','item':{'type':'mcp_tool_call','status':'completed'}}),flush=True)
if mode=='started_mcp':
 print(json.dumps({'type':'item.started','item':{'type':'mcp_tool_call','status':'in_progress'}}),flush=True)
if mode=='changed_input':
 p=Path('''+repr(str(tmp_path/'drawing.dxf'))+''');p.write_bytes(p.read_bytes()+b'changed')
if mode=='config_changed':
 p=Path('''+repr(str(tmp_path/'home/config.toml'))+''');p.write_text('model="other"',encoding='utf8')
if mode=='config_deleted':Path('''+repr(str(tmp_path/'home/config.toml'))+''').unlink()
if mode!='missing_result':target.write_text('''+repr(json.dumps(final))+''',encoding='utf8')
if mode!='no_model_event':print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':('Different result' if mode=='mismatched_model_event' else ''' + repr(json.dumps(final)) + ''')}}),flush=True)
print(json.dumps({'type':'turn.completed'}),flush=True)
''',encoding='utf8')
    original=review_runner.subprocess.Popen
    seen=[]
    def launch(args,**kwargs):
        if args[0]!=sys.executable:return original(args,**kwargs)
        seen.append(args)
        assert args[args.index('-s')+1]=='read-only'
        assert '--ephemeral' in args and '--output-schema' in args
        assert args[-2]=='--' and args[-1].startswith('现在立即调用指定只读证据MCP')
        assert not any(v in args for v in ['--model','-m','--local-provider','--oss'])
        assert not any(str(v).startswith('model_provider=') for v in args)
        return original([sys.executable,str(script),*args[1:]],**kwargs)
    monkeypatch.setattr(review_runner,'native_codex',lambda:sys.executable)
    monkeypatch.setattr(review_runner,'_configured_mcp_names',lambda *_:['home-server','project-server'])
    monkeypatch.setattr(review_runner.subprocess,'Popen',launch)
    return seen


def test_real_process_events_and_result_are_bound_but_do_not_replace_delivery_gate(tmp_path,monkeypatch):
    packet,drawing,home=task(tmp_path);before=digest(drawing);seen=native_fixture(monkeypatch,tmp_path)
    result=review_runner.run(packet,tmp_path/'review',home,bundle_root=ROOT)
    assert result['independent_review_ready'],result
    assert result['agent_verdict'] is True and result['accepted_for_delivery'] is False
    assert result['execution_mode']=='isolated_cli_reviewer'
    assert result['execution']['successful_check_commands']==0
    assert result['execution']['successful_evidence_reads']==3
    assert result['execution']['session_ids']==['controlled-fixture-session']
    independent=json.loads(Path(result['independent_review']['path']).read_text(encoding='utf8'))
    assert independent['artifact_sha256']=={'native':before}
    assert independent['reviewer_id']=='isolated-cli:controlled-fixture-session'
    assert digest(drawing)==before
    assert 'developer_instructions=' in ' '.join(seen[0])
    assert 'mcp_servers.project-server.enabled=false' in seen[0]
    assert not result['native_spawn_claimed']


def test_producer_identity_is_metadata_without_producer_reports_or_expected_verdicts(tmp_path,monkeypatch):
    packet,_,home=task(tmp_path);data=json.loads(packet.read_text(encoding='utf8'))
    data['producer_id']='original-generation-session';packet.write_text(json.dumps(data),encoding='utf8')
    native_fixture(monkeypatch,tmp_path)
    result=review_runner.run(packet,tmp_path/'review',home,bundle_root=ROOT)
    assert result['independent_review_ready']
    inputs=json.loads((tmp_path/'review/input-inventory.json').read_text(encoding='utf8'))
    assert inputs['producer_id']=='original-generation-session'
    assert inputs['producer_identity_authenticated'] is False
    assert inputs['review_process_provenance']['session_id_source'].startswith('Controller binds')


def cross_format_task(tmp_path):
    packet,drawing,home=task(tmp_path)
    paper=tmp_path/'drawing.pdf';writer=PdfWriter();writer.add_blank_page(width=300,height=200)
    with paper.open('wb') as stream:writer.write(stream)
    brief=tmp_path/'customer.json';source=json.loads(brief.read_text(encoding='utf8'))
    source['required_sheets'][0]['formats'].append('pdf')
    source['requirements'][0]['checks']=[{'artifact_id':'native'}]
    source['requirements'][1]['checks']=[{'artifact_id':'paper','source_artifact_id':'native'}]
    brief.write_text(json.dumps(source),encoding='utf8')
    value=json.loads(packet.read_text(encoding='utf8'));value['customer_brief']['sha256']=digest(brief)
    value['artifacts'].append({'id':'paper','path':paper.name,'sha256':digest(paper)})
    packet.write_text(json.dumps(value),encoding='utf8')
    return packet,drawing,home


@pytest.mark.parametrize('actual_read',[False,True])
def test_original_task_binding_requires_actual_source_zero_read(tmp_path,monkeypatch,actual_read):
    packet,_,home=task(tmp_path);source=tmp_path/'original-task.txt';source.write_text('Original customer request: line1000mm, preserve model units.',encoding='utf8')
    raw={'path':source.name,'sha256':digest(source)}
    brief=tmp_path/'customer.json';data=json.loads(brief.read_text(encoding='utf8'));data['original_task']=raw
    brief.write_text(json.dumps(data),encoding='utf8')
    value=json.loads(packet.read_text(encoding='utf8'));value['customer_brief']['sha256']=digest(brief);value['raw_sources']=[raw]
    packet.write_text(json.dumps(value),encoding='utf8')
    native_fixture(monkeypatch,tmp_path,mode='normal' if actual_read else 'omitted_original_task')
    result=review_runner.run(packet,tmp_path/'review',home,bundle_root=ROOT)
    assert result['independent_review_ready'] is actual_read,result
    if actual_read:
        report=json.loads(Path(result['independent_review']['path']).read_text(encoding='utf8'))
        assert report['original_task_sha256']==raw['sha256']
    else:assert not (tmp_path/'review/independent-review.json').exists()


@pytest.mark.parametrize('mutation',['missing','wrong_position','other_same_hash_path'])
def test_original_task_cannot_be_claimed_without_matching_source_zero(tmp_path,mutation):
    packet,_,home=task(tmp_path);source=tmp_path/'task.txt';source.write_text('original task',encoding='utf8')
    copy_source=tmp_path/'other.txt';copy_source.write_bytes(source.read_bytes())
    raw={'path':source.name,'sha256':digest(source)};other={'path':copy_source.name,'sha256':digest(copy_source)}
    brief=tmp_path/'customer.json';data=json.loads(brief.read_text(encoding='utf8'));data['original_task']=raw;brief.write_text(json.dumps(data),encoding='utf8')
    data=json.loads(packet.read_text(encoding='utf8'));data['customer_brief']['sha256']=digest(brief)
    data['raw_sources']={'missing':[],'wrong_position':[other,raw],'other_same_hash_path':[other]}[mutation]
    packet.write_text(json.dumps(data),encoding='utf8')
    with pytest.raises(ValueError,match='ORIGINAL_TASK_SOURCE_ZERO_REQUIRED'):review_runner._prepare(packet)


@pytest.mark.parametrize('complete',[False,True])
def test_cross_format_requirement_needs_its_own_source_and_target_observations(tmp_path,monkeypatch,complete):
    packet,_,home=cross_format_task(tmp_path);value=response()
    # The native source was observed under R1, but that does not cover R2.
    value['requirements'][1]['observations'][0]['artifact_id']='paper'
    if complete:
        native=copy.deepcopy(value['requirements'][1]['observations'][0]);native['artifact_id']='native'
        value['requirements'][1]['observations'].append(native)
    native_fixture(monkeypatch,tmp_path,value)
    result=review_runner.run(packet,tmp_path/'review',home,bundle_root=ROOT)
    assert result['independent_review_ready'] is complete,result
    if not complete:
        assert 'INDEPENDENT_REQUIREMENT_ARTIFACT_COVERAGE_INCOMPLETE: R2' in result['findings'][0]['error']
        assert not (tmp_path/'review/independent-review.json').exists()
    inventory=json.loads((tmp_path/'review/input-inventory.json').read_text(encoding='utf8'))
    assert inventory['requirement_artifact_ids']=={'R1':['native'],'R2':['native','paper']}


def test_multi_artifact_associations_cannot_be_guessed_or_relabelled(tmp_path):
    packet,_,home=cross_format_task(tmp_path);brief=tmp_path/'customer.json'
    for mutation in ['missing','unknown_source']:
        source=json.loads(brief.read_text(encoding='utf8'))
        if mutation=='missing':source['requirements'][1].pop('checks')
        else:source['requirements'][1]['checks']=[{'artifact_id':'paper','source_artifact_id':'not-in-original-packet'}]
        brief.write_text(json.dumps(source),encoding='utf8')
        data=json.loads(packet.read_text(encoding='utf8'));data['customer_brief']['sha256']=digest(brief)
        packet.write_text(json.dumps(data),encoding='utf8')
        with pytest.raises(ValueError):review_runner.run(packet,tmp_path/('review-'+mutation),home,bundle_root=ROOT)


@pytest.mark.parametrize('mode,error',[('no_checks','EVIDENCE_FILE_READ_COVERAGE_INCOMPLETE'),('nonzero','REVIEWER_PROCESS_FAILED'),
    ('missing_result','REVIEWER_RESULT_MISSING'),('mcp','UNEXPECTED_DELEGATION_OR_MCP'),
    ('started_mcp','UNEXPECTED_DELEGATION_OR_MCP'),('echo','UNEXPECTED_DELEGATION_OR_COMMAND'),
    ('omitted_file_read','EVIDENCE_FILE_READ_COVERAGE_INCOMPLETE'),('omitted_image','EVIDENCE_IMAGE_COVERAGE_INCOMPLETE'),
    ('wrong_hash','EVIDENCE_SOURCE_BINDING_MISMATCH'),('ledger_missing','EVIDENCE_REAL_READ_RECORD_MISSING'),
    ('image_bytes_missing','EVIDENCE_ACTUAL_IMAGE_MISSING'),
    ('own_pending','EVIDENCE_TOOL_CALL_NOT_COMPLETED'),('own_failed','EVIDENCE_TOOL_REFUSED_OR_FAILED'),
    ('reused_pending','EVIDENCE_NATIVE_CALL_ID_REUSED_OR_CHANGED'),
    ('policy_refusal','REVIEWER_HOST_POLICY_REFUSAL'),
    ('no_model_event','REVIEWER_MODEL_RESULT_EVENT_MISSING'),('mismatched_model_event','REVIEWER_FINAL_NOT_BOUND_TO_MODEL_EVENT'),
    ('changed_input','RAW_INPUT_CHANGED'),('config_changed','HOST_CONFIG_CHANGED'),('config_deleted','HOST_CONFIG_CHANGED')])
def test_false_or_missing_execution_evidence_never_reaches_ready(tmp_path,monkeypatch,mode,error):
    packet,_,home=task(tmp_path);native_fixture(monkeypatch,tmp_path,mode=mode)
    result=review_runner.run(packet,tmp_path/'review',home,bundle_root=ROOT)
    assert not result['independent_review_ready'] and not result['accepted_for_delivery']
    assert error in result['findings'][0]['error']
    assert not (tmp_path/'review/independent-review.json').exists()


def test_deadline_stops_real_owned_fixture_process(tmp_path,monkeypatch):
    packet,_,home=task(tmp_path);native_fixture(monkeypatch,tmp_path,mode='timeout')
    result=review_runner.run(packet,tmp_path/'review',home,timeout_seconds=1,bundle_root=ROOT)
    assert result['execution']['timed_out'] and result['execution']['elapsed_seconds']<4
    assert not result['independent_review_ready']


@pytest.mark.parametrize('mutation',['omitted','duplicate','claim_over_rejected','empty_observation','unknown_artifact','wrong_preview'])
def test_model_result_cannot_omit_or_relabel_original_customer_requirements(tmp_path,monkeypatch,mutation):
    packet,_,home=task(tmp_path);value=response()
    if mutation=='omitted':value['requirements'].pop()
    elif mutation=='duplicate':value['requirements'][1]['requirement_id']='R1'
    elif mutation=='claim_over_rejected':value['requirements'][0]['verdict']='rejected'
    elif mutation=='empty_observation':value['requirements'][0]['observations']=[]
    elif mutation=='unknown_artifact':value['requirements'][0]['observations'][0]['artifact_id']='other'
    else:value['requirements'][0]['observations'][0]['preview_index']=999
    native_fixture(monkeypatch,tmp_path,value)
    result=review_runner.run(packet,tmp_path/'review',home,bundle_root=ROOT)
    assert not result['independent_review_ready'],mutation


def test_actual_rejection_is_returned_without_changing_it_to_acceptance(tmp_path,monkeypatch):
    packet,_,home=task(tmp_path);value=response();value['accepted_for_delivery']=False
    value['requirements'][1]['verdict']='rejected';value['unresolved']=['Original required dimension is missing']
    native_fixture(monkeypatch,tmp_path,value)
    result=review_runner.run(packet,tmp_path/'review',home,bundle_root=ROOT)
    assert result['independent_review_ready'] and result['agent_verdict'] is False
    assert result['accepted_for_delivery'] is False


def test_overall_rejection_without_per_item_rejection_remains_blocking(tmp_path,monkeypatch):
    packet,_,home=task(tmp_path);value=response();value['accepted_for_delivery']=False
    native_fixture(monkeypatch,tmp_path,value)
    result=review_runner.run(packet,tmp_path/'review',home,bundle_root=ROOT)
    assert result['independent_review_ready'] and result['agent_verdict'] is False
    independent=json.loads(Path(result['independent_review']['path']).read_text(encoding='utf8'))
    assert independent['unresolved']


def test_readonly_inspection_reopens_actual_native_values_and_preview_is_attached(tmp_path,monkeypatch):
    packet,drawing,home=task(tmp_path);before=digest(drawing)
    facts=review_runner.inspect_packet(packet)
    assert facts['artifacts']['native']['units']==4
    line=facts['artifacts']['native']['entities'][0]
    assert line['type']=='LINE' and line['dxf']['end']==[1000,0,0]
    assert digest(drawing)==before
    seen=native_fixture(monkeypatch,tmp_path)
    result=review_runner.run(packet,tmp_path/'review',home,bundle_root=ROOT)
    assert result['independent_review_ready']
    assert '-i' in seen[0]
    manifest=json.loads((tmp_path/'review/launch-manifest.json').read_text(encoding='utf8'))
    assert manifest['images_attached'][0]['sha256']==digest(Path(manifest['images_attached'][0]['path']))


@pytest.mark.parametrize('mutation',['missing_inventory','missing_format','unknown_format','missing_description'])
def test_original_sheet_inventory_is_required_before_model_launch(tmp_path,mutation):
    packet,drawing,home=task(tmp_path)
    data=json.loads(packet.read_text(encoding='utf8'));brief=tmp_path/'customer.json'
    value=json.loads(brief.read_text(encoding='utf8'))
    if mutation=='missing_inventory':value.pop('required_sheets')
    elif mutation=='missing_format':value['required_sheets'][0]['formats'].append('pdf')
    elif mutation=='missing_description':value['requirements'][0].pop('description')
    else:
        drawing.rename(tmp_path/'drawing.dwg');data['artifacts'][0]['path']='drawing.dwg'
        value['required_sheets'][0]['formats']=['dwg']
    brief.write_text(json.dumps(value),encoding='utf8');data['customer_brief']['sha256']=digest(brief)
    packet.write_text(json.dumps(data),encoding='utf8')
    with pytest.raises(ValueError):review_runner.run(packet,tmp_path/'review',home,bundle_root=ROOT)
    assert not (tmp_path/'review').exists()


def test_raw_packet_rejects_producer_conclusions_and_output_overwrite(tmp_path,monkeypatch):
    packet,_,home=task(tmp_path)
    data=json.loads(packet.read_text(encoding='utf8'));data['producer_report']='pass';packet.write_text(json.dumps(data),encoding='utf8')
    with pytest.raises(ValueError,match='producer reports'):review_runner.run(packet,tmp_path/'review',home)
    data.pop('producer_report');packet.write_text(json.dumps(data),encoding='utf8')
    output=tmp_path/'existing';output.mkdir();(output/'keep.txt').write_text('user')
    with pytest.raises(ValueError,match='no overwrite'):review_runner.run(packet,output,home)
    assert (output/'keep.txt').read_text()=='user'


def test_artifact_name_cannot_escape_preview_directory(tmp_path):
    packet,_,home=task(tmp_path);data=json.loads(packet.read_text(encoding='utf8'))
    data['artifacts'][0]['id']='../escape';packet.write_text(json.dumps(data),encoding='utf8')
    with pytest.raises(ValueError,match='Artifact IDs'):review_runner.run(packet,tmp_path/'review',home)
    assert not (tmp_path/'review').exists()


def test_native_effective_project_and_home_mcp_are_disabled_without_starting_servers(tmp_path):
    if shutil.which('codex') is None:pytest.skip('Native Codex CLI unavailable')
    command=review_runner.native_codex()
    home=tmp_path/'home';home.mkdir();project=tmp_path/'project';project.mkdir()
    (project/'.git').mkdir();(project/'.codex').mkdir()
    trust=str(project).lower() if os.name=='nt' else str(project)
    (home/'config.toml').write_text('[projects.'+json.dumps(trust)+']\ntrust_level="trusted"\n[mcp_servers.home-server]\ncommand="never-start-this-server"\n',encoding='utf8')
    (project/'.codex/config.toml').write_text('[mcp_servers.project-server]\ncommand="never-start-this-project-server"\n',encoding='utf8')
    names=review_runner._configured_mcp_names(command,home,project)
    assert names==['home-server','project-server']
    args=[command,'-C',str(project)]
    for name in names:args+=['-c','mcp_servers.'+name+'.enabled=false']
    result=subprocess.run([*args,'mcp','list','--json'],cwd=project,
        env=dict(os.environ,CODEX_HOME=str(home)),stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr
    rows=json.loads(result.stdout)
    assert {r['name'] for r in rows}==set(names)
    assert all(r['enabled'] is False for r in rows)
