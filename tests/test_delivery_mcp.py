"""Customer acceptance is separate from successful construction over actual MCP."""
import json
import os
from pathlib import Path
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from luomu_cad.cli import unpack
from luomu_cad.storage import ROOT
from test_delivery import exercise


@pytest.mark.asyncio
async def test_industry_customer_route_and_independent_delivery_over_mcp(tmp_path):
    contract=exercise(tmp_path/'customer')
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),LUOMU_CAD_ROOT=str(tmp_path),LUOMU_CAD_LIVE_WRITES='0',PYTHONUTF8='1')
    params=StdioServerParameters(command=sys.executable,args=['-m','luomu_cad.server'],env=env,cwd=str(ROOT))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            names={row.name for row in (await session.list_tools()).tools}
            assert {'workbench_industry','workbench_delivery','workbench_project'} <= names
            profile=unpack(await session.call_tool('cad_adapt_session',{
                'task_target':'offline_dxf','deliverable':'customer_delivery','industry_ids':['interior']}))
            assert profile['workflow']['independent_delivery_review_required']
            assert profile['workflow']['default_review_agent']=='luomu-cad-reviewer'
            assert not profile['workflow']['construction_success_is_customer_acceptance']
            selected=unpack(await session.call_tool('workbench_industry',{
                'operation':'route','industry_ids':['mechanical']}))
            assert all(row['id'].startswith('mechanical.') for row in selected['drawing_types'])
            mixed=unpack(await session.call_tool('workbench_industry',{
                'operation':'validate_assignments','industry_ids':['interior'],
                'assignments':[{'industry_id':'interior','standard_id':'mechanical-cad'}]}))
            assert not mixed['ok']
            template=unpack(await session.call_tool('workbench_delivery',{
                'operation':'template','industry_ids':['interior']}))
            assert not template['accepted_for_delivery']
            approved=unpack(await session.call_tool('workbench_delivery',{
                'operation':'review','contract':contract,'base':str(tmp_path/'customer')}))
            assert approved['accepted_for_delivery'],approved
            contract['requirements'].pop()
            rejected=unpack(await session.call_tool('workbench_delivery',{
                'operation':'review','contract':contract,'base':str(tmp_path/'customer')}))
            assert not rejected['accepted_for_delivery']
            built=unpack(await session.call_tool('workbench_casework',{
                'spec':json.loads((ROOT/'examples/casework.json').read_text(encoding='utf8')),
                'output':str(tmp_path/'casework')}))
            assert built['ok']
            assert built['delivery_review_required'] and not built['accepted_for_delivery']
            outside=await session.call_tool('workbench_delivery',{
                'operation':'review','contract':contract,'base':str(tmp_path.parent)})
            assert outside.isError
