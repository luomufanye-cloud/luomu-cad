"""Single MCP entry for original file jobs, reference research and live CAD."""
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from mcp.server.fastmcp import FastMCP
from . import __version__
from .jobs import Jobs
from .cad import CAD
from .optimizer import optimize_layout
from .qa import audit_dxf
from .storage import ROOT, inside

mcp=FastMCP("luomu-cad")
jobs=Jobs()
cad=CAD()
cad_thread=ThreadPoolExecutor(max_workers=1,thread_name_prefix="luomu-cad-sta")


async def _cad(method,*args,**kwargs):
    try:
        return await asyncio.get_running_loop().run_in_executor(cad_thread,lambda:getattr(cad,method)(*args,**kwargs))
    except Exception as exc:
        return {"ok":False,"error":str(exc),"error_type":type(exc).__name__,"cad_started":False,"gui_fallback":False}


@mcp.tool()
def workbench_status() -> dict:
    """Check environment only; does not attach to or start AutoCAD."""
    from importlib.metadata import version
    return {"ok":True,"skill":"luomu-cad","version":__version__,"transport":"stdio-mcp",
        "output_root":str(jobs.root),"live_writes_enabled":os.environ.get("LUOMU_CAD_LIVE_WRITES")=="1",
        "dependencies":{name:version(name) for name in ("mcp","ezdxf","shapely","scrapling","protego")}}


@mcp.tool()
async def cad_adapt_session(model_id:str|None=None,provider:str|None=None,context_window:int|None=None) -> dict:
    """Use disclosed metadata only. Unknown model identities remain unknown."""
    return {"ok":True,"profile":{"model_id":model_id or "unknown","provider":provider or "unknown","context_window":context_window,"entity_page_size":20},
        "tools":[{"name":t.name,"description":t.description} for t in await mcp.list_tools()]}


@mcp.tool()
async def cad_tool_schema(name:str) -> dict:
    """Read the authoritative schema before composing a tool request."""
    tools={t.name:t for t in await mcp.list_tools()}
    if name not in tools:
        raise ValueError("Unknown tool")
    return {"ok":True,"tool":tools[name].model_dump(mode="json")}


@mcp.tool()
async def workbench_generate(job_id:str,spec:dict) -> dict:
    """Generate a separate offline DXF/PNG from explicit mm inputs; never operates active CAD."""
    return await asyncio.to_thread(jobs.generate,job_id,spec)


@mcp.tool()
async def workbench_patch_opening(job_id:str,source_job:str,expected_revision:str,opening_id:str,changes:dict) -> dict:
    """Update owned host-wall/opening/schedule groups in a copy; verify all other entity hashes."""
    return await asyncio.to_thread(jobs.patch,job_id,source_job,expected_revision,opening_id,changes)


@mcp.tool()
def workbench_job(job_id:str) -> dict:
    """Read committed or uncertain job state without executing it again."""
    return jobs.result(job_id) or {"ok":False,"error":"Unknown job"}


@mcp.tool()
async def workbench_audit(path:str) -> dict:
    """Check saved DXF geometry within the output root, without changing the file."""
    return await asyncio.to_thread(audit_dxf,inside(path,jobs.root))


@mcp.tool()
async def workbench_optimize(spec:dict) -> dict:
    """Solve axis-aligned rectangle placement using caller-provided mm clearances."""
    return await asyncio.to_thread(optimize_layout,spec)


@mcp.tool()
async def workbench_source_inventory(path:str,box_mm:list[float]|None=None,
                                     unit_mm:float|None=None,unit_reason:str="") -> dict:
    """Read a local DXF inside the Skill root without modifying it. Return nested source IDs, WCS-mm bounds and explicit unsupported items; no CAD connection or semantic guessing."""
    from .source_inventory import inventory
    return await asyncio.to_thread(inventory,inside(path,ROOT),box_mm,unit_mm,unit_reason)


