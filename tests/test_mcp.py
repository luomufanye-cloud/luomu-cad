import json
import os
import sys
from pathlib import Path
import pytest
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from luomu_cad.cli import unpack
from luomu_cad.storage import ROOT


@pytest.mark.asyncio
async def test_real_stdio_mcp_metadata_drawing_patch_and_research(tmp_path):
    env=dict(os.environ,PYTHONPATH=str(ROOT/"src"),LUOMU_CAD_ROOT=str(tmp_path),LUOMU_CAD_LIVE_WRITES="0",PYTHONUTF8="1")
    parameters=StdioServerParameters(command=sys.executable,args=["-m","luomu_cad.server"],env=env,cwd=str(ROOT))
    async with stdio_client(parameters) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            names={t.name for t in (await session.list_tools()).tools}
            assert {"cad_connect","cad_mutate","workbench_generate","workbench_research","workbench_learn"}<=names
            assert {'cad_start','cad_save_as','workbench_curved_walls','workbench_export_pdf','workbench_redraw'}<=names
            assert {'cad_new_document','cad_open_document','cad_activate_document','cad_close_document','cad_preview'}<=names
            assert {'cad_performance_snapshot','workbench_assess_interaction'}<=names
            assert 'workbench_components' in names
            assert 'workbench_solid' in names
            components=unpack(await session.call_tool('workbench_components',{'query':'sofa'}))
            assert any(row['key']=='sofa' for row in components['furniture'])
            from test_house_components import plan as component_plan
            component_result=unpack(await session.call_tool('workbench_components',{
                'operation':'build','spec':component_plan(),'output':str(tmp_path/'component-mcp')}))
            assert component_result['geometry_passed']
            assert component_result['single_door_readback'][0]['hinge_gap']<1e-6
            standards=unpack(await session.call_tool('workbench_standards',{'operation':'route','discipline':'mechanical'}))
            assert standards['ok'] and not standards['auto_apply']
            assert 'mechanical-cad' in {s['id'] for s in standards['standards']}
            unbound=unpack(await session.call_tool('cad_performance_snapshot',{'document_token':'not-connected'}))
            assert not unbound['ok'] and 'CAD_NOT_CONNECTED' in unbound['error']
            performance=unpack(await session.call_tool('workbench_assess_interaction',{'evidence':{
                'document_path':'/exercise/current.dwg','document_token':'current-token','change':'one setting',
                'operation':'pan','before':'slow','after':'not observed','command_seconds':[.01]}}))
            assert not performance['interaction_recovery_accepted']
            forbidden_start=unpack(await session.call_tool('cad_start',{'operation_id':'not-authorized','explicit_request':True}))
            assert not forbidden_start['ok'] and 'LIVE_WRITES_DISABLED' in forbidden_start['error']
            forbidden_new=unpack(await session.call_tool('cad_new_document',{'operation_id':'no-new-document','explicit_request':True}))
            assert not forbidden_new['ok'] and 'LIVE_WRITES_DISABLED' in forbidden_new['error']
            curves=unpack(await session.call_tool('workbench_curved_walls',{'job_id':'curves','spec':{'walls':[{
                'id':'C1','center':[0,0],'radius':3000,'thickness':200,'start_angle':0,'sweep_angle':180}]}}))
            assert curves['ok'] and curves['readback']['checked_entities']==4
            pdf=unpack(await session.call_tool('workbench_export_pdf',{'job_id':'curves-pdf','source':curves['artifacts']['dxf']['path'],
                'paper_mm':[297,210],'window_mm':[-3500,-500,3500,3500],'scale':50}))
            assert pdf['ok'] and Path(pdf['artifacts']['pdf']['path']).read_bytes().startswith(b'%PDF-')
            from test_redraw_delivery import fixture
            _,_,ref_source,ref_inventory,_=fixture(tmp_path)
            redrawn=unpack(await session.call_tool('workbench_redraw',{'job_id':'source-redraw','source':str(ref_source),'inventory':ref_inventory}))
            assert redrawn['ok'] and not redrawn['complete_redraw_accepted']
            from test_raster_quality import source_exercise
            raster_source,raster_inventory=source_exercise(tmp_path)
            raster=unpack(await session.call_tool('workbench_redraw',{'job_id':'raster-source','source':str(raster_source),'inventory':raster_inventory}))
            assert raster['ok'] and raster['reference_check']['coordinate_basis']['status']=='unscaled'
            assert not raster['complete_redraw_accepted']
            profile=unpack(await session.call_tool("cad_adapt_session",{}))
            assert profile["profile"]["model_id"]=="unknown"
            route=unpack(await session.call_tool('cad_adapt_session',{'task_target':'live_cad','deliverable':'furnished_plan','model_id':'deepseek-v4.1-flash'}))
            assert route['workflow']['automatic_offline_fallback'] is False
            assert 'cad_connect' in route['workflow']['next_tools']
            assert route['workflow']['furnished_plan_required_fields']
            redraw=unpack(await session.call_tool('cad_adapt_session',{'task_target':'offline_dxf','deliverable':'faithful_redraw'}))
            assert redraw['workflow']['reference_inventory_required']
            assert 'workbench_generate' not in redraw['workflow']['next_tools']
            redraw_wrong=unpack(await session.call_tool('workbench_generate',{'job_id':'wrong-redraw','spec':{'deliverable':'faithful_redraw'}}))
            assert not redraw_wrong['ok'] and 'REDRAW_ROUTE_REQUIRED' in redraw_wrong['error']
            wrong=unpack(await session.call_tool('workbench_generate',{'job_id':'wrong-target','spec':{},'target':'live_cad'}))
            assert wrong['ok'] is False and 'TARGET_MISMATCH' in wrong['error']
            invalid=unpack(await session.call_tool('workbench_generate',{'job_id':'incomplete','spec':{'walls':[]}}))
            assert invalid['ok'] is False and 'walls requires' in invalid['error']
            assert unpack(await session.call_tool("workbench_status",{}))["skill"]=="luomu-cad"
            assert unpack(await session.call_tool("workbench_research",{"operation":"status"}))["pages_by_status"]=={}
            technical=json.loads((ROOT/"references/technical/wet-area-waterproof-interfaces.json").read_text(encoding="utf-8"))
            saved=unpack(await session.call_tool("workbench_technical",{"operation":"record","card":technical}))
            assert saved["ok"] and saved["auto_apply"] is False
            steps=[step['id'] for step in technical['procedure']]
            sequence=unpack(await session.call_tool("workbench_technical",{"operation":"check_sequence","card_id":technical['id'],"sequence":steps}))
            assert sequence["ok"] and not sequence["engineering_approval"]
            bad=unpack(await session.call_tool("workbench_technical",{"operation":"check_sequence","card_id":technical['id'],"sequence":[s for s in steps if s!='reinforce']}))
            assert not bad["ok"]
            unsupported=await session.call_tool("workbench_optimize",{"spec":{"width":6000,"height":4000,"boundary":[[0,0],[6000,0],[4000,4000],[0,4000]],"items":[{"id":"display","width":1500,"height":800}]}})
            assert unsupported.isError  # A rectangular result must not pretend to satisfy an irregular boundary.
            spec=json.loads((ROOT/"examples/two-room.json").read_text(encoding="utf-8"))
            generated=unpack(await session.call_tool("workbench_generate",{"job_id":"mcp-original","spec":spec}))
            assert generated["ok"],generated
            patched=unpack(await session.call_tool("workbench_patch_opening",{"job_id":"mcp-patch","source_job":"mcp-original","expected_revision":generated["revision"],"opening_id":"M2","changes":{"width":1000}}))
            assert patched["ok"] and patched["unrelated_entities_unchanged"]
