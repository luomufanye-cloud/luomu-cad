"""Run a real isolated reviewer process and reject unaudited model claims.

The process is an independent CLI reviewer, not a claimed T3 UI/native spawn.
Its observations still require the ordinary delivery engine's actual-file checks.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import tomllib
import uuid

from .reviewer_install import AGENT_NAME, definitions


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path, value):
    with path.open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def native_codex():
    command = shutil.which('codex')
    if command is None:
        raise ValueError('CODEX_CLI_UNAVAILABLE: install/use a compatible existing Codex CLI')
    if os.name == 'nt' and Path(command).suffix.lower() in {'.cmd', '.ps1'}:
        package = Path(command).parent/'node_modules/@openai/codex'
        candidates = list(package.rglob('codex.exe')) if package.is_dir() else []
        if not candidates:
            raise ValueError('Native Codex executable unavailable; no shell-built fallback is used')
        return str(candidates[0])
    return command


def _configured_mcp_names(command, home, project):
    """Ask the native CLI for effective layered config, without starting any server."""
    response = subprocess.run([command,'-C',str(project),'mcp','list','--json'],
        env=dict(os.environ,CODEX_HOME=str(home)),cwd=project,stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
    if response.returncode:
        raise ValueError('EFFECTIVE_MCP_CONFIG_UNAVAILABLE: refusing offline review without disabling effective servers')
    try:
        rows=json.loads(response.stdout.decode('utf8'))
        if not isinstance(rows,list):raise ValueError()
        names=[r['name'] for r in rows]
        if any(not isinstance(name,str) or not re.fullmatch('[A-Za-z0-9_-]+',name) for name in names):raise ValueError()
        return sorted(set(names))
    except (ValueError,KeyError,TypeError):
        raise ValueError('EFFECTIVE_MCP_CONFIG_INVALID: no unsafe raw config is logged') from None


def _record(value, base):
    if not isinstance(value, dict) or not isinstance(value.get('path'), str) or not re.fullmatch('[a-f0-9]{64}', str(value.get('sha256', ''))):
        raise ValueError('Raw file records require a path and lowercase SHA256')
    path = (base/value['path']).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise ValueError('Input files must exist inside the packet directory')
    if _hash(path) != value['sha256']:
        raise ValueError('Source hash mismatch: '+value['path'])
    return path


def _requirement_artifacts(brief,packet,paths):
    """Derive only original source associations, including correspondence sources."""
    result={};available=set(paths)
    for row in brief['requirements']:
        required=set()
        if 'artifact_ids' in row:
            ids=row['artifact_ids']
            if not isinstance(ids,list) or not ids or any(not isinstance(a,str) for a in ids):
                raise ValueError('Original requirement artifact_ids must be explicit nonempty IDs')
            required.update(ids)
        checks=row.get('checks',[])
        if not isinstance(checks,list) or any(not isinstance(c,dict) for c in checks):
            raise ValueError('Original requirement checks must be objects')
        for check in checks:
            for key in ('artifact_id','source_artifact_id'):
                if key in check:
                    if not isinstance(check[key],str) or not check[key]:raise ValueError('Original check needs a valid artifact association')
                    required.add(check[key])
        if not required:
            if len(available)==1:required.update(available)
            else:raise ValueError('Original multi-artifact requirement must declare its artifact associations; no cross-industry guessing')
        if not required.issubset(available):raise ValueError('Original requirement refers to missing packet artifacts')
        result[row['id']]=sorted(required)
    return result


def _original_task(brief,packet,base):
    record=brief.get('original_task')
    if record is None:return None
    path=_record(record,base)
    sources=packet.get('raw_sources',[])
    if not sources or _record(sources[0],base)!=path or sources[0]['sha256']!=record['sha256']:
        raise ValueError('ORIGINAL_TASK_SOURCE_ZERO_REQUIRED: original task must be the same hash-locked raw source:0')
    return {'path':path,'sha256':record['sha256']}


def validate_native_evidence(packet,packet_base):
    """Validate bound Main-MCP reading evidence; JSON never becomes a live context.

    Public packet-factory hook. No packet file, CAD access, expected verdict or
    output mutation is required. All file dependencies are returned in tracked.
    """
    from .storage import digest
    base=Path(packet_base).resolve(strict=True)
    artifacts=packet.get('artifacts',[])
    if not isinstance(artifacts,list) or any(not isinstance(r,dict) for r in artifacts):raise ValueError('Native evidence needs an artifact inventory')
    by_id={r.get('id'):r for r in artifacts}
    if len(by_id)!=len(artifacts):raise ValueError('Duplicate native packet artifact IDs')
    paths={aid:_record(row,base) for aid,row in by_id.items()}
    native={aid for aid,path in paths.items() if path.suffix.lower()=='.dwg'}
    declared=packet.get('native_evidence',{})
    if not isinstance(declared,dict) or set(declared)!=native:
        raise ValueError('DWG_BOUND_NATIVE_EVIDENCE_REQUIRED: every actual DWG needs exactly one bound Main-MCP evidence record')
    result={};tracked={}
    for aid,binding in declared.items():
        if not isinstance(binding,dict) or set(binding)!={'snapshot','source_artifact_id'}:
            raise ValueError('Native evidence requires only snapshot record and original source_artifact_id')
        source_id=binding['source_artifact_id']
        if not isinstance(source_id,str) or source_id not in paths or paths[source_id].suffix.lower()!='.dxf':
            raise ValueError('Native evidence needs a separately declared original source DXF')
        if by_id[source_id].get('sheet_id')!=by_id[aid].get('sheet_id'):
            raise ValueError('Native evidence source must belong to the same original sheet')
        dwg=paths[aid];source=paths[source_id]
        if re.fullmatch(rb'AC10[0-9]{2}',dwg.read_bytes()[:6]) is None:
            raise ValueError('DWG_FORMAT_SIGNATURE_REQUIRED: do not substitute another format')
        sidecar=_record(binding['snapshot'],base)
        if sidecar.suffix.lower()!='.json':raise ValueError('Native snapshot must be hash-locked JSON')
        snapshot=json.loads(sidecar.read_text(encoding='utf-8-sig'))
        facts=snapshot.get('facts');fact_hash=snapshot.get('snapshot_sha256')
        dwg_hash=by_id[aid]['sha256'];source_hash=by_id[source_id]['sha256']
        if (not isinstance(facts,dict) or digest(facts)!=fact_hash or snapshot.get('ok') is not True
                or snapshot.get('stable_read_verified') is not True or snapshot.get('saved') is not True
                or type(snapshot.get('dbmod')) is not int or snapshot['dbmod']!=0
                or snapshot.get('settings_changed') is not False
                or Path(snapshot.get('path','')).resolve()!=dwg or snapshot.get('file_sha256')!=dwg_hash
                or not isinstance(snapshot.get('document_token'),str) or not snapshot['document_token']):
            raise ValueError('NATIVE_SNAPSHOT_BINDING_INVALID: complete stable clean raw capture required')
        provenance=snapshot.get('provenance',{})
        if (not isinstance(provenance,dict) or provenance.get('kind') not in {'save','save_as','open_document'}
                or not isinstance(provenance.get('operation_id'),str) or not provenance['operation_id']
                or Path(provenance.get('path','')).resolve()!=dwg or provenance.get('file_sha256')!=dwg_hash):
            raise ValueError('NATIVE_MAIN_MCP_LOAD_SAVE_PROVENANCE_REQUIRED')
        if (facts.get('complete') is not True or facts.get('unsupported_entities')!=[]
                or not isinstance(facts.get('model'),list) or not facts['model']
                or facts.get('modelspace_count')!=len(facts['model'])):
            raise ValueError('NATIVE_COMPLETE_SUPPORTED_FACTS_REQUIRED')
        from collections import Counter
        if facts.get('entity_counts')!=dict(Counter(r['ObjectName'] for r in facts['model'])):
            raise ValueError('Native model counts differ from actual raw inventory')
        preview=snapshot.get('correspondence_preview',{})
        if (not isinstance(preview,dict) or preview.get('kind')!='native_source_correspondence'
                or preview.get('native_export') is not False or preview.get('full_model_coverage_verified') is not True
                or preview.get('native_file_sha256')!=dwg_hash or preview.get('native_snapshot_sha256')!=fact_hash
                or preview.get('source_file_sha256')!=source_hash or Path(preview.get('source_path','')).resolve()!=source):
            raise ValueError('NATIVE_FULL_CORRESPONDENCE_PREVIEW_BINDING_REQUIRED')
        image=_record({'path':preview.get('path'),'sha256':preview.get('sha256')},base)
        from PIL import Image
        with Image.open(image) as bitmap:
            if bitmap.format!='PNG':raise ValueError('Native correspondence preview must be an actual PNG')
            bitmap.verify()
        import ezdxf
        from .native_correspondence import compare
        doc=ezdxf.readfile(source)
        compared=compare({'actual':facts},doc)
        if compared.get('passed') is not True or compared.get('differences'):
            raise ValueError('NATIVE_SOURCE_GEOMETRY_DIFFERENT: raw facts do not match the original source')
        result[aid]={'snapshot':snapshot,'snapshot_path':sidecar,'snapshot_file_sha256':binding['snapshot']['sha256'],
                     'source_artifact_id':source_id,'source_path':source,'preview_path':image,
                     'preview_sha256':preview['sha256'],'live_context_provided':False}
        tracked.update({dwg:dwg_hash,source:source_hash,sidecar:binding['snapshot']['sha256'],image:preview['sha256']})
    return {'bindings':result,'tracked':tracked}


def _prepare(packet_path):
    packet_path = Path(packet_path).resolve(strict=True)
    packet = json.loads(packet_path.read_text(encoding='utf-8-sig'))
    allowed = {'schema_version', 'contract_id', 'producer_id', 'customer_brief', 'artifacts', 'raw_sources', 'standard_sources','native_evidence'}
    if not isinstance(packet, dict) or set(packet)-allowed or packet.get('schema_version') != 1:
        raise ValueError('Use a raw reviewer packet; producer reports/verdicts are not accepted inputs')
    if not isinstance(packet.get('contract_id'), str) or not packet['contract_id'].strip():
        raise ValueError('contract_id is required')
    if 'producer_id' in packet and (not isinstance(packet['producer_id'],str) or not packet['producer_id'].strip()):
        raise ValueError('producer_id is optional provenance metadata, and must be nonempty when supplied')
    base = packet_path.parent
    brief_path = _record(packet.get('customer_brief'), base)
    brief = json.loads(brief_path.read_text(encoding='utf-8-sig'))
    requirements = brief.get('requirements')
    if not isinstance(requirements, list) or not requirements or any(not isinstance(r, dict) or not isinstance(r.get('id'), str) or not r['id'].strip() for r in requirements):
        raise ValueError('Original customer brief must contain the complete stable requirements list')
    requirement_ids = [r['id'] for r in requirements]
    if len(requirement_ids) != len(set(requirement_ids)):
        raise ValueError('Duplicate original requirement IDs')
    if brief.get('scope') not in {'reference_redraw', 'drawing_delivery', 'engineering_delivery'}:
        raise ValueError('Original customer brief needs an explicit delivery scope')
    sheets = brief.get('required_sheets')
    if not isinstance(sheets, list) or not sheets or any(not isinstance(r, dict) or not isinstance(r.get('sheet_id'), str) or not r['sheet_id'].strip() or not isinstance(r.get('formats'), list) or not r['formats'] or any(not isinstance(f, str) or not f.strip() for f in r['formats']) for r in sheets):
        raise ValueError('Original customer brief needs complete required_sheets and formats')
    if len({r['sheet_id'] for r in sheets}) != len(sheets):
        raise ValueError('Duplicate original required sheet IDs')
    if any(not isinstance(r.get('description'), str) or not r['description'].strip() for r in requirements):
        raise ValueError('Every original requirement needs its customer description')
    artifacts = packet.get('artifacts')
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError('Real delivery artifacts are required')
    ids = []
    tracked = {packet_path: _hash(packet_path), brief_path: packet['customer_brief']['sha256']}
    paths = {}
    for row in artifacts:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,63}', row['id']):
            raise ValueError('Artifact IDs need 1..64 ASCII letters/numbers/hyphens/underscores')
        ids.append(row['id'])
        path = _record(row, base)
        paths[row['id']] = path
        tracked[path] = row['sha256']
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate artifact IDs')
    from collections import Counter
    if any(path.suffix.lower() not in {'.dxf','.pdf','.dwg'} for path in paths.values()):
        raise ValueError('Reviewer supports DXF/PDF and explicitly bound native DWG evidence only; other formats need their native acceptance path')
    tracked.update(validate_native_evidence(packet,base)['tracked'])
    actual_sheets=Counter((r.get('sheet_id',paths[r['id']].stem),paths[r['id']].suffix.lower().lstrip('.')) for r in artifacts)
    if actual_sheets != Counter((sheet['sheet_id'],f.lower()) for sheet in sheets for f in sheet['formats']):
        raise ValueError('Raw artifacts do not cover the complete required sheet/format inventory')
    for name in ('raw_sources', 'standard_sources'):
        rows = packet.setdefault(name, [])
        if not isinstance(rows, list):
            raise ValueError(name+' must be a list')
        for row in rows:
            path = _record(row, base)
            tracked[path] = row['sha256']
    _requirement_artifacts(brief,packet,paths)
    _original_task(brief,packet,base)
    return packet_path, packet, brief, requirement_ids, paths, tracked


def inspect_packet(packet_path):
    """Read original bytes and native properties without adopting producer conclusions."""
    packet_path, packet, brief, _, paths, tracked = _prepare(packet_path)
    facts = {'schema_version': 1, 'inspection': 'luomu-cad-raw-readback',
             'packet_sha256': _hash(packet_path), 'brief': brief,
             'source_sha256': {str(path): value for path, value in tracked.items()}, 'artifacts': {}}
    for aid, path in paths.items():
        row = {'sha256': _hash(path), 'format': path.suffix.lower().lstrip('.')}
        if path.suffix.lower() == '.dxf':
            import ezdxf
            doc = ezdxf.readfile(path)
            entities = list(doc.modelspace())
            if len(entities) > 5000:
                raise ValueError('Raw DXF inspection workload exceeds 5000 entities; split the authorized review')
            row.update(units=doc.units, entities=[{'type': e.dxftype(), 'handle': e.dxf.handle,
                       'dxf': e.dxf.all_existing_dxf_attribs(),
                       **({'vertices_xyseb':[list(p) for p in e.get_points('xyseb')]} if e.dxftype()=='LWPOLYLINE' else {})} for e in entities],
                       layers=[layer.dxf.all_existing_dxf_attribs() for layer in doc.layers])
        elif path.suffix.lower() == '.pdf':
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(path)
            try:
                pages=[]
                for index in range(len(doc)):
                    page=doc[index];text=page.get_textpage()
                    pages.append({'page':index+1,'size_mm':[round(v*25.4/72,6) for v in page.get_size()],
                                  'text':text.get_text_range()})
                    text.close();page.close()
                row['pages']=pages
            finally:doc.close()
        facts['artifacts'][aid]=row
    # Vec3/Vec2 are raw native values; normalize deterministically for CLI JSON.
    return json.loads(json.dumps(facts, ensure_ascii=False, default=lambda v:list(v)))


def _inspection_command(bundle, packet_path):
    script = bundle/'scripts/run_review_agent.py'
    if not script.is_file():raise ValueError('Canonical packet inspection entry point unavailable')
    if os.name == 'nt':
        quote=lambda v:"'"+str(v).replace("'", "''")+"'"
        return '& '+quote(sys.executable)+' '+quote(script)+' --inspect-packet '+quote(packet_path)
    import shlex
    return shlex.join([sys.executable,str(script),'--inspect-packet',str(packet_path)])


def _inspection_event(item, command, expected):
    """Require the exact dedicated readback invocation, never arbitrary successful shell."""
    actual=item.get('command','')
    matched=actual == command
    if not matched and os.name == 'nt' and isinstance(actual,str):
        wrapper=re.fullmatch(r'(?:"[^"\r\n]*(?:pwsh|powershell)\.exe"|[^\s"\r\n]*(?:pwsh|powershell)(?:\.exe)?) (?:-NoProfile )?-Command (.+)', actual, re.IGNORECASE)
        if wrapper:
            body=wrapper.group(1)
            matched=body in {command,'"'+command+'"'}
    if not matched or item.get('type')!='command_execution' or item.get('exit_code')!=0:return False
    try:return json.loads(item.get('aggregated_output','')) == expected
    except (ValueError,TypeError):return False


def _evidence_lock(packet_path,previews,output,server_name):
    from .review_evidence_server import original_records
    records=original_records(packet_path)
    for index,row in enumerate(records):
        path=Path(row['path'])
        if row['category']=='artifact':row['previews']=previews[row['file_id'].split(':',1)[1]]
        elif path.suffix.lower() in {'.png','.jpg','.jpeg','.webp'}:
            row['previews']=[{'path':str(path),'sha256':row['sha256'],'source_sha256':row['sha256'],'page':1}]
        elif row['category']!='customer_brief' and path.suffix.lower() in {'.pdf','.dxf'}:
            row['previews']=_previews({'source-'+str(index):path},output)['source-'+str(index)]
        else:row['previews']=[]
    lock={'schema_version':1,'packet_path':str(packet_path),'packet_sha256':_hash(packet_path),
          'mcp_server_name':server_name,'files':records}
    target=output/'evidence-lock.json';_json(target,lock)
    return target,lock


def _mcp_evidence(rows,lock,output):
    """Match completed native MCP events to the dedicated service's actual read ledger."""
    from .review_evidence_server import encoded,TOOLS
    records={r['file_id']:r for r in lock['files']}
    audit_path=output/'evidence-access.jsonl'
    audit_rows=_events(audit_path) if audit_path.is_file() else []
    ledger={r.get('record_id'):r for r in audit_rows}
    if len(ledger)!=len(audit_rows):raise ValueError('EVIDENCE_AUDIT_DUPLICATE_RECORDS')
    reads=set();views=set();checked=[];seen=set();calls={}
    for event in rows:
        item=event.get('item',{})
        kind=item.get('type')
        if kind in {'collab_tool_call','command_execution','file_change','web_search'}:
            raise ValueError('UNEXPECTED_DELEGATION_OR_COMMAND: only the packet evidence MCP is authorized')
        if kind!='mcp_tool_call':continue
        if item.get('server')!=lock['mcp_server_name'] or item.get('tool') not in TOOLS:
            raise ValueError('UNEXPECTED_DELEGATION_OR_MCP: unknown evidence service or tool')
        if not isinstance(item.get('id'),str) or not item['id']:raise ValueError('EVIDENCE_NATIVE_CALL_ID_MISSING')
        call_id=item['id'];signature=encoded([item['server'],item['tool'],item.get('arguments',{})])
        previous=calls.get(call_id)
        if previous and (previous['completed'] or previous['signature']!=signature or event.get('type')=='item.started'):
            raise ValueError('EVIDENCE_NATIVE_CALL_ID_REUSED_OR_CHANGED')
        if event.get('type') not in {'item.started','item.updated','item.completed'}:
            raise ValueError('EVIDENCE_NATIVE_CALL_EVENT_INVALID')
        calls[call_id]={'signature':signature,'completed':event.get('type')=='item.completed'}
        if event.get('type')!='item.completed':continue
        if item.get('status')!='completed' or item.get('error'):
            raise ValueError('EVIDENCE_TOOL_REFUSED_OR_FAILED: no policy/permission retry is authorized')
        result=item.get('result')
        if not isinstance(result,dict) or result.get('isError'):
            raise ValueError('EVIDENCE_TOOL_RESULT_MISSING')
        blocks=result.get('content',[])
        values=[]
        for block in blocks:
            if block.get('type')=='text':
                try:values.append(json.loads(block.get('text','')))
                except ValueError:pass
        if len(values)!=1 or not isinstance(values[0],dict) or values[0].get('ok') is not True:
            raise ValueError('EVIDENCE_TOOL_FACTS_MISSING')
        response=values[0]
        if response.get('packet_sha256')!=lock['packet_sha256']:raise ValueError('EVIDENCE_PACKET_BINDING_MISMATCH')
        args=item.get('arguments',{})
        if item['tool']=='review_inventory':
            if args or response.get('files')!=[{'file_id':r['file_id'],'category':r['category'],'sha256':r['sha256'],
                  'format':Path(r['path']).suffix.lower().lstrip('.'),'preview_indices':list(range(len(r['previews'])))} for r in records.values()]:
                raise ValueError('EVIDENCE_INVENTORY_MISMATCH')
            continue
        fid=response.get('file_id');operation='read' if item['tool']=='review_read' else 'view'
        if fid not in records or response.get('source_sha256')!=records[fid]['sha256'] or response.get('operation')!=operation:
            raise ValueError('EVIDENCE_SOURCE_BINDING_MISMATCH')
        expected_args={'file_id':fid}
        if operation=='view':expected_args['preview_index']=response.get('preview',{}).get('index')
        if args!=expected_args:raise ValueError('EVIDENCE_ARGUMENT_BINDING_MISMATCH')
        rid=response.get('record_id')
        audit=ledger.get(rid)
        if rid in seen or not audit or audit.get('operation')!=operation or audit.get('file_id')!=fid or audit.get('source_sha256')!=records[fid]['sha256'] or audit.get('packet_sha256')!=lock['packet_sha256'] or audit.get('response_sha256')!=hashlib.sha256(encoded(response).encode('utf8')).hexdigest():
            raise ValueError('EVIDENCE_REAL_READ_RECORD_MISSING')
        seen.add(rid)
        if operation=='read':
            if 'facts' not in response:raise ValueError('EVIDENCE_NATIVE_FACTS_MISSING')
            reads.add(fid)
        else:
            preview=response.get('preview',{});index=preview.get('index')
            if type(index) is not int or not 0<=index<len(records[fid]['previews']):raise ValueError('EVIDENCE_PREVIEW_INDEX_INVALID')
            locked=records[fid]['previews'][index]
            if preview.get('sha256')!=locked['sha256'] or audit.get('preview')!=preview:
                raise ValueError('EVIDENCE_PREVIEW_BINDING_MISMATCH')
            import base64
            images=[b for b in blocks if b.get('type')=='image']
            if len(images)!=1:raise ValueError('EVIDENCE_ACTUAL_IMAGE_MISSING')
            if images[0].get('mimeType') not in {'image/png','image/jpeg','image/webp'}:raise ValueError('EVIDENCE_ACTUAL_IMAGE_MIME_INVALID')
            try:image_hash=hashlib.sha256(base64.b64decode(images[0]['data'],validate=True)).hexdigest()
            except (ValueError,KeyError):raise ValueError('EVIDENCE_ACTUAL_IMAGE_INVALID') from None
            if image_hash!=locked['sha256']:raise ValueError('EVIDENCE_ACTUAL_IMAGE_HASH_MISMATCH')
            views.add((fid,index))
        checked.append({'file_id':fid,'operation':operation,'record_id':rid})
    if any(not state['completed'] for state in calls.values()):raise ValueError('EVIDENCE_TOOL_CALL_NOT_COMPLETED')
    if reads!=set(records):raise ValueError('EVIDENCE_FILE_READ_COVERAGE_INCOMPLETE')
    required_views={(r['file_id'],index) for r in records.values() for index in range(len(r['previews']))}
    if views!=required_views:raise ValueError('EVIDENCE_IMAGE_COVERAGE_INCOMPLETE')
    return checked


