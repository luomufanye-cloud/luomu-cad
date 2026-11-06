"""Public synthetic vector PDF -> inventory -> editable DXF through real MCP."""
import os
from pathlib import Path
import sys
import ezdxf
import pytest
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from luomu_cad.cli import unpack
from luomu_cad.storage import ROOT
from test_pdf_source import write_pdf


@pytest.mark.asyncio
async def test_pdf_to_editable_drawing_real_mcp(tmp_path):
    source=tmp_path/'original.pdf'
    write_pdf(source,b'0.2 w 0 0 0 RG 10 10 m 110 10 l S 10 30 m 30 60 70 60 110 30 c S')
    calibration={'source_points':[[10,10],[110,10]],'distance_mm':1000,
                 'check_points':[[10,10],[10,110]],'check_distance_mm':1000,'tolerance_mm':.01}
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),LUOMU_CAD_ROOT=str(tmp_path),LUOMU_CAD_LIVE_WRITES='0',PYTHONUTF8='1')
    params=StdioServerParameters(command=sys.executable,args=['-m','luomu_cad.server'],env=env,cwd=str(ROOT))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            args={'job_id':'vector-extract','source':str(source),'calibration':calibration}
            extracted=unpack(await session.call_tool('workbench_pdf_inventory',args))
            assert extracted['ok'],extracted
            assert extracted['inventory']['extraction_complete']
            assert Path(extracted['artifacts']['inventory']['path']).is_file()
            assert unpack(await session.call_tool('workbench_pdf_inventory',args))['artifacts']==extracted['artifacts']
            redraw=unpack(await session.call_tool('workbench_redraw',{'job_id':'vector-redraw','source':str(source),'inventory':extracted['inventory']}))
            assert redraw['ok'],redraw
            drawing=ezdxf.readfile(redraw['artifacts']['dxf']['path'])
            assert len(drawing.modelspace().query('LINE'))==1 and len(drawing.modelspace().query('SPLINE'))==1
            invalid=unpack(await session.call_tool('workbench_pdf_inventory',{'job_id':'bad-calibration','source':str(source),'calibration':{**calibration,'check_distance_mm':1200}}))
            assert not invalid['ok'] and 'CALIBRATION_CONFLICT' in invalid['error']
            incomplete={**extracted['inventory'],'extraction_complete':False}
            refused=unpack(await session.call_tool('workbench_redraw',{'job_id':'incomplete','source':str(source),'inventory':incomplete}))
            assert not refused['ok'] and 'PDF_EXTRACTION_INCOMPLETE' in refused['error']
