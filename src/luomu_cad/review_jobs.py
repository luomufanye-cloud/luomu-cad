"""Durable, at-most-once launches of the fixed isolated reviewer.

No packet selects an executable, model, home, permission or authorization root.
Ready means review evidence is available, never delivery acceptance.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from .storage import ROOT, Journal, digest, inside, now, workspace_lock


def _hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _exclusive(path, value):
    with path.open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def _base(base):
    result = Path(ROOT if base is None else base).resolve(strict=True)
    if not result.is_dir():
        raise ValueError('Explicit authorized base must be an existing directory')
    return result


def _store(base):
    return Journal(inside('runtime/review-jobs', base))


def _process_state(pid):
    """Read-only worker identity/liveness. Unknown permission errors stay unknown.

    A PID is never evidence of successful review. Creation time distinguishes a
    reused PID; no kill, breakaway, elevation, process launch or CAD query occurs.
    """
    if type(pid) is not int or pid <= 0:
        return {'state':'unknown','reason':'invalid worker PID'}
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE,*([ctypes.POINTER(wintypes.FILETIME)]*4)]
        kernel.GetProcessTimes.restype = wintypes.BOOL
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE,wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x1000 | 0x100000,False,pid)  # QUERY_LIMITED_INFORMATION | SYNCHRONIZE
        if not handle:
            error = ctypes.get_last_error()
            return {'state':'exited' if error == 87 else 'unknown','query_error':error,'pid':pid}
        try:
            created,exited,kernel_time,user_time = (wintypes.FILETIME() for _ in range(4))
            if not kernel.GetProcessTimes(handle,ctypes.byref(created),ctypes.byref(exited),
                                          ctypes.byref(kernel_time),ctypes.byref(user_time)):
                return {'state':'unknown','query_error':ctypes.get_last_error(),'pid':pid}
            identity = str((created.dwHighDateTime << 32) | created.dwLowDateTime)
            wait = kernel.WaitForSingleObject(handle,0)
            return {'state':{0:'exited',258:'alive'}.get(wait,'unknown'),
                    'pid':pid,'creation_id':identity,'identity_source':'windows_process_creation_filetime'}
        finally:
            kernel.CloseHandle(handle)
    proc = Path('/proc')/str(pid)/'stat'
    try:
        fields = proc.read_text().rsplit(')',1)[1].split()
        return {'state':'exited' if fields[0] in {'Z','X'} else 'alive','pid':pid,
                'creation_id':fields[19],'identity_source':'proc_starttime_ticks'}
    except FileNotFoundError:
        if Path('/proc').is_dir():
            return {'state':'exited','pid':pid}
    except (OSError,IndexError):
        pass
    # Without an identity-bearing /proc API, existence alone cannot disprove PID
    # reuse. Even a live PID remains diagnostic, never success.
    try:
        os.kill(pid,0)
    except ProcessLookupError:
        return {'state':'exited','pid':pid}
    except OSError:
        pass
    return {'state':'unknown','pid':pid,'reason':'process identity unavailable'}


def _orphan_state(store, operation_id, row):
    if row.get('status') not in {'queued','running'} or type(row.get('worker_pid')) is not int:
        return row
    observed = _process_state(row['worker_pid'])
    recorded = row.get('worker_identity', {})
    reused = (observed.get('state') == 'alive' and recorded.get('creation_id') is not None
              and observed.get('creation_id') is not None
              and observed['creation_id'] != recorded['creation_id'])
    if observed.get('state') != 'exited' and not reused:
        return row
    failure = {'status':'failed','finished_at':now(),
               'error':('REVIEW_WORKER_PID_REUSED' if reused else 'REVIEW_WORKER_EXITED_WITHOUT_COMPLETION')+
                       ': worker exited or host terminated it before a bound completion receipt; no automatic relaunch',
               'orphaned_worker':{'previous_status':row['status'],'observed':observed,
                                  'recorded_identity':recorded,'host_termination_cause_proven':False},
               'accepted_for_delivery':False,'independent_review_ready':False}
    try:
        with workspace_lock(store.root):
            latest = store.get(operation_id)
            # It may have committed a genuine result while we inspected its PID.
            if (latest.get('status') in {'queued','running'} and latest.get('nonce') == row.get('nonce')
                    and latest.get('worker_pid') == row.get('worker_pid')
                    and latest.get('worker_identity') == row.get('worker_identity')):
                store.set(operation_id, failure)
                return store.get(operation_id)
            return latest
    except RuntimeError:
        # E.g. replay queried from start's already-held lock. Report failure now;
        # the next ordinary status call persists it, without waiting or replaying.
        return {**row,**failure,'orphan_state_persistence':'workspace_busy_retry_status'}


@contextmanager
def _worker_lock(root):
    # The parent holds the lock while recording the just-created worker PID.
    # A fast child must wait for that tiny critical section, not silently exit.
    deadline = time.monotonic()+30
    while True:
        manager = workspace_lock(root)
        try:
            manager.__enter__()
            break
        except RuntimeError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(.05)
    try:
        yield
    finally:
        manager.__exit__(None, None, None)


def _snapshot(packet_path):
    from .review_runner import _prepare
    packet_path, _, _, _, _, tracked = _prepare(packet_path)
    return {str(path): sha for path, sha in tracked.items()}


def _same_inputs(request, base):
    for name in ('packet_path', 'output', 'project_root'):
        path = Path(request[name])
        if inside(path, base) != path:
            raise ValueError('AUTHORIZED_PATH_CHANGED: '+name)
    if _snapshot(request['packet_path']) != request['inputs']:
        raise ValueError('REVIEW_JOB_INPUT_CHANGED: original packet or source bytes changed')


def _launch(job_path, base, nonce, log):
    """Only this installed fixed worker is executable; no executor input exists."""
    package_parent = Path(__file__).resolve().parents[1]
    bundle = package_parent.parent if package_parent.name == 'src' else package_parent
    script = bundle/'scripts/review_job_worker.py'
    if not script.is_file():
        raise ValueError('Installed fixed review_job_worker.py is unavailable')
    kwargs = dict(stdin=subprocess.DEVNULL, stdout=log, stderr=log, cwd=str(base),
                  close_fds=True, env=dict(os.environ, PYTHONUTF8='1'))
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        kwargs['startupinfo'] = startup
    else:
        kwargs['start_new_session'] = True
    return subprocess.Popen([sys.executable, str(script), '--job', str(job_path),
                             '--base', str(base), '--nonce', nonce], **kwargs)


def start(operation_id, packet_path, output, codex_home, project_root=None,
          timeout_seconds=600, *, base=None):
    """Launch once; identical repeats query state even after an uncertain launch.

    base is a trusted server configuration value, NOT an untrusted tool/packet
    option. codex_home must be explicitly supplied by caller/server environment.
    """
    base = _base(base)
    store = _store(base)
    job_path = store.path(operation_id)
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 1 <= timeout_seconds <= 3600):
        raise ValueError('timeout_seconds must be a finite number between 1 and 3600')
    packet_path = inside(packet_path, base)
    output = inside(output, base)
    project = inside(project_root if project_root is not None else packet_path.parent, base)
    home = Path(codex_home).resolve(strict=True)
    if not home.is_dir() or not project.is_dir():
        raise ValueError('Explicit existing Codex home and project directory required')
    request = {'packet_path':str(packet_path), 'output':str(output),
               'codex_home':str(home), 'project_root':str(project),
               'timeout_seconds':timeout_seconds, 'inputs':_snapshot(packet_path)}
    if (output.is_relative_to(store.root) or store.root.is_relative_to(output)
            or any(Path(p).is_relative_to(output) for p in request['inputs'])
            or home.is_relative_to(output) or output.is_relative_to(home)):
        raise ValueError('Review output must not contain inputs, Codex home or job state')
    with workspace_lock(store.root):
        old = store.get(operation_id)
        if old is not None:
            if old['request_hash'] != digest(request):
                raise ValueError('JOB_CONFLICT: operation_id already binds different inputs/options')
            return status(operation_id, base=base)
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise ValueError('Review output must be new or empty; no overwrite')
        # Reserve outputs outside the runner directory, which must remain empty.
        for other in store.root.glob('*.json'):
            row = _load(other)
            reserved = Path(row['request']['output'])
            if output.is_relative_to(reserved) or reserved.is_relative_to(output):
                raise ValueError('OUTPUT_RESERVED: another operation owns an overlapping output')
        nonce = uuid.uuid4().hex
        store.set(operation_id, {'schema_version':1, 'operation_id':operation_id,
                  'request_hash':digest(request), 'request':request, 'nonce':nonce,
                  'status':'queued', 'created_at':now(), 'accepted_for_delivery':False,
                  'independent_review_ready':False})
        try:
            with (store.root/(operation_id+'.worker.log')).open('xb') as log:
                process = _launch(job_path, base, nonce, log)
            # Worker claims under the same lock; it cannot race this update.
            store.set(operation_id, {'worker_pid':process.pid,'worker_identity':_process_state(process.pid)})
        except Exception as exc:
            store.set(operation_id, {'status':'launch_failed', 'error':str(exc)})
    return status(operation_id, base=base)


def _verify_result(request, result, base):
    """Verify result bytes and all run artifacts, never discover success by PID."""
    _same_inputs(request, base)
    output = Path(request['output'])
    runner_path = inside('runner-result.json', output)
    if _load(runner_path) != result:
        raise ValueError('RUNNER_RESULT_MISMATCH')
    if (result.get('execution_mode') != 'isolated_cli_reviewer'
            or result.get('accepted_for_delivery') is not False):
        raise ValueError('INVALID_RUNNER_RESULT_IDENTITY')
    for name, record in result.get('artifacts', {}).items():
        path = inside(record['path'], output)
        if path.name != name or _hash(path) != record['sha256']:
            raise ValueError('RUNNER_ARTIFACT_CHANGED: '+name)
    if result.get('independent_review_ready') is not True:
        return False
    execution = result.get('execution', {})
    if (execution.get('exit_code') != 0 or execution.get('timed_out') is not False
            or execution.get('model_output_observed') is not True
            or len(execution.get('session_ids', [])) != 1
            or execution.get('successful_evidence_reads', 0) < 1):
        raise ValueError('INCOMPLETE_NATIVE_MODEL_EXECUTION')
    required = {'independent-review.json','events.jsonl','evidence-lock.json','launch-manifest.json',
                'input-inventory.json','evidence-access.jsonl','reviewer-result.json'}
    if not required.issubset(result.get('artifacts', {})):
        raise ValueError('REQUIRED_RUN_EVIDENCE_MISSING')
    lock = _load(output/'evidence-lock.json')
    if (lock.get('packet_path') != request['packet_path']
            or lock.get('packet_sha256') != request['inputs'][request['packet_path']]):
        raise ValueError('RUN_RESULT_PACKET_BINDING_MISMATCH')
    inventory = _load(output/'input-inventory.json')
    if inventory.get('packet') != request['packet_path']:
        raise ValueError('RUN_INPUT_INVENTORY_MISMATCH')
    record = result.get('independent_review', {})
    path = inside(record.get('path', ''), output)
    if path != output/'independent-review.json' or _hash(path) != record.get('sha256'):
        raise ValueError('INDEPENDENT_RESULT_CHANGED')
    packet = _load(request['packet_path'])
    review = _load(path)
    if (review.get('contract_id') != packet['contract_id']
            or review.get('customer_brief_sha256') != packet['customer_brief']['sha256']
            or review.get('artifact_sha256') != {a['id']:a['sha256'] for a in packet['artifacts']}
            or review.get('reviewer_id') != 'isolated-cli:'+execution['session_ids'][0]):
        raise ValueError('INDEPENDENT_RESULT_INPUT_BINDING_MISMATCH')
    return True


def status(operation_id, *, base=None):
    """Read durable state and recheck hashes; never start/restart any process."""
    base = _base(base)
    store = _store(base)
    row = store.get(operation_id)
    if row is None:
        raise ValueError('UNKNOWN_REVIEW_JOB')
    view = {key:row[key] for key in ('schema_version','operation_id','request_hash','status',
             'created_at','updated','worker_pid','worker_identity','started_at','finished_at','error',
             'orphaned_worker','orphan_state_persistence') if key in row}
    view.update(accepted_for_delivery=False, independent_review_ready=False,
                execution_mode='isolated_cli_reviewer', model_weights_trained=False)
    try:
        if digest(row['request']) != row['request_hash']:
            raise ValueError('JOB_REQUEST_CHANGED')
        _same_inputs(row['request'], base)
        row = _orphan_state(store, operation_id, row)
        view.update({key:row[key] for key in ('status','updated','finished_at','error','worker_identity',
                     'orphaned_worker','orphan_state_persistence') if key in row})
        if row['status'] in {'ready','failed'} and 'receipt' in row:
            receipt = inside(row['receipt']['path'], store.root)
            if _hash(receipt) != row['receipt']['sha256']:
                raise ValueError('JOB_RECEIPT_CHANGED')
            binding = _load(receipt)
            if (binding.get('request_hash') != row['request_hash']
                    or binding.get('nonce') != row['nonce']):
                raise ValueError('JOB_RECEIPT_BINDING_MISMATCH')
            result_path = inside(binding['result_path'], Path(row['request']['output']))
            if result_path.name != 'runner-result.json' or _hash(result_path) != binding['result_sha256']:
                raise ValueError('JOB_RUNNER_RESULT_CHANGED')
            result = _load(result_path)
            ready = _verify_result(row['request'], result, base)
            if ready != (row['status'] == 'ready'):
                raise ValueError('JOB_RESULT_STATE_MISMATCH')
            view.update(independent_review_ready=ready, result={'path':str(result_path),
                        'sha256':binding['result_sha256']}, findings=result.get('findings', []))
            if ready:
                view['independent_review'] = result['independent_review']
                view['agent_verdict'] = result.get('agent_verdict')
        elif row['status'] == 'ready':
            raise ValueError('JOB_COMPLETION_RECEIPT_MISSING')
    except (ValueError, KeyError, TypeError, OSError) as exc:
        view.update(status='invalidated', independent_review_ready=False, error=str(exc))
    view['next_step'] = ('Run delivery.review with the original contract and this independent review'
                         if view['independent_review_ready'] else
                         'Inspect the preserved failure/logs; do not replay this operation or reuse its output'
                         if view['status'] in {'failed','launch_failed','invalidated'} else
                         'Query this operation again; keep the owning MCP session connected; never automatically relaunch')
    return view


def worker(job_path, base, nonce):
    """Fixed worker entry point. No arbitrary command or fixture mode is public."""
    base = _base(base)
    store = _store(base)
    path = inside(job_path, store.root)
    operation_id = path.stem
    if store.path(operation_id) != path:
        raise ValueError('INVALID_JOB_PATH')
    with _worker_lock(store.root):
        row = store.get(operation_id)
        if not row or row.get('nonce') != nonce or row.get('status') != 'queued':
            raise ValueError('JOB_NOT_QUEUED_OR_NONCE_MISMATCH: duplicate execution refused')
        if digest(row['request']) != row['request_hash']:
            raise ValueError('JOB_REQUEST_CHANGED')
        store.set(operation_id, {'status':'running','worker_pid':os.getpid(),
                                'worker_identity':_process_state(os.getpid()),'started_at':now()})
    request = row['request']
    terminal = {'status':'failed','finished_at':None}
    try:
        _same_inputs(request, base)
        output = Path(request['output'])
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise ValueError('OUTPUT_CHANGED_BEFORE_RUN: no existing file is overwritten')
        from .review_runner import run
        result = run(request['packet_path'], request['output'], request['codex_home'],
                     request['project_root'], request['timeout_seconds'])
        ready = _verify_result(request, result, base)
        receipt_path = store.root/(operation_id+'.receipt')
        _exclusive(receipt_path, {'request_hash':row['request_hash'],'nonce':nonce,
                   'result_path':str(output/'runner-result.json'),
                   'result_sha256':_hash(output/'runner-result.json')})
        terminal.update(status='ready' if ready else 'failed',
                        receipt={'path':str(receipt_path),'sha256':_hash(receipt_path)})
    except Exception as exc:
        terminal['error'] = str(exc)
    terminal['finished_at'] = now()
    with _worker_lock(store.root):
        store.set(operation_id, terminal)
    return status(operation_id, base=base)


def packet_from_contract(contract_path, packet_path, *, base=None, source_base=None, native_evidence=None):
    """Export original files/associations, never producer verdicts or old reports.

    Original brief bytes (including all expected values/checks) are unchanged.
    Packet must be beside the contract or in an authorized ancestor directory;
    this helper does not copy, rewrite or downgrade the customer deliverables.
    """
    from .delivery import _brief, _file
    from .industry import get_profile
    base = _base(base)
    contract_path = inside(contract_path, base)
    packet_path = inside(packet_path, base)
    contract = _load(contract_path)
    source_base = inside(source_base,base) if source_base is not None else contract_path.parent
    if not source_base.is_dir():
        raise ValueError('Original contract record base must be an existing authorized directory')
    if (not isinstance(contract, dict) or contract.get('schema_version') != 1
            or not isinstance(contract.get('contract_id'), str) or not contract['contract_id'].strip()
            or not isinstance(contract.get('producer_id'), str) or not contract['producer_id'].strip()):
        raise ValueError('Original contract identity and producer metadata required')
    brief_path, brief, original, requested, sheets = _brief(contract, source_base)
    profiles = {iid:get_profile(iid) for iid in brief['industries']}
    for sheet in sheets.values():
        if sheet['drawing_type'] not in {t['id'] for t in profiles[sheet['industry_id']]['drawing_types']}:
            raise ValueError('UNKNOWN_OR_CROSS_INDUSTRY_DRAWING_TYPE')

    def record(row, keys=()):
        path = _file(row, source_base)
        if not path.is_relative_to(packet_path.parent):
            raise ValueError('Packet directory must contain every original file; no copying or traversal')
        return {'path':str(path.relative_to(packet_path.parent)), 'sha256':row['sha256'],
                **{key:row[key] for key in keys}}

    artifacts = []
    seen = set()
    raw_artifacts = contract.get('artifacts')
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise ValueError('Original artifact inventory required')
    for item in raw_artifacts:
        if (not isinstance(item, dict) or not isinstance(item.get('id'), str)
                or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,63}', item['id']) or item['id'] in seen):
            raise ValueError('Duplicate or invalid artifact ID')
        seen.add(item['id'])
        sheet = sheets.get(item.get('sheet_id'))
        fmt = item.get('format')
        supported = fmt in {'dxf','pdf'} or (fmt == 'dwg' and isinstance(native_evidence,dict) and item['id'] in native_evidence)
        if not supported:
            raise ValueError('UNSUPPORTED_REVIEW_FORMAT: '+str(fmt)+'; do not substitute DXF for a required DWG/native format')
        if (sheet is None or fmt not in sheet['formats']
                or item.get('industry_id') != sheet['industry_id']
                or item.get('drawing_type') != sheet['drawing_type']
                or digest(item.get('expected')) != digest(sheet['expected'][fmt])):
            raise ValueError('Artifact differs from original sheet industry/format/expectations')
        # Industry/type/format were checked against the unchanged original brief.
        # Do not duplicate producer metadata beyond the runner's minimal schema.
        value = record(item, ('id','sheet_id'))
        if Path(value['path']).suffix.lower() != '.'+fmt:
            raise ValueError('Actual artifact format differs from its declared format')
        artifacts.append(value)
    if Counter((r['sheet_id'],Path(r['path']).suffix.lower().lstrip('.')) for r in artifacts) != Counter((s['sheet_id'],f) for s in sheets.values() for f in s['formats']):
        raise ValueError('Original full sheet/format inventory is missing or duplicated')
    by_id = {a['id']:a for a in raw_artifacts}
    for rid, requirement in original.items():
        associated = set(requirement.get('artifact_ids', []))
        for check in requirement['checks']:
            associated.update(check[k] for k in ('artifact_id','source_artifact_id') if k in check)
        if not associated or not associated.issubset(by_id):
            raise ValueError('Original requirement has missing or ambiguous artifact associations: '+rid)
        if any(by_id[aid]['industry_id'] != requirement['industry_id'] for aid in associated):
            raise ValueError('CROSS_INDUSTRY_REQUIREMENT_ARTIFACT: '+rid)
        if 'artifact_ids' in requested[rid] and set(requested[rid]['artifact_ids']) != associated:
            raise ValueError('Producer requirement artifact association differs from original checks')
    raw = [record(r) for r in brief.get('raw_sources', [])]
    if 'original_task' in brief:
        raw.insert(0, record(brief['original_task']))
    # Sources only, never standard review conclusions or producer interpretations.
    standards = []
    assignments = contract.get('standard_assignments', [])
    if not isinstance(assignments, list):
        raise ValueError('Standards assignments must be a list')
    for assignment in assignments:
        if (not isinstance(assignment, dict) or assignment.get('industry_id') not in profiles
                or assignment.get('standard_id') not in profiles[assignment['industry_id']]['standard_ids']):
            raise ValueError('UNKNOWN_OR_CROSS_INDUSTRY_STANDARD_SOURCE')
        if 'source_evidence' in assignment:
            standards.append(record(assignment['source_evidence']))
    packet = {'schema_version':1, 'contract_id':contract['contract_id'],
              'producer_id':contract['producer_id'], 'customer_brief':record(contract['customer_brief']),
              'artifacts':artifacts, 'raw_sources':raw, 'standard_sources':standards}
    if native_evidence is not None:
        if not isinstance(native_evidence, dict):
            raise ValueError('native_evidence must map DWG artifact IDs to bound original snapshots')
        bindings = {}
        for aid, evidence in native_evidence.items():
            if not isinstance(evidence, dict) or set(evidence) != {'snapshot','source_artifact_id'}:
                raise ValueError('Native evidence requires only snapshot and source_artifact_id')
            bindings[aid] = {'snapshot':record(evidence['snapshot']),
                             'source_artifact_id':evidence['source_artifact_id']}
        packet['native_evidence'] = bindings
        from . import review_runner
        validator = getattr(review_runner, 'validate_native_evidence', None)
        if validator is None:
            raise ValueError('NATIVE_REVIEW_READER_UNAVAILABLE: installed runner cannot validate original DWG evidence')
        validator(packet, packet_path.parent)
    if not packet_path.parent.is_dir():
        raise ValueError('Packet parent must be an existing authorized directory')
    # Exclusive create protects any previous packet/result. Original task remains untouched.
    _exclusive(packet_path, packet)
    _snapshot(packet_path)
    return {'packet':{'path':str(packet_path),'sha256':_hash(packet_path)},
            'contract':{'path':str(contract_path),'sha256':_hash(contract_path)},
            'accepted_for_delivery':False, 'independent_review_ready':False}
