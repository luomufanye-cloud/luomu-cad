"""Opt-in real AutoCAD acceptance through persistent stdio MCP only.

Creates an isolated drawing, checks native arcs/dimensions, exports a native
preview, saves DWG, closes and reopens it. Existing drawings are preserved.
"""
import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from luomu_cad.cli import unpack


async def verify(destination):
    destination.mkdir(parents=True,exist_ok=False)
    evidence={'ok':False,'cad_contacted':True,'transport':'stdio-mcp','stages':{},
              'started_at':datetime.now(timezone.utc).isoformat(),'existing_drawings_modified':False}
    report=destination/'native-acceptance.json'
    def save():report.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    env=dict(os.environ,LUOMU_CAD_ROOT=str(ROOT),PYTHONPATH=str(ROOT/'src'),LUOMU_CAD_LIVE_WRITES='1',PYTHONUTF8='1')
    params=StdioServerParameters(command=sys.executable,args=['-u','-m','luomu_cad.server'],env=env,cwd=str(ROOT))
    prefix='native-'+datetime.now().strftime('%Y%m%d%H%M%S%f')
    try:
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=240)) as session:
                await session.initialize()
                async def call(label,tool,args,expect_error=None):
                    result=unpack(await session.call_tool(tool,args))
                    evidence['stages'][label]=result;save()
                    print(json.dumps({'stage':label,'ok':result.get('ok'),'error':result.get('error')},ensure_ascii=False),flush=True)
                    if expect_error:
                        assert result.get('ok') is False and expect_error in result.get('error',''),result
                    else:assert result.get('ok') is True,result
                    return result
                await call('start_without_request','cad_start',{'operation_id':prefix+'-no-start'},'Explicit')
                await call('start','cad_start',{'operation_id':prefix+'-start','explicit_request':True})
                await call('start_replay','cad_start',{'operation_id':prefix+'-start','explicit_request':True})
                before=await call('documents_before','list_documents',{})
                initial=None
                if before['documents']:
                    initial=await call('initial_binding','cad_connect',{})
                created=await call('new_document','cad_new_document',{'operation_id':prefix+'-new','explicit_request':True,'units':4})
                token=created['document_token']
                arc_args={'center':[1000,2000],'radius':3000,'start_angle':330,'end_angle':90}
                arc=await call('arc','cad_mutate',{'operation_id':prefix+'-arc','document_token':token,'operation':'arc','arguments':arc_args})
                await call('arc_replay','cad_mutate',{'operation_id':prefix+'-arc','document_token':token,'operation':'arc','arguments':arc_args})
                await call('circle','cad_mutate',{'operation_id':prefix+'-circle','document_token':token,'operation':'circle','arguments':{'center':[1000,2000],'radius':100}})
                dimension=await call('dimension','cad_mutate',{'operation_id':prefix+'-dim','document_token':token,'operation':'dimension',
                    'arguments':{'start':[1000,2000],'end':[4000,2000],'at':[2500,1000],
                      'style':{'TextHeight':2.5,'ArrowheadSize':2.5,'TextGap':1.,'ScaleFactor':50.,'LinearScaleFactor':1.,'ExtensionLineOffset':1.,'ExtensionLineExtend':2.}}})
                await call('text','cad_mutate',{'operation_id':prefix+'-text','document_token':token,'operation':'text',
                    'arguments':{'at':[1000,5500],'text':'NATIVE ARC / DWG READBACK','height':150}})
                await call('reject_unsaved_close','cad_close_document',{'operation_id':prefix+'-bad-close','document_token':token,'explicit_request':True},'UNSAVED')
                native=await call('readback_before_save','cad_read_entities',{'document_token':token,'limit':20})
                def check_geometry(result):
                    assert result['total']==4,result
                    entities={e['handle']:e for e in result['entities']}
                    a=entities[arc['handle']];d=entities[dimension['handle']]
                    assert a['type']=='AcDbArc' and math.dist(a['Center'],[1000,2000,0])<1e-7
                    assert abs(a['Radius']-3000)<1e-7
                    assert abs(a['StartAngle']-math.radians(330))<1e-7 and abs(a['EndAngle']-math.pi/2)<1e-7
                    assert abs(d['Measurement']-3000)<1e-7
                    assert d['TextHeight']==2.5 and d['ScaleFactor']==50 and d['LinearScaleFactor']==1
                check_geometry(native)
                preview=await call('native_preview','cad_preview',{'operation_id':prefix+'-preview','document_token':token,'path':str(destination/'native.wmf')})
                from luomu_cad.native_preview import render_wmf
                render_wmf(preview['path'],destination/'native-preview.png')
                evidence['native_preview_raster_sha256']=hashlib.sha256((destination/'native-preview.png').read_bytes()).hexdigest()
                dwg=destination/'native-acceptance.dwg'
                saved=await call('save_as','cad_save_as',{'operation_id':prefix+'-save','document_token':token,'path':str(dwg)})
                await call('save_replay','cad_save_as',{'operation_id':prefix+'-save','document_token':token,'path':str(dwg)})
                token=saved['document_token']
                await call('reject_overwrite','cad_save_as',{'operation_id':prefix+'-overwrite','document_token':token,'path':str(dwg)},'exists')
                await call('close','cad_close_document',{'operation_id':prefix+'-close','document_token':token,'explicit_request':True})
                reopened=await call('reopen','cad_open_document',{'operation_id':prefix+'-reopen','path':str(dwg),'explicit_request':True})
                assert reopened['document_token']!=token,'Reopening must issue a new document identity'
                await call('reject_old_reopen_token','cad_read_entities',{'document_token':token,'limit':20},'TOKEN_MISMATCH')
                token=reopened['document_token']
                after=await call('readback_reopened','cad_read_entities',{'document_token':token,'limit':20})
                check_geometry(after)
                assert native['entities']==after['entities'],'Native entities changed after SaveAs/reopen'
                await call('close_reopened','cad_close_document',{'operation_id':prefix+'-close-reopened','document_token':token,'explicit_request':True})
                if initial:
                    await call('restore_original_active','cad_activate_document',{'document_name':initial['path'] or initial['document'],'explicit_request':True})
                remaining=await call('documents_after','list_documents',{})
                assert before['documents']==remaining['documents'],'Existing document set changed'
                evidence.update(ok=True,cold_start=evidence['stages']['start']['cad_started'],
                    native_geometry_reopened=True,native_preview=preview,
                    dwg_sha256=hashlib.sha256(dwg.read_bytes()).hexdigest(),
                    tested=['start','native arc','native dimension','native preview','DWG SaveAs','DWG reopen','operation replay','overwrite rejection','unsaved-close rejection'],
                    host_model_tested=False)
    except BaseException as exc:
        evidence['failure']={'type':type(exc).__name__,'message':str(exc)}
        raise
    finally:save()
    return evidence


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-native',action='store_true',help='Explicitly authorize launching CAD and creating isolated test files/documents')
    parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args()
    if not args.run_native:parser.error('--run-native is required; this test contacts real AutoCAD')
    if os.name!='nt':parser.error('Native AutoCAD acceptance requires Windows')
    result=asyncio.run(verify(args.destination.resolve()))
    print(json.dumps({'ok':result['ok'],'cold_start':result['cold_start'],'report':str(args.destination.resolve()/'native-acceptance.json')},ensure_ascii=False))


if __name__=='__main__':main()
