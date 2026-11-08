"""Bound native JSON reading is not a live DWG acceptance channel.

Fixtures use fake native objects and synthetic DWG bytes, never AutoCAD/API.
"""
import copy
import hashlib
import json
from pathlib import Path
from datetime import timedelta
import sys

import ezdxf
import pytest
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

from luomu_cad.storage import ROOT,digest
from luomu_cad import review_runner as runner
from luomu_cad.review_evidence_server import Evidence
from luomu_cad.native_delivery import capture,inspect
from luomu_cad.native_correspondence import correspondence_preview
from test_native_delivery import document,retry
from test_review_runner import native_fixture


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value),encoding='utf8')


def sample(tmp_path):
    native=tmp_path/'native.dwg';native.write_bytes(b'AC1032-synthetic-protocol-only-not-a-real-DWG')
    doc=ezdxf.new();doc.units=4;doc.layers.new('WALL',dxfattribs={'lineweight':25})
    entity=doc.modelspace().add_line((0,0),(1000,0),dxfattribs={'layer':'WALL'})
    source=tmp_path/'source.dxf';doc.saveas(source)
    memory=document(native);memory.ModelSpace.items[0].Handle=entity.dxf.handle
    facts=capture(memory,retry)
    facts['model'][0]['native_entity_groups']=[(0,'LINE'),(5,entity.dxf.handle)]
    facts['layers'][0]['transparency_xdata']=[None,None]
    snapshot={'ok':True,'path':str(native),'file_sha256':sha(native),'document_token':'synthetic-native-token',
        'provenance':{'kind':'open_document','operation_id':'synthetic-only','path':str(native),'file_sha256':sha(native)},
        'facts':facts,'snapshot_sha256':digest(facts),'stable_read_verified':True,'saved':True,'dbmod':0,'settings_changed':False}
    snapshot['correspondence_preview']=correspondence_preview(snapshot,source,tmp_path/'full.png')
    sidecar=tmp_path/'capture.json';save(sidecar,snapshot)
    task=tmp_path/'original-task.txt';task.write_text('Original task: retain actual native DWG and source DXF; compare original line1000.',encoding='utf8')
    record=lambda path:{'path':path.name,'sha256':sha(path)}
    brief=tmp_path/'brief.json';save(brief,{'scope':'reference_redraw','original_task':record(task),
        'requirements':[{'id':'R1','description':'Native line corresponds to original source',
            'checks':[{'artifact_id':'dwg','source_artifact_id':'source'}]}],
        'required_sheets':[{'sheet_id':'P01','formats':['dwg','dxf']}]})
    packet={'schema_version':1,'contract_id':'native-original','producer_id':'fixture-producer',
        'customer_brief':record(brief),'artifacts':[dict(record(native),id='dwg',sheet_id='P01'),dict(record(source),id='source',sheet_id='P01')],
        'raw_sources':[record(task)],'native_evidence':{'dwg':{'snapshot':record(sidecar),'source_artifact_id':'source'}}}
    path=tmp_path/'packet.json';save(path,packet)
    home=tmp_path/'home';home.mkdir();(home/'config.toml').write_text('model="same-existing-model"',encoding='utf8')
    return path,packet,snapshot,home


def test_public_native_hook_tracks_every_dependency_but_json_is_not_live_context(tmp_path):
    path,packet,snapshot,_=sample(tmp_path)
    verified=runner.validate_native_evidence(packet,tmp_path)
    assert set(p.name for p in verified['tracked'])=={'native.dwg','source.dxf','capture.json','full.png'}
    assert verified['bindings']['dwg']['live_context_provided'] is False
    assert runner._prepare(path)[-1].keys()>=verified['tracked'].keys()
    with pytest.raises(ValueError,match='LIVE_MCP'):inspect(snapshot,tmp_path/'native.dwg',{})


@pytest.mark.parametrize('attack',['missing','digest','dirty','provenance','clipped','source','image','geometry','format'])
def test_native_binding_never_accepts_stale_partial_or_substituted_evidence(tmp_path,attack):
    path,packet,snapshot,_=sample(tmp_path);sidecar=tmp_path/'capture.json'
    if attack=='missing':packet.pop('native_evidence')
    elif attack=='digest':snapshot['snapshot_sha256']='0'*64
    elif attack=='dirty':snapshot['dbmod']=1
    elif attack=='provenance':snapshot['provenance']['file_sha256']='0'*64
    elif attack=='clipped':snapshot['correspondence_preview']['full_model_coverage_verified']=False
    elif attack=='source':snapshot['correspondence_preview']['source_file_sha256']='0'*64
    elif attack=='image':(tmp_path/'full.png').write_bytes(b'not-the-locked-image')
    elif attack=='geometry':
        snapshot['facts']['model'][0]['EndPoint']=[999,0,0]
        snapshot['snapshot_sha256']=digest(snapshot['facts'])
        snapshot['correspondence_preview']['native_snapshot_sha256']=snapshot['snapshot_sha256']
    else:
        (tmp_path/'native.dwg').write_bytes(b'not-native-format')
        packet['artifacts'][0]['sha256']=sha(tmp_path/'native.dwg')
    if attack not in {'missing','image','format'}:
        save(sidecar,snapshot);packet['native_evidence']['dwg']['snapshot']['sha256']=sha(sidecar)
    with pytest.raises(ValueError):runner.validate_native_evidence(packet,tmp_path)