def _stop_tree(process):
    """Terminate only this owned review process and its descendants."""
    if os.name == 'nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,timeout=10,check=False)
    else:
        import signal
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


def result_schema(requirement_ids, artifact_ids):
    observation = {'type': 'object', 'additionalProperties': False,
        'properties': {'artifact_id': {'type': 'string', 'enum': artifact_ids},
                       'locator': {'type': 'string'}, 'source_locator': {'type': 'string'},
                       'finding': {'type': 'string'}, 'preview_index': {'type': 'integer'}},
        'required': ['artifact_id', 'locator', 'source_locator', 'finding', 'preview_index']}
    requirement = {'type': 'object', 'additionalProperties': False,
        'properties': {'requirement_id': {'type': 'string', 'enum': requirement_ids},
                       'verdict': {'type': 'string', 'enum': ['accepted', 'rejected']},
                       'finding': {'type': 'string'}, 'observations': {'type': 'array', 'items': observation,
                           'description':'In each requirement independently include factual observations for EVERY associated artifact in requirement_artifact_ids, including native source_artifact_id in cross-format checks; another requirement cannot substitute.'}},
        'required': ['requirement_id', 'verdict', 'finding', 'observations']}
    return {'type': 'object', 'additionalProperties': False,
        'properties': {'accepted_for_delivery': {'type': 'boolean'},
                       'requirement_inventory_checked': {'type': 'boolean'},
                       'inventory_observation': {'type': 'string'},
                       'requirements': {'type': 'array', 'items': requirement},
                       'unresolved': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['accepted_for_delivery', 'requirement_inventory_checked', 'inventory_observation', 'requirements', 'unresolved']}


def _previews(paths, output):
    """Render original saved properties; no alternate linework or customer file edits."""
    previews = {}
    for key, path in paths.items():
        suffix = path.suffix.lower()
        rows = []
        if suffix == '.pdf':
            import pypdfium2 as pdfium
            document = pdfium.PdfDocument(path)
            try:
                if not 1 <= len(document) <= 200:
                    raise ValueError('PDF page count is outside the supported review workload')
                for index in range(len(document)):
                    page = document[index]
                    bitmap = page.render(scale=1.5)
                    target = output/(key+'-page-'+str(index+1)+'.png')
                    bitmap.to_pil().save(target)
                    bitmap.close();page.close()
                    rows.append({'path': str(target), 'sha256': _hash(target), 'source_sha256': _hash(path), 'page': index+1})
            finally:
                document.close()
        elif suffix == '.dxf':
            import matplotlib
            matplotlib.use('Agg')
            import ezdxf
            from ezdxf.addons.drawing.matplotlib import qsave
            doc = ezdxf.readfile(path)
            # The renderer otherwise follows IMAGE/underlay paths outside the
            # packet. External dependencies need a separately bound native path.
            external={'IMAGE','IMAGEDEF','PDFUNDERLAY','PDFDEFINITION','DGNUNDERLAY','DGNDEFINITION','DWFUNDERLAY','DWFDEFINITION','OLEFRAME','OLE2FRAME'}
            if any(e.dxftype() in external for e in doc.entitydb.values() if e.is_alive) or any(b.block.is_xref or b.block.is_xref_overlay for b in doc.blocks):
                raise ValueError('DXF_EXTERNAL_DEPENDENCY: offline preview cannot follow unbound image/underlay/xref paths')
            target = output/(key+'-native.png')
            qsave(doc.modelspace(), str(target), dpi=120, bg='#ffffff')
            rows.append({'path': str(target), 'sha256': _hash(target), 'source_sha256': _hash(path), 'page': 1})
        previews[key] = rows
    return previews


def _events(path):
    rows = []
    for line in path.read_text(encoding='utf8', errors='replace').splitlines():
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except ValueError:
            pass
    return rows


def _validate_result(value, requirement_ids, artifact_ids, required_artifacts):
    if not isinstance(value, dict) or set(value) != {'accepted_for_delivery', 'requirement_inventory_checked', 'inventory_observation', 'requirements', 'unresolved'}:
        raise ValueError('Missing or unexpected structured reviewer fields')
    if type(value['accepted_for_delivery']) is not bool or value['requirement_inventory_checked'] is not True:
        raise ValueError('Reviewer did not check original requirement inventory')
    if not isinstance(value['inventory_observation'], str) or len(value['inventory_observation'].strip()) < 8:
        raise ValueError('Concrete inventory observation required')
    rows = value['requirements']
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError('Per-requirement review list required')
    ids = [r.get('requirement_id') for r in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(requirement_ids):
        raise ValueError('Independent review changed or omitted original requirement inventory')
    for row in rows:
        if row.get('verdict') not in {'accepted', 'rejected'} or not isinstance(row.get('finding'), str) or len(row['finding'].strip()) < 8:
            raise ValueError('Each requirement needs a concrete finding and verdict')
        observations = row.get('observations')
        if not isinstance(observations, list) or (row['verdict'] == 'accepted' and not observations):
            raise ValueError('Accepted requirements need artifact observations')
        for observation in observations:
            if observation.get('artifact_id') not in artifact_ids or any(not isinstance(observation.get(key), str) or len(observation[key].strip()) < 3 for key in ('locator','source_locator','finding')):
                raise ValueError('Observation must identify a real artifact and concrete source/file locations')
            if type(observation.get('preview_index')) is not int or observation['preview_index'] < 0:
                raise ValueError('Invalid observation preview index')
        if {o['artifact_id'] for o in observations} != set(required_artifacts[row['requirement_id']]):
            raise ValueError('INDEPENDENT_REQUIREMENT_ARTIFACT_COVERAGE_INCOMPLETE: '+row['requirement_id'])
    if not isinstance(value['unresolved'], list) or any(not isinstance(s, str) or not s.strip() for s in value['unresolved']):
        raise ValueError('Unresolved findings must be a list')
    if value['accepted_for_delivery'] and (value['unresolved'] or any(r['verdict'] != 'accepted' for r in rows)):
        raise ValueError('Reviewer acceptance contradicts unresolved or rejected requirements')


def run(packet_path, output, codex_home, project_root=None, timeout_seconds=240, *, bundle_root=None):
    """Start an isolated reviewer process; no model/provider/authentication selection."""
    if type(timeout_seconds) not in (int, float) or not 1 <= timeout_seconds <= 3600:
        raise ValueError('timeout_seconds must be between 1 and 3600')
    packet_path, packet, brief, requirements, paths, tracked = _prepare(packet_path)
    required_artifacts=_requirement_artifacts(brief,packet,paths)
    home = Path(codex_home).resolve(strict=True)
    project = Path(project_root or packet_path.parent).resolve(strict=True)
    if not home.is_dir() or not project.is_dir():
        raise ValueError('Explicit existing Codex home and project directory required')
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Reviewer output must be new or empty; no overwrite')
    if any(path.is_relative_to(output) for path in tracked):
        raise ValueError('Reviewer output cannot contain raw input files')
    command = native_codex()
    bundle = Path(bundle_root).resolve(strict=True) if bundle_root else Path(__file__).resolve().parents[2]
    if not (bundle/'agents/luomu-cad-reviewer.md').is_file():
        # Market packages place luomu_cad beside agents rather than below src.
        bundle = Path(__file__).resolve().parents[1]
    role = tomllib.loads(definitions(bundle, project, absolute_resources=True)['codex'].decode('utf8'))
    cfg_path = home/'config.toml'
    cfg = tomllib.loads(cfg_path.read_text(encoding='utf8')) if cfg_path.is_file() else {}
    config_hash = _hash(cfg_path) if cfg_path.is_file() else None
    mcp_names = _configured_mcp_names(command,home,project)
    output.mkdir(parents=True, exist_ok=True)
    result = {'schema_version': 1, 'execution_mode': 'isolated_cli_reviewer', 'role': AGENT_NAME,
              'accepted_for_delivery': False, 'independent_review_ready': False,
              'agent_verdict': None, 'findings': [], 'model_weights_trained': False,
              'reviewer_identity_authenticated': False, 'native_spawn_claimed': False}
    try:
        previews = _previews(paths, output)
        native=validate_native_evidence(packet,packet_path.parent)['bindings']
        for aid,binding in native.items():
            source=binding['preview_path'];target=output/(aid+'-bound-native-full.png')
            raw=source.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=binding['preview_sha256']:raise ValueError('Native full preview changed before attachment')
            with target.open('xb') as stream:stream.write(raw)
            previews[aid]=[{'path':str(target),'sha256':binding['preview_sha256'],'source_sha256':packet['artifacts'][next(i for i,r in enumerate(packet['artifacts']) if r['id']==aid)]['sha256'],
                           'page':1,'kind':'native_source_correspondence','native_export':False,'native_paper_plot':False}]
        schema = output/'review-schema.json';_json(schema, result_schema(requirements, list(paths)))
        inputs = {'packet': str(packet_path), 'customer_brief': str((packet_path.parent/packet['customer_brief']['path']).resolve()),
                  'artifacts': {key:str(path) for key,path in paths.items()}, 'previews': previews,
                  'raw_source_files': [str((packet_path.parent/r['path']).resolve()) for r in packet['raw_sources']],
                  'standard_source_files': [str((packet_path.parent/r['path']).resolve()) for r in packet['standard_sources']]}
        server_name='luomu-review-evidence-'+uuid.uuid4().hex[:12]
        lock_path,lock=_evidence_lock(packet_path,previews,output,server_name)
        inputs['evidence_mcp_server']=server_name
        inputs['producer_id']=packet.get('producer_id')
        inputs['producer_identity_authenticated']=False
        inputs['review_process_provenance']={'role':AGENT_NAME,'execution_mode':'isolated_cli_reviewer',
            'session_id_source':'Controller binds the actual native thread.started event after completion',
            'identity_authenticated':False}
        inputs['requirement_artifact_ids']=required_artifacts
        inputs['native_artifacts']={aid:{'readback_mode':'main_mcp_bound_native_facts',
            'offline_dwg_parsed':False,'live_context_provided':False,'live_final_revalidation_required':True,
            'preview_kind':'native_source_correspondence','native_paper_plot_verified':False} for aid in native}
        inputs['authorized_files']=[{'file_id':r['file_id'],'category':r['category'],
            'sha256':r['sha256'],'preview_indices':list(range(len(r['previews'])))} for r in lock['files']]
        _json(output/'input-inventory.json', inputs)
        instruction = role['developer_instructions']+'\n本次是独立离线验收进程，不是等待其他代理。角色指令已经完整装载，无需另读Skill文件。必须仅使用本次evidence_mcp_server中的review_inventory/review_read/review_view亲自检查；每个authorized file必须review_read，所有preview index必须review_view。禁止任何shell/exec_command、spawn/wait、其他MCP、AutoCAD/COM/GUI、网络或修改文件。任何工具/审批拒绝时保留失败，不换路径绕过。不得读producer report、旧验收结论或指定原件以外资料。每个accepted项须有原始实际图元事实和实际图像依据；事实MCP只给事实不提供通过结论。'
        prompt = '现在立即调用指定只读证据MCP。先review_inventory，然后为每个authorized_files.file_id调用review_read，并为所有preview_indices调用review_view；不需要也不允许任何命令。实际独立核对客户原始需求、原生DXF属性/顶点/尺寸、PDF纸面尺寸及真实图面；标准只采用原始提供依据，不臆造。只检查本次文件ID，不读取目录里其他报告/contract。需求ID必须与原始任务书一致。requirement_artifact_ids仅从原任务checks的artifact_id/source_artifact_id关联派生：每条需求必须分别为其每个应检artifact写有实际定位和事实的observation，PDF对应检查中的原生源也必须单独记录；另一条需求里已有该artifact的观察不能替代，不能仅列ID或复制通过结论。观察和结论仍需你独立判断，缺证据拒绝。最后按给定schema返回完整逐项结果，不输出绘图或修改脚本。\n'+json.dumps(inputs,ensure_ascii=False)
        (output/'request.txt').write_text(prompt,encoding='utf8')
        args = [command, '-c', 'developer_instructions='+json.dumps(instruction,ensure_ascii=False),
                '-c','features.shell_tool=false','-c','features.unified_exec=false',
                '-c','features.view_image=false','-c','features.image_generation=false',
                '-c','web_search="disabled"']
        if native:
            # Evidence visibility budget only; no model/provider/permissions or
            # acceptance threshold changes. Full R2 native facts are ~50k chars.
            args += ['-c','tool_output_token_limit=50000']
        for name in mcp_names:
            args += ['-c', 'mcp_servers.'+name+'.enabled=false']
        server_script=bundle/'scripts/review_evidence_server.py'
        if not server_script.is_file():raise ValueError('Dedicated read-only evidence MCP entry point unavailable')
        args += ['-c','mcp_servers.'+server_name+'.command='+json.dumps(sys.executable),
                 '-c','mcp_servers.'+server_name+'.args='+json.dumps([str(server_script),'--packet',str(packet_path),'--lock',str(lock_path),'--output',str(output)]),
                 '-c','mcp_servers.'+server_name+'.enabled=true',
                 '-c','mcp_servers.'+server_name+'.startup_timeout_sec=30',
                 '-c','mcp_servers.'+server_name+'.tool_timeout_sec=60']
        final = output/'reviewer-result.json'
        args += ['-a','never','exec','-s','read-only','--ephemeral','--skip-git-repo-check','--json',
                 '--output-schema',str(schema),'--output-last-message',str(final),'-C',str(project)]
        image_inputs=[p for r in lock['files'] for p in r['previews']]
        if len(image_inputs)>32:raise ValueError('Review image workload exceeds32; split the authorized review')
        for row in image_inputs:args += ['-i',row['path']]
        # --image accepts one-or-more values; stop option parsing so the final
        # customer prompt cannot be swallowed as another image filename.
        args += ['--',prompt]
        _json(output/'launch-manifest.json', {'execution_mode':'isolated_cli_reviewer',
             'arguments':args,'images_attached':image_inputs,
             'disabled_effective_mcp_servers':mcp_names,
             'only_authorized_mcp_server':server_name,
             'mcp_config_source':'native codex -C <project> mcp list --json; server transports/auth are not logged',
             'inspection_transport':'packet-scoped-readonly-stdio-mcp',
             'evidence_lock_sha256':_hash(lock_path),
             'canonical_role_sha256':hashlib.sha256(instruction.encode('utf8')).hexdigest()})
        started = time.monotonic()
        timed_out = False
        started_at = datetime.now(timezone.utc).isoformat()
        environment = dict(os.environ, CODEX_HOME=str(home), PYTHONUTF8='1')
        # A new review process must not inherit the invoking tool's thread identity.
        # These are execution correlation IDs, not authentication or provider settings.
        for name in ('CODEX_THREAD_ID', 'CODEX_SESSION_ID', 'CODEX_TOOL_CALL_ID'):
            environment.pop(name, None)
        with (output/'events.jsonl').open('xb') as stdout, (output/'stderr.txt').open('xb') as stderr:
            process = subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,
                                       env=environment,cwd=project, **({'start_new_session':True} if os.name!='nt' else {}))
            result['process_id'] = process.pid
            try:
                exit_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True;_stop_tree(process);exit_code=process.returncode
        rows = _events(output/'events.jsonl')
        sessions = [r.get('thread_id') for r in rows if r.get('type') == 'thread.started' and r.get('thread_id')]
        completed = [r.get('item',{}) for r in rows if r.get('type') == 'item.completed']
        result['execution'] = {'started_at':started_at,'elapsed_seconds':round(time.monotonic()-started,3),
            'timeout_seconds':timeout_seconds,'timed_out':timed_out,'exit_code':exit_code,'session_ids':sessions,
            'successful_check_commands':0,'successful_evidence_reads':0,
            'inspection_transport':'packet-scoped-readonly-stdio-mcp','model':cfg.get('model'),'model_provider_changed':False,
            'authentication_changed_by_runner':False,
            'model_output_observed':any(r.get('type')=='agent_message' for r in completed)}
        if timed_out:raise ValueError('REVIEWER_TIMEOUT: incomplete independent execution')
        if exit_code != 0:raise ValueError('REVIEWER_PROCESS_FAILED: inspect the recorded native events and stderr')
        if len(sessions) != 1:raise ValueError('REVIEWER_SESSION_NOT_OBSERVED')
        stderr_text=(output/'stderr.txt').read_text(encoding='utf8',errors='replace')
        if re.search(r'(?:rejected.*blocked by policy|approval (?:was )?(?:denied|rejected)|auto.review.*reject)',stderr_text,re.IGNORECASE):
            raise ValueError('REVIEWER_HOST_POLICY_REFUSAL: existing host policy remains enforced')
        if any(r.get('type')=='turn.failed' for r in rows):raise ValueError('REVIEWER_MODEL_TURN_FAILED')
        checked=_mcp_evidence(rows,lock,output)
        result['execution']['successful_evidence_reads']=len(checked)
        result['execution']['evidence_checks']=checked
        if not result['execution']['model_output_observed']:raise ValueError('REVIEWER_MODEL_RESULT_EVENT_MISSING')
        if not any(r.get('type')=='turn.completed' for r in rows):raise ValueError('REVIEWER_TURN_NOT_COMPLETED')
        if not final.is_file():raise ValueError('REVIEWER_RESULT_MISSING')
        value = json.loads(final.read_text(encoding='utf8'))
        messages=[]
        for item in completed:
            if item.get('type')=='agent_message':
                try:messages.append(json.loads(item.get('text','')))
                except ValueError:pass
        if value not in messages:raise ValueError('REVIEWER_FINAL_NOT_BOUND_TO_MODEL_EVENT')
        _validate_result(value, requirements, set(paths),required_artifacts)
        if any(_hash(path) != expected for path,expected in tracked.items()):
            raise ValueError('RAW_INPUT_CHANGED_DURING_REVIEW')
        if (_hash(cfg_path) if cfg_path.is_file() else None) != config_hash:
            raise ValueError('HOST_CONFIG_CHANGED_DURING_REVIEW: inspect concurrent host edits')
        if not value['accepted_for_delivery'] and not value['unresolved'] and all(r['verdict']=='accepted' for r in value['requirements']):
            value['unresolved'].append('Independent reviewer rejected the overall delivery; no overall acceptance was granted.')
        independent = {'schema_version':1,'contract_id':packet['contract_id'],'scope':brief['scope'],
            'reviewer_id':'isolated-cli:'+sessions[0], 'customer_brief_sha256':packet['customer_brief']['sha256'],
            'artifact_sha256':{r['id']:r['sha256'] for r in packet['artifacts']},
            'requirement_inventory_checked':value['requirement_inventory_checked'],
            'inventory_observation':value['inventory_observation'], 'unresolved':value['unresolved'],
            'requirements':value['requirements'], 'execution_mode':'isolated_cli_reviewer'}
        original_task=_original_task(brief,packet,packet_path.parent)
        if original_task is not None:
            if not any(r['file_id']=='source:0' and r['operation']=='read' for r in checked):
                raise ValueError('ORIGINAL_TASK_ACTUAL_READ_REQUIRED')
            independent['original_task_sha256']=original_task['sha256']
        for row in independent['requirements']:
            for observation in row['observations']:
                aid=observation['artifact_id'];observation['artifact_sha256']=independent['artifact_sha256'][aid]
                index=observation.pop('preview_index')
                if paths[aid].suffix.lower() in {'.pdf','.dxf','.dwg'}:
                    if index >= len(previews[aid]):raise ValueError('REVIEWER_PREVIEW_INDEX_INVALID')
                    observation['preview']={k:v for k,v in previews[aid][index].items() if k in {'path','sha256'}}
        if native:
            independent['native_evidence_sha256']={aid:b['snapshot_file_sha256'] for aid,b in native.items()}
            independent['native_live_revalidation_required']=True
        _json(output/'independent-review.json', independent)
        result.update(independent_review_ready=True, agent_verdict=value['accepted_for_delivery'],
                      independent_review={'path':str(output/'independent-review.json'),'sha256':_hash(output/'independent-review.json')},
                      note='Independent observations are ready; call delivery.review with the original contract for final acceptance')
    except Exception as exc:
        result['findings'].append({'kind':'INDEPENDENT_RUN_NOT_ACCEPTED','error':str(exc)})
    result['artifacts'] = {p.name:{'path':str(p),'sha256':_hash(p)} for p in output.iterdir() if p.is_file()}
    _json(output/'runner-result.json',result)
    return result