@mcp.tool()
def workbench_dimension_chains(features:list[dict],chains:list[dict]) -> dict:
    """Check explicit axis/face/opening references and conflicting source dimension chains. Coordinates must come from saved-DXF readback; no drawing changes."""
    from .source_inventory import check_dimension_chains
    return check_dimension_chains(features,chains)


@mcp.tool()
async def workbench_research(operation:str="status",url:str="",query:str="",discipline:str="",drawing_type:str="",limit:int=16,time_budget:int=120) -> dict:
    """Bounded public reference index; no AutoCAD access, login bypass or bulk mirroring."""
    def execute():
        from .research import Research
        research=Research()
        try:
            if operation=="status": return {"ok":True,**research.status()}
            if operation=="run": return research.run(limit,time_budget)
            if operation=="ingest": return research.ingest(url)
            if operation=="search": return research.search(query,discipline,drawing_type,limit)
            if operation=="report": return {"ok":True,"report":str(research.report())}
            raise ValueError("operation requires status/run/ingest/search/report")
        finally: research.close()
    return await asyncio.to_thread(execute)


@mcp.tool()
async def workbench_learn(lesson:dict) -> dict:
    """Promote reviewed original workflow lessons with collected sources; no engineering prescriptions."""
    def execute():
        from .research import Research
        research=Research()
        try:return research.promote_lesson(lesson)
        finally:research.close()
    return await asyncio.to_thread(execute)


@mcp.tool()
async def cad_detect_versions() -> dict:
    """Read installed ProgIDs only; registration does not prove a running CAD connection."""
    return await _cad("versions")


@mcp.tool()
def workbench_technical(operation:str="list",card_id:str="",card:dict|None=None,sequence:list[str]|None=None,project_context:dict|None=None,edges:list[list[str]]|None=None) -> dict:
    """Study construction details/methods and professional systems with scoped evidence. Record/get/list cards or check a training sequence, applicability and named-terminal topology. Never applies parameters to CAD or approves engineering."""
    from .technical import TechnicalLibrary,check_sequence,check_applicability,check_connections
    library=TechnicalLibrary()
    if operation=="list":return {"ok":True,"cards":library.list()}
    if operation=="record":return library.record(card or {})
    selected=library.get(card_id)
    if operation=="get":return {"ok":True,"card":selected}
    if operation=="check_sequence":return check_sequence(selected,sequence or [])
    if operation=="check_applicability":return check_applicability(selected,project_context or {})
    if operation=="check_connections":return check_connections(selected,edges or [],project_context or {})
    raise ValueError("Unknown technical learning operation")


@mcp.tool()
async def list_documents(progid:str="AutoCAD.Application") -> dict:
    """List documents of an already-running CAD application; never launches it."""
    return await _cad("list_documents",progid)


@mcp.tool()
async def cad_connect(document_name:str|None=None,progid:str="AutoCAD.Application") -> dict:
    """Attach to the active drawing and return its identity token; never changes tabs."""
    return await _cad("connect",document_name,progid)


@mcp.tool()
async def cad_read_entities(offset:int=0,limit:int=20,document_token:str|None=None) -> dict:
    """Read a bounded page of current modelspace entities via server-side ActiveX."""
    return await _cad("read",offset,limit,document_token)


@mcp.tool()
async def cad_mutate(operation_id:str,document_token:str,operation:str,arguments:dict) -> dict:
    """Authorized live line/circle/polyline/text/dimension/properties/save. Requires session write flag and document token. Interrupted operations stay uncertain and are never automatically replayed."""
    return await _cad("mutate",operation_id,document_token,operation,arguments)


@mcp.tool()
def cad_operation(operation_id:str) -> dict:
    """Read the durable live-write journal; a started operation must be checked before retrying."""
    return cad.journal.get(operation_id) or {"ok":False,"error":"Unknown operation"}


def main():
    try:mcp.run(transport="stdio")
    finally:cad_thread.shutdown(wait=False)

if __name__=="__main__":main()
