"""Controlled processes/events, NOT a live-model or recognition benchmark."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import ezdxf
import pytest

from luomu_cad import review_jobs as jobs
from luomu_cad.storage import ROOT, digest


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf8')
    return {'path':path.name,'sha256':jobs._hash(path)}


def contract_fixture(base):
    task = base/'task.txt';task.write_text('Original customer line and native units request',encoding='utf8')
    doc=ezdxf.new();doc.units=4;doc.modelspace().add_line((0,0),(1000,0));doc.saveas(base/'drawing.dxf')
    requirements=[{'id':rid,'description':description,'industry_id':'interior',
        'source_locator':'Original task '+rid,'checks':[{'id':rid+'-check','kind':'dxf_measure',
        'artifact_id':'native','measurement':{'kind':'length','expected':1000}}]}
        for rid,description in [('R1','Original line from0,0 to1000,0'),('R2','Keep explicit model millimetres')]]
    brief={'schema_version':1,'scope':'reference_redraw','jurisdiction':'CN','industries':['interior'],
           'original_task':{'path':task.name,'sha256':jobs._hash(task)},
           'requirements':requirements,'required_sheets':[{'sheet_id':'drawing','industry_id':'interior',
           'drawing_type':'interior.layout','formats':['dxf'],'expected':{'dxf':{'units':4}}}]}
    contract={'schema_version':1,'contract_id':'original-task','scope':brief['scope'],'jurisdiction':'CN',
              'industries':['interior'],'producer_id':'fixture-producer',
              'customer_brief':save(base/'customer.json',brief),'original_task_sha256':jobs._hash(task),
              'requirements':[{**copy.deepcopy(r),'artifact_ids':['native']} for r in requirements],
              'artifacts':[{'id':'native','path':'drawing.dxf','sha256':jobs._hash(base/'drawing.dxf'),
              'format':'dxf','industry_id':'interior','drawing_type':'interior.layout','sheet_id':'drawing',
              'expected':{'units':4},'passed':True,'producer_conclusion':'Trust producer statement'}],
              'independent_review':{'path':'old-report.json','sha256':'0'*64},'accepted_for_delivery':True,
              'standard_assignments':[]}
    source=base/'standard.txt';source.write_text('Original standard source fixture only',encoding='utf8')
    contract['standard_assignments']=[{'industry_id':'interior','standard_id':'interior-drawing',
        'source_evidence':{'path':source.name,'sha256':jobs._hash(source)},
        'evidence':{'path':'old-standards-report.json','sha256':'0'*64},'claims_compliance':True}]
    path=base/'contract.json';save(path,contract)
    home=base/'home';home.mkdir();(home/'config.toml').write_text('model="fixture-only"',encoding='utf8')
    return path,contract,home


def setup_packet(base):
    contract,_,home=contract_fixture(base)
    packet=base/'packet.json';jobs.packet_from_contract(contract,packet,base=base)
    return packet,home


def hold_launch(monkeypatch):
    calls=[]
    def launch(*args):
        calls.append(args)
        return type('Process',(),{'pid':123456})()
    monkeypatch.setattr(jobs,'_launch',launch)
    # This fixture deliberately has no OS process; it must not masquerade as a
    # live/dead worker. Real-process liveness is exercised separately below.
    monkeypatch.setattr(jobs,'_process_state',lambda pid:{'state':'unknown','pid':pid,'reason':'controlled no-process fixture'})
    return calls


def test_packet_exports_only_original_records(tmp_path):
    path,contract,_=contract_fixture(tmp_path)
    original=(tmp_path/'customer.json').read_bytes()
    result=jobs.packet_from_contract(path,tmp_path/'packet.json',base=tmp_path)
    packet=jobs._load(tmp_path/'packet.json')
    assert set(packet)=={'schema_version','contract_id','producer_id','customer_brief','artifacts','raw_sources','standard_sources'}
    assert packet['producer_id']=='fixture-producer'
    assert set(packet['artifacts'][0])=={'id','path','sha256','sheet_id'}
    assert packet['raw_sources'][0]['path']=='task.txt'
    assert packet['standard_sources'][0]['path']=='standard.txt'
    assert 'old-report' not in json.dumps(packet) and 'producer_conclusion' not in json.dumps(packet)
    assert (tmp_path/'customer.json').read_bytes()==original
    assert 'expected' in jobs._load(tmp_path/'customer.json')['required_sheets'][0]
    assert not result['accepted_for_delivery']
    with pytest.raises(FileExistsError):jobs.packet_from_contract(path,tmp_path/'packet.json',base=tmp_path)


def test_factory_packet_real_validator_and_evidence_service_read_original_task(tmp_path):
    from luomu_cad.review_runner import _prepare, _evidence_lock, _previews
    from luomu_cad.review_evidence_server import Evidence
    contract,_,_=contract_fixture(tmp_path)
    packet=tmp_path/'packet.json'
    task_sha=jobs._hash(tmp_path/'task.txt');brief_sha=jobs._hash(tmp_path/'customer.json')
    jobs.packet_from_contract(contract,packet,base=tmp_path)
    _,_,brief,ids,paths,tracked=_prepare(packet)
    assert ids==['R1','R2'] and brief['required_sheets'][0]['industry_id']=='interior'
    assert tracked[tmp_path/'task.txt']==task_sha
    output=tmp_path/'direct-evidence';output.mkdir()
    previews=_previews(paths,output)
    lock_path,lock=_evidence_lock(packet,previews,output,'controlled-no-model')
    task_record=next(row for row in lock['files'] if row['path']==str(tmp_path/'task.txt'))
    assert task_record['file_id']=='source:0' and task_record['sha256']==task_sha
    evidence=Evidence(packet,lock_path,output)
    inventory=evidence.inventory()
    assert task_record['file_id'] in json.dumps(inventory)
    read=evidence.read(task_record['file_id'])
    assert read['source_sha256']==task_sha
    assert 'Original customer line and native units request' in json.dumps(read)
    evidence.close()
    assert jobs._hash(tmp_path/'task.txt')==task_sha
    assert jobs._hash(tmp_path/'customer.json')==brief_sha


@pytest.mark.parametrize('fault',['checks','requirement_ids','scope','jurisdiction','industry','sheet_industry',
    'drawing_type','extra_sheet','missing_artifact','format','weakened_expected','source_hash','escape',
    'cross_requirement','association','original_task','brief_hash','invalid_artifact_id','cross_standard'])
def test_packet_rejects_weakened_or_cross_industry_input(tmp_path,fault):
    path,c,_=contract_fixture(tmp_path)
    if fault=='checks':c['requirements'][0]['checks'][0]['measurement']['expected']=1
    elif fault=='requirement_ids':c['requirements'].pop()
    elif fault=='scope':c['scope']='drawing_delivery'
    elif fault=='jurisdiction':c['jurisdiction']='CN-Beijing'
    elif fault=='industry':c['industries']=['mechanical']
    elif fault=='sheet_industry':c['artifacts'][0]['industry_id']='mechanical'
    elif fault=='drawing_type':c['artifacts'][0]['drawing_type']='mechanical.assembly'
    elif fault=='extra_sheet':c['artifacts'][0]['sheet_id']='other'
    elif fault=='missing_artifact':c['artifacts']=[]
    elif fault=='format':c['artifacts'][0]['format']='dwg'
    elif fault=='weakened_expected':c['artifacts'][0]['expected']['units']=0
    elif fault=='source_hash':c['standard_assignments'][0]['source_evidence']['sha256']='0'*64
    elif fault=='escape':c['artifacts'][0]['path']='../drawing.dxf'
    elif fault=='association':c['requirements'][0]['artifact_ids']=['fake']
    elif fault=='original_task':c['original_task_sha256']='0'*64
    elif fault=='brief_hash':c['customer_brief']['sha256']='0'*64
    elif fault=='invalid_artifact_id':c['artifacts'][0]['id']='bad id'
    elif fault=='cross_standard':c['standard_assignments'][0]['standard_id']='mechanical-drawing'
    else:
        brief=jobs._load(tmp_path/'customer.json');brief['requirements'][0]['checks'][0]['artifact_id']='fake'
        c['requirements'][0]['checks']=copy.deepcopy(brief['requirements'][0]['checks'])
        c['customer_brief']=save(tmp_path/'customer.json',brief)
    save(path,c)
    with pytest.raises((ValueError,KeyError)):jobs.packet_from_contract(path,tmp_path/'packet.json',base=tmp_path)
    assert not (tmp_path/'packet.json').exists()


def test_idempotent_start_never_relaunches_uncertain_job(tmp_path,monkeypatch):
    packet,home=setup_packet(tmp_path);calls=hold_launch(monkeypatch)
    first=jobs.start('one',packet,tmp_path/'out',home,base=tmp_path)
    second=jobs.start('one',packet,tmp_path/'out',home,base=tmp_path)
    assert first['status']==second['status']=='queued' and len(calls)==1
    assert not second['accepted_for_delivery'] and not second['independent_review_ready']
    with pytest.raises(ValueError,match='JOB_CONFLICT'):
        jobs.start('one',packet,tmp_path/'out',home,timeout_seconds=601,base=tmp_path)
    with pytest.raises(ValueError,match='OUTPUT_RESERVED'):
        jobs.start('two',packet,tmp_path/'out/nested',home,base=tmp_path)
    assert len(calls)==1


@pytest.mark.parametrize('fault',['output_escape','packet_escape','project_escape','nonempty','input_parent','state_parent',
    'invalid_id','output_in_home','timeout_bool','timeout_nan','timeout_infinite','timeout_zero','timeout_too_large'])
def test_start_safety_boundaries(tmp_path,monkeypatch,fault):
    packet,home=setup_packet(tmp_path);calls=hold_launch(monkeypatch)
    output=tmp_path/'out';project=tmp_path;op='one';timeout=600
    if fault=='output_escape':output=tmp_path.parent/'escape'
    elif fault=='packet_escape':packet=tmp_path.parent/'packet.json'
    elif fault=='project_escape':project=tmp_path.parent
    elif fault=='nonempty':output.mkdir();(output/'important').write_text('keep')
    elif fault=='input_parent':output=tmp_path
    elif fault=='state_parent':output=tmp_path/'runtime'
    elif fault=='invalid_id':op='../one'
    elif fault=='output_in_home':output=home/'out'
    else:timeout={'timeout_bool':True,'timeout_nan':float('nan'),'timeout_infinite':float('inf'),'timeout_zero':0,'timeout_too_large':3601}[fault]
    with pytest.raises((ValueError,FileNotFoundError)):
        jobs.start(op,packet,output,home,project,timeout,base=tmp_path)
    assert not calls


def test_launch_failure_and_unknown_state_do_not_replay(tmp_path,monkeypatch):
    packet,home=setup_packet(tmp_path)
    calls=[]
    def fail(*args):calls.append(1);raise OSError('controlled launch failure')
    monkeypatch.setattr(jobs,'_launch',fail)
    assert jobs.start('one',packet,tmp_path/'out',home,base=tmp_path)['status']=='launch_failed'
    assert jobs.start('one',packet,tmp_path/'out',home,base=tmp_path)['status']=='launch_failed'
    assert len(calls)==1
    with pytest.raises(ValueError,match='UNKNOWN'):jobs.status('unknown',base=tmp_path)


def test_worker_rejects_duplicate_and_changed_inputs(tmp_path,monkeypatch):
    packet,home=setup_packet(tmp_path);hold_launch(monkeypatch)
    jobs.start('one',packet,tmp_path/'out',home,base=tmp_path)
    store=jobs._store(tmp_path);row=store.get('one')
    with pytest.raises(ValueError,match='NONCE'):jobs.worker(store.path('one'),tmp_path,'wrong')
    (tmp_path/'drawing.dxf').write_text('changed')
    result=jobs.worker(store.path('one'),tmp_path,row['nonce'])
    assert result['status']=='invalidated' and not result['independent_review_ready']
    assert store.get('one')['status']=='failed'
    with pytest.raises(ValueError,match='duplicate execution'):jobs.worker(store.path('one'),tmp_path,row['nonce'])


def test_preexisting_runner_report_is_not_discovered_as_success(tmp_path,monkeypatch):
    packet,home=setup_packet(tmp_path);hold_launch(monkeypatch)
    jobs.start('one',packet,tmp_path/'out',home,base=tmp_path)
    output=tmp_path/'out';output.mkdir();save(output/'runner-result.json',{'independent_review_ready':True})
    assert jobs.status('one',base=tmp_path)['status']=='queued'
    row=jobs._store(tmp_path).get('one')
    result=jobs.worker(jobs._store(tmp_path).path('one'),tmp_path,row['nonce'])
    assert result['status']=='failed' and 'OUTPUT_CHANGED' in result['error']


def fixture_subprocess_launcher(monkeypatch,tmp_path,mode='normal',pause=.25):
    """Actual fixed-worker/runner/event fixture child; model CLI is replaced only in tests."""
    fixture=tmp_path/'controlled-worker.py'
    fixture.write_text('''import sys,time
from pathlib import Path
sys.path.insert(0,'''+repr(str(ROOT/'src'))+''')
sys.path.insert(0,'''+repr(str(ROOT/'tests'))+''')
import pytest
from test_review_runner import native_fixture
from luomu_cad import review_jobs
patch=pytest.MonkeyPatch()
native_fixture(patch,Path('''+repr(str(tmp_path))+'''),mode='''+repr(mode)+''')
time.sleep('''+repr(pause)+''')
result=review_jobs.worker(Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3])
raise SystemExit(0 if result['independent_review_ready'] else 1)
''',encoding='utf8')
    processes=[]
    def launch(job,base,nonce,log):
        process=subprocess.Popen([sys.executable,str(fixture),str(job),str(base),nonce],
             stdin=subprocess.DEVNULL,stdout=log,stderr=log,close_fds=True,
             **({'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}))
        processes.append(process);return process
    monkeypatch.setattr(jobs,'_launch',launch)
    return processes


def wait_done(base,timeout=35):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        state=jobs.status('one',base=base)
        if state['status'] not in {'queued','running'}:return state
        time.sleep(.1)
    raise AssertionError('Worker did not complete; log: '+(base/'runtime/review-jobs/one.worker.log').read_text(encoding='utf8'))


def test_real_background_fixture_survives_short_start_and_integrity_rechecked(tmp_path,monkeypatch):
    packet,home=setup_packet(tmp_path);processes=fixture_subprocess_launcher(monkeypatch,tmp_path)
    before=time.monotonic();initial=jobs.start('one',packet,tmp_path/'out',home,base=tmp_path)
    assert time.monotonic()-before<5 and initial['status'] in {'queued','running'}
    assert jobs.start('one',packet,tmp_path/'out',home,base=tmp_path)['operation_id']=='one'
    final=wait_done(tmp_path)
    assert final['status']=='ready',final
    assert final['independent_review_ready'] and not final['accepted_for_delivery']
    assert len(processes)==1
    assert processes[0].wait(timeout=5)==0
    # A brand-new API process reads the same state; no parent object is needed.
    command='from luomu_cad.review_jobs import status;import json;print(json.dumps(status("one",base='+repr(str(tmp_path))+')))'
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
    other=subprocess.run([sys.executable,'-c',command],env=env,capture_output=True,text=True,timeout=15)
    assert other.returncode==0,other.stderr
    assert json.loads(other.stdout)['independent_review_ready']
    # Each layer is rechecked; restore bytes after each fault to isolate it.
    for target in (tmp_path/'out/events.jsonl',tmp_path/'out/runner-result.json',
                   tmp_path/'runtime/review-jobs/one.receipt',tmp_path/'packet.json',tmp_path/'task.txt'):
        original=target.read_bytes();target.write_bytes(original+b'changed evidence')
        invalid=jobs.status('one',base=tmp_path)
        assert invalid['status']=='invalidated' and not invalid['independent_review_ready'],target
        target.write_bytes(original)
        assert jobs.status('one',base=tmp_path)['independent_review_ready']
    assert len(processes)==1


@pytest.mark.parametrize('mode',['timeout','missing_result','mismatched_model_event','own_failed'])
def test_background_fixture_failures_are_not_delivery_success(tmp_path,monkeypatch,mode):
    packet,home=setup_packet(tmp_path);processes=fixture_subprocess_launcher(monkeypatch,tmp_path,mode,pause=0)
    jobs.start('one',packet,tmp_path/'out',home,timeout_seconds=1 if mode=='timeout' else 20,base=tmp_path)
    result=wait_done(tmp_path)
    assert result['status']=='failed',result
    assert not result['independent_review_ready'] and not result['accepted_for_delivery']
    processes[0].wait(timeout=5)
    jobs.start('one',packet,tmp_path/'out',home,timeout_seconds=1 if mode=='timeout' else 20,base=tmp_path)
    assert len(processes)==1


def test_fixed_launcher_uses_only_installed_worker_and_hidden_detached_flags(tmp_path,monkeypatch):
    calls=[]
    def popen(args,**kwargs):calls.append((args,kwargs));return type('P',(),{'pid':1})()
    monkeypatch.setattr(jobs.subprocess,'Popen',popen)
    with (tmp_path/'log').open('wb') as log:jobs._launch(tmp_path/'one.json',tmp_path,'nonce',log)
    args,kwargs=calls[0]
    assert args[0]==sys.executable and Path(args[1]).name=='review_job_worker.py'
    assert args[2:]==['--job',str(tmp_path/'one.json'),'--base',str(tmp_path),'--nonce','nonce']
    assert kwargs['stdin']==subprocess.DEVNULL and kwargs['close_fds']
    assert 'shell' not in kwargs and '--model' not in args
    if os.name=='nt':
        assert kwargs['creationflags'] & subprocess.DETACHED_PROCESS
        assert kwargs['startupinfo'].wShowWindow==0
    else:assert kwargs['start_new_session']


def test_worker_script_supports_flat_installed_layout(tmp_path):
    bundle=tmp_path/'flat';(bundle/'scripts').mkdir(parents=True);(bundle/'luomu_cad').mkdir()
    shutil.copyfile(ROOT/'scripts/review_job_worker.py',bundle/'scripts/review_job_worker.py')
    (bundle/'luomu_cad/__init__.py').write_text('')
    (bundle/'luomu_cad/review_jobs.py').write_text('def worker(*a): return {"independent_review_ready": True}')
    result=subprocess.run([sys.executable,str(bundle/'scripts/review_job_worker.py'),'--job','j','--base','b','--nonce','n'],
                          capture_output=True,text=True,timeout=10,env=dict(os.environ,PYTHONPATH=''))
    assert result.returncode==0,result.stderr


def test_real_default_worker_continues_after_launcher_api_process_exits(tmp_path):
    """Temporary flat installation with a clearly fake runner; no real model/API."""
    base=tmp_path/'authorized';base.mkdir();packet,home=setup_packet(base)
    bundle=tmp_path/'controlled-install';(bundle/'scripts').mkdir(parents=True);package=bundle/'luomu_cad';package.mkdir()
    # A nearby script must never be mistaken for this installed bundle's worker.
    (tmp_path/'scripts').mkdir()
    (tmp_path/'scripts/review_job_worker.py').write_text('raise SystemExit("UNRELATED_WORKER_MUST_NOT_RUN")')
    for name in ('review_jobs.py','storage.py'):shutil.copyfile(ROOT/'src/luomu_cad'/name,package/name)
    shutil.copyfile(ROOT/'scripts/review_job_worker.py',bundle/'scripts/review_job_worker.py')
    (package/'__init__.py').write_text('')
    (package/'review_runner.py').write_text('''import json,time,hashlib
from pathlib import Path
def _prepare(packet):
 p=Path(packet);v=json.loads(p.read_text());rows=[v['customer_brief'],*v['artifacts'],*v['raw_sources'],*v['standard_sources']]
 tracked={p:hashlib.sha256(p.read_bytes()).hexdigest()}
 for r in rows:
  target=(p.parent/r['path']).resolve()
  assert hashlib.sha256(target.read_bytes()).hexdigest()==r['sha256']
  tracked[target]=r['sha256']
 return p,v,{},[],{},tracked
def run(packet,output,*args):
 time.sleep(1)
 output=Path(output);output.mkdir()
 result={'execution_mode':'isolated_cli_reviewer','accepted_for_delivery':False,'independent_review_ready':False,'artifacts':{},'findings':[{'kind':'CONTROLLED_FAKE_RUNNER_NO_MODEL'}]}
 (output/'runner-result.json').write_text(json.dumps(result))
 return result
''',encoding='utf8')
    command=('import json;from luomu_cad.review_jobs import start;print(json.dumps(start("one",'
             +repr(str(packet))+','+repr(str(base/'out'))+','+repr(str(home))+',base='+repr(str(base))+')))')
    result=subprocess.run([sys.executable,'-c',command],cwd=bundle,capture_output=True,text=True,
                          env=dict(os.environ,PYTHONPATH=str(bundle)),timeout=10)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['status'] in {'queued','running'}
    # The API process is now gone. The detached fixed worker must still finish.
    final=wait_done(base,timeout=20)
    assert final['status']=='failed',final
    assert final['findings'][0]['kind']=='CONTROLLED_FAKE_RUNNER_NO_MODEL'
    assert not final['independent_review_ready'] and not final['accepted_for_delivery']


@pytest.mark.parametrize('claimed',['queued','running'])
def test_actual_worker_process_exit_without_result_persists_failure_and_never_restarts(tmp_path,monkeypatch,claimed):
    """A controlled real child dies; no model and no AutoCAD is launched."""
    packet,home=setup_packet(tmp_path);processes=[]
    script=tmp_path/'controlled-exit.py'
    script.write_text('''import os,sys,time
from pathlib import Path
sys.path.insert(0,'''+repr(str(ROOT/'src'))+''')
from luomu_cad import review_jobs as jobs
base=Path(sys.argv[2]);store=jobs._store(base)
if '''+repr(claimed)+'''=='running':
 with jobs._worker_lock(store.root):
  store.set('one',{'status':'running','worker_pid':os.getpid(),'worker_identity':jobs._process_state(os.getpid())})
time.sleep(.3)
os._exit(23)
''',encoding='utf8')
    def launch(job,base,nonce,log):
        child=subprocess.Popen([sys.executable,str(script),str(job),str(base)],stdin=subprocess.DEVNULL,
            stdout=log,stderr=log,**({'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}))
        processes.append(child);return child
    monkeypatch.setattr(jobs,'_launch',launch)
    jobs.start('one',packet,tmp_path/'out',home,base=tmp_path)
    assert processes[0].wait(timeout=10)==23
    observed=jobs._process_state(processes[0].pid)
    assert observed['state']=='exited',observed
    result=jobs.status('one',base=tmp_path)
    assert result['status']=='failed' and 'EXITED_WITHOUT_COMPLETION' in result['error'],result
    assert result['orphaned_worker']['previous_status']==claimed
    assert not result['orphaned_worker']['host_termination_cause_proven']
    assert not result['accepted_for_delivery'] and not result['independent_review_ready']
    stored=jobs._store(tmp_path).get('one')
    assert stored['status']=='failed' and stored['finished_at']
    assert not (tmp_path/'out/runner-result.json').exists()
    repeated=jobs.start('one',packet,tmp_path/'out',home,base=tmp_path)
    assert repeated['status']=='failed' and len(processes)==1


def test_process_identity_self_is_alive_and_invalid_pid_is_unknown():
    current=jobs._process_state(os.getpid())
    assert current['state']=='alive' and current['creation_id'],current
    assert jobs._process_state(-1)['state']=='unknown'


def test_pid_reuse_is_failure_not_an_unrelated_process_to_wait_or_kill(tmp_path,monkeypatch):
    packet,home=setup_packet(tmp_path);calls=hold_launch(monkeypatch)
    jobs.start('one',packet,tmp_path/'out',home,base=tmp_path)
    store=jobs._store(tmp_path)
    store.set('one',{'status':'running','worker_identity':{'state':'alive','creation_id':'original'}})
    monkeypatch.setattr(jobs,'_process_state',lambda pid:{'state':'alive','pid':pid,'creation_id':'reused'})
    result=jobs.status('one',base=tmp_path)
    assert result['status']=='failed' and 'PID_REUSED' in result['error']
    assert len(calls)==1 and not result['accepted_for_delivery']


def test_unknown_liveness_and_legacy_live_pid_never_claim_success(tmp_path,monkeypatch):
    packet,home=setup_packet(tmp_path);hold_launch(monkeypatch)
    jobs.start('one',packet,tmp_path/'out',home,base=tmp_path)
    monkeypatch.setattr(jobs,'_process_state',lambda pid:{'state':'unknown','pid':pid,'query_error':5})
    assert jobs.status('one',base=tmp_path)['status']=='queued'
    monkeypatch.setattr(jobs,'_process_state',lambda pid:{'state':'alive','pid':pid,'creation_id':'current-but-no-old-id'})
    result=jobs.status('one',base=tmp_path)
    assert result['status']=='queued' and not result['independent_review_ready']