def test_real_controlled_native_read_pipeline_keeps_original_formats_and_task_binding(tmp_path,monkeypatch):
    path,packet,snapshot,home=sample(tmp_path)
    value={'accepted_for_delivery':True,'requirement_inventory_checked':True,
        'inventory_observation':'Original task and both requested original formats were independently read.',
        'requirements':[{'requirement_id':'R1','verdict':'accepted','finding':'The actual declared native facts and separately read source line are consistent.',
            'observations':[{'artifact_id':aid,'locator':'Original line handle and full correspondence image',
                'source_locator':'Original customer R1 source/native relationship','finding':'Actual endpoints and complete visual preview were read independently.','preview_index':0} for aid in ['dwg','source']]}],
        'unresolved':[]}
    native_fixture(monkeypatch,tmp_path,value)
    result=runner.run(path,tmp_path/'review',home,bundle_root=ROOT)
    assert result['independent_review_ready'],result
    assert result['accepted_for_delivery'] is False
    report=json.loads(Path(result['independent_review']['path']).read_text(encoding='utf8'))
    assert report['native_live_revalidation_required'] is True
    assert report['original_task_sha256']==packet['raw_sources'][0]['sha256']
    assert report['artifact_sha256']['dwg']==sha(tmp_path/'native.dwg')
    assert report['native_evidence_sha256']['dwg']==sha(tmp_path/'capture.json')
    inventory=json.loads((tmp_path/'review/input-inventory.json').read_text(encoding='utf8'))
    assert 'native-snapshot:dwg' in {r['file_id'] for r in inventory['authorized_files']}
    assert inventory['native_artifacts']['dwg']['offline_dwg_parsed'] is False
    lock=json.loads((tmp_path/'review/evidence-lock.json').read_text(encoding='utf8'))
    # Open a separate service-owned output to inspect sanitized responses.
    other=tmp_path/'inspection';other.mkdir();lock_path=other/'lock.json';save(lock_path,lock)
    evidence=Evidence(path,lock_path,other)
    native=evidence.read('artifact:dwg')['facts'];capture=evidence.read('native-snapshot:dwg')['facts']
    assert native['raw_native_facts']['model'][0]['EndPoint']==[1000,0,0]
    assert 'raw_native_facts' not in capture and 'comparison' not in native
    assert native['live_context_provided'] is False and native['offline_dwg_parsed'] is False
    evidence.close()


@pytest.mark.asyncio
async def test_native_bound_evidence_real_stdio_only_returns_original_facts_and_bound_image(tmp_path):
    path,packet,snapshot,_=sample(tmp_path);output=tmp_path/'stdio-review';output.mkdir()
    _,_,_,_,paths,_=runner._prepare(path)
    previews=runner._previews(paths,output)
    target=output/'native-bound-full.png';target.write_bytes((tmp_path/'full.png').read_bytes())
    previews['dwg']=[{'path':str(target),'sha256':sha(target),'source_sha256':sha(tmp_path/'native.dwg'),'page':1}]
    lock_path,_=runner._evidence_lock(path,previews,output,'native-stdio-probe')
    params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'scripts/review_evidence_server.py'),
        '--packet',str(path),'--lock',str(lock_path),'--output',str(output)])
    before=sha(tmp_path/'native.dwg')
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=15)) as session:
            await session.initialize()
            value=await session.call_tool('review_read',{'file_id':'artifact:dwg'})
            assert not value.isError
            actual=json.loads(value.content[0].text)['facts']
            assert actual['offline_dwg_parsed'] is False and actual['live_final_revalidation_required'] is True
            assert actual['raw_native_facts']['model'][0]['EndPoint']==[1000,0,0]
            image=await session.call_tool('review_view',{'file_id':'artifact:dwg','preview_index':0})
            metadata=json.loads(image.content[0].text)
            assert not image.isError and image.content[1].type=='image'
            assert metadata['preview']['native_export'] is False and metadata['preview']['native_paper_plot'] is False
            import base64
            assert hashlib.sha256(base64.b64decode(image.content[1].data)).hexdigest()==sha(target)
            task=await session.call_tool('review_read',{'file_id':'source:0'})
            assert not task.isError and json.loads(task.content[0].text)['source_sha256']==packet['raw_sources'][0]['sha256']
    assert sha(tmp_path/'native.dwg')==before
