"""MCP client CLI; all live CAD operations remain inside the MCP service."""
import argparse
import asyncio
import json
import os
import sys
from datetime import timedelta
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from .storage import ROOT, atomic_json


def unpack(result):
    data=getattr(result,"structuredContent",None)
    if data is None:
        try:data=json.loads("\n".join(c.text for c in result.content if c.type=="text"))
        except ValueError:data={"ok":False,"error":"Non-JSON MCP response"}
    if isinstance(data,dict) and set(data)=={"result"}:data=data["result"]
    return data


async def execute(tool,arguments,live_writes=False):
    env=dict(os.environ,PYTHONUTF8="1",LUOMU_CAD_ROOT=str(ROOT),PYTHONPATH=str(ROOT/"src"),LUOMU_CAD_LIVE_WRITES="1" if live_writes else "0")
    logs=ROOT/"runtime/logs"
    logs.mkdir(parents=True,exist_ok=True)
    with (logs/"mcp.log").open("a",encoding="utf-8") as log:
        parameters=StdioServerParameters(command=sys.executable,args=["-u","-m","luomu_cad.server"],env=env,cwd=str(ROOT))
        async with stdio_client(parameters,errlog=log) as (read,write):
            async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=240)) as session:
                await session.initialize()
                result=await session.call_tool(tool,arguments)
                data=unpack(result)
                if result.isError and isinstance(data,dict):data["ok"]=False
                return data


async def live_status(once=False):
    attempts=0
    while True:
        if (ROOT/"runtime/PAUSE").exists():
            return {"ok":False,"status":"paused"}
        try:result=await execute("cad_connect",{})
        except Exception as exc:result={"ok":False,"error":str(exc)}
        attempts+=1
        atomic_json(ROOT/"runtime/live-status.json",{**result,"attempts":attempts})
        if result.get("ok") or once:return result
        # Explicit status workflow retries reads only, never writes or application launch.
        await asyncio.sleep([1,2,5,10,20,30][min(attempts-1,5)])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="action",required=True)
    sub.add_parser("health")
    sub.add_parser("serve")
    status=sub.add_parser("status")
    status.add_argument("--once",action="store_true")
    generate=sub.add_parser("generate")
    generate.add_argument("spec")
    generate.add_argument("--job",required=True)
    research=sub.add_parser("research")
    research.add_argument("operation",choices=["status","run","report","search","ingest"],default="run",nargs="?")
    research.add_argument("--query",default="")
    research.add_argument("--discipline",default="")
    research.add_argument("--drawing-type",default="")
    research.add_argument("--url",default="")
    research.add_argument("--limit",type=int,default=16)
    research.add_argument("--time-budget",type=int,default=120)
    call=sub.add_parser("call")
    call.add_argument("tool")
    call.add_argument("arguments",help="JSON object")
    args=parser.parse_args()
    if args.action=="serve":
        from .server import main as serve
        return serve()
    if args.action=="status":result=asyncio.run(live_status(args.once))
    else:
        if args.action=="health":tool,arguments="workbench_status",{}
        elif args.action=="generate":tool,arguments="workbench_generate",{"job_id":args.job,"spec":json.loads(__import__('pathlib').Path(args.spec).read_text(encoding="utf-8-sig"))}
        elif args.action=="research":tool,arguments="workbench_research",{k:v for k,v in vars(args).items() if k!="action"}
        else:tool,arguments=args.tool,json.loads(args.arguments)
        # CLI calls stay read-only. Authorized live write clients use a persistent MCP session.
        result=asyncio.run(execute(tool,arguments))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if isinstance(result,dict) and result.get("ok") is False else 0

if __name__=="__main__":sys.exit(main())
