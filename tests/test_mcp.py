import json
import os
import sys
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
            profile=unpack(await session.call_tool("cad_adapt_session",{}))
            assert profile["profile"]["model_id"]=="unknown"
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
