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
        import logging
        if os.environ.get('LUOMU_CAD_DEBUG')=='1':
            logging.getLogger(__name__).exception('CAD %s failed',method)
        return {"ok":False,"error":str(exc),"error_type":type(exc).__name__,"cad_started":None if method=='start' else False,"gui_fallback":False}


@mcp.tool()
def workbench_status() -> dict:
    """Check environment only; does not attach to or start AutoCAD."""
    from importlib.metadata import version
    return {"ok":True,"skill":"luomu-cad","version":__version__,"transport":"stdio-mcp",
        "output_root":str(jobs.root),"live_writes_enabled":os.environ.get("LUOMU_CAD_LIVE_WRITES")=="1",
        "dependencies":{name:version(name) for name in ("mcp","ezdxf","shapely","scrapling","protego")}}


@mcp.tool()
async def cad_adapt_session(model_id:str|None=None,provider:str|None=None,context_window:int|None=None,
                            task_target:str="unspecified",deliverable:str="geometry_plan",source_format:str="unspecified") -> dict:
    """Use disclosed metadata only. Unknown model identities remain unknown."""
    if task_target not in {'unspecified','reference','offline_dxf','live_cad'}:
        raise ValueError('task_target requires reference/offline_dxf/live_cad')
    if deliverable not in {'geometry_plan','furnished_plan','faithful_redraw'}:raise ValueError('Unknown deliverable')
    if source_format not in {'unspecified','pdf','dxf','image'}:raise ValueError('Unknown source format')
    workflow={'task_target':task_target,'deliverable':deliverable,'task_target_required_before_drawing':task_target=='unspecified',
              'automatic_offline_fallback':False,'schema_before_tool_call':True,
              'on_tool_error':'Read the original error; correct inputs before retrying. Do not loop unchanged requests.',
              'acceptance':'Tool ok is not task completion. Check requested contents, saved readback and rendered view.',
              'next_tools':(['cad_detect_versions','list_documents','cad_connect','cad_read_entities'] if task_target=='live_cad' else
                            ['cad_tool_schema','workbench_generate'] if task_target=='offline_dxf' else []),
              'furnished_plan_required_fields':['floor_boundary','furniture','furniture_requirements','clear_zones'] if deliverable=='furnished_plan' else [],
              'furniture_relationship_fields':['room','placement','clearances','clearance_basis'] if deliverable=='furnished_plan' else [],
              'cad_start_supported':True,'cad_start_requires_explicit_task':True}
    if task_target in {'offline_dxf','live_cad'}:
        workflow.update(standards_basis_required_before_delivery=True,
                        standards_reference='references/standards-foundation.md',
                        standards_tools=['workbench_standards'])
    if deliverable=='faithful_redraw':
        workflow.update(reference_inventory_required=True,generator_output_is_reference=False,
            presentation_reference='references/pdf-presentation.md',
            conversion_helpers=['PageTransform.add_cubic','measured_text_attributes','stroke_attributes','add_solid_fill'],
            preflight_identity_required=True,
            source_format=source_format,
            next_tools=['cad_tool_schema',*(['workbench_pdf_inventory'] if source_format=='pdf' else ['workbench_source_inventory'] if source_format=='dxf' else []),'workbench_redraw'],
            verification='scripts/verify_redraw.py with --reference-inventory, --source and --review; structural-only is diagnostic')
        workflow['verification']+='; full delivery also requires --standards-manifest with explicit reproduction/review scope'
        if source_format=='image':
            workflow.update(raster_reference='references/raster-redraw-quality.md',
                coordinate_modes=['calibrated_mm','unscaled_source_coordinates'],
                native_representation='Reconstruct source components using clean native geometry; do not trace JPEG texture as microfaces',
                raster_component_inventory_required=True,
                component_tool='workbench_components',
                component_reference='references/house-plan-components.md',
                old_geometry_replay_requires_current_source_comparison=True,
                prototype_before_batch=True)
    return {"ok":True,"profile":{"model_id":model_id or "unknown","provider":provider or "unknown","context_window":context_window,"entity_page_size":20},'workflow':workflow,
        "tools":[{"name":t.name,"description":t.description} for t in await mcp.list_tools()]}


@mcp.tool()
async def cad_tool_schema(name:str) -> dict:
    """Read the authoritative schema before composing a tool request."""
    tools={t.name:t for t in await mcp.list_tools()}
    if name not in tools:
        raise ValueError("Unknown tool")
    return {"ok":True,"tool":tools[name].model_dump(mode="json")}


@mcp.tool()
async def workbench_generate(job_id:str,spec:dict,target:str="offline_dxf") -> dict:
    """Generate offline DXF/PNG, not an active-CAD drawing. furnished_plan requires furniture with room, placement (wall + gap or freestanding + reason), clearances and clearance_basis; also floor_boundary, room requirements and circulation zones. Validate relationships before coordinates; never substitutes for a live CAD task or full design acceptance."""
    if target!='offline_dxf' or spec.get('target','offline_dxf')!='offline_dxf':
        raise ValueError('TARGET_MISMATCH: workbench_generate cannot fulfill a live_cad task; attach through CAD MCP instead')
    if spec.get('deliverable')=='faithful_redraw':
        raise ValueError('REDRAW_ROUTE_REQUIRED: use source inventory and source-to-entity mapping, not the parameterized design generator')
    return await asyncio.to_thread(jobs.generate,job_id,spec)


@mcp.tool()
async def workbench_components(operation:str='catalogue',query:str='',spec:dict|None=None,
                               output:str|None=None) -> dict:
    """Discover Luomu CAD components or build a wall-bound native DXF bundle.

    Explicit opening host, position, width, side and hinge are required. Source-coordinate
    mode requires library_scale and scale_basis. This offline tool does not insert into CAD.
    """
    from .components import catalogue, build
    if operation=='catalogue':
        return await asyncio.to_thread(catalogue,query)
    if operation=='build' and spec is not None and output:
        return await asyncio.to_thread(build,spec,inside(output,ROOT))
    raise ValueError('Use catalogue or build with spec and output')


@mcp.tool()
async def workbench_patch_opening(job_id:str,source_job:str,expected_revision:str,opening_id:str,changes:dict) -> dict:
    """Update owned host-wall/opening/schedule groups in a copy; verify all other entity hashes."""
    return await asyncio.to_thread(jobs.patch,job_id,source_job,expected_revision,opening_id,changes)


@mcp.tool()
async def workbench_curved_walls(job_id:str,spec:dict) -> dict:
    """Create exact concentric circular-wall ARC/CIRCLE boundaries in mm, with explicit arc-length voids. Read back every entity. No inferred join, door leaf or furniture placement."""
    return await asyncio.to_thread(jobs.curved_walls,job_id,spec)


@mcp.tool()
async def workbench_redraw(job_id:str,source:str,inventory:dict) -> dict:
    """Build editable DXF from a source-derived inventory, preserve presentation and read back against that inventory. Requires original source SHA; no image interpretation, scale inference or complete-visual-acceptance claim."""
    return await asyncio.to_thread(jobs.redraw,job_id,inside(source,ROOT),inventory)


@mcp.tool()
async def cad_performance_snapshot(document_token:str) -> dict:
    """Read current path/token, save state, object count and supported graphics/preview variables. No settings change, scan, benchmark, save or restart. Read timings do not measure mouse interaction."""
    return await _cad('performance_snapshot',document_token)


@mcp.tool()
def workbench_assess_interaction(evidence:dict) -> dict:
    """Assess a supplied same-document before/after interaction observation. Command timings alone never establish recovery; no CAD contact or root-cause claim."""
    from .performance import assess_interaction
    return assess_interaction(evidence)


@mcp.tool()
async def workbench_standards(operation:str='catalogue',discipline:str|None=None,jurisdiction:str='CN',
                              manifest:dict|None=None,drawing:str|None=None,evidence_directory:str|None=None,
                              project_catalogue:dict|None=None) -> dict:
    """Discover source-linked cross-industry standards or check a project basis against a saved drawing and evidence hashes. Candidates never auto-apply. Metadata, clause review and engineering approval remain separate. No network, CAD access or engineering certification."""
    from .standards import catalogue,route,review_basis
    if operation=='catalogue':
        value=catalogue()
        return {'ok':True,'checked_on':value['checked_on'],'scope':value['scope'],
                'standards_count':len(value['standards']),'routes':value['routes'],
                'portals':value['portals'],'auto_apply':False,'engineering_approval':False}
    if operation=='route':return {'ok':True,**route(discipline,jurisdiction)}
    if operation=='review':
        if not drawing or not evidence_directory:raise ValueError('Saved drawing and evidence directory required')
        return await asyncio.to_thread(review_basis,manifest,inside(drawing,ROOT),inside(evidence_directory,ROOT),project_catalogue)
    raise ValueError('Use catalogue/route/review')


@mcp.tool()
async def workbench_professional(operation:str='profiles',profile_ids:list[str]|None=None,
                                 drawing:str|None=None,manifest:dict|None=None,
                                 evidence_directory:str|None=None) -> dict:
    """List professional task profiles, create a pending review template, or measure a saved DXF.

    Resolves actual object lineweights/widths and compares source-bound geometry.
    No live CAD access, design calculation or engineering approval.
    """
    from .professional import profiles,template,audit
    if operation=='profiles':
        library=profiles()
        return {'schema_version':library['schema_version'],'profiles':[
            {key:row[key] for key in ('id','title','standard_routes','validation_level')}
            for row in library['profiles']]}
    if operation=='template':return template(profile_ids)
    if operation=='review':
        if not drawing or not evidence_directory:
            raise ValueError('Saved DXF and evidence directory required')
        return await asyncio.to_thread(audit,inside(drawing,ROOT),manifest,inside(evidence_directory,ROOT))
    raise ValueError('Use profiles/template/review')


@mcp.tool()
async def workbench_pdf_inventory(job_id:str,source:str,calibration:dict,font_map:dict|None=None,page:int=0) -> dict:
    """Extract a local vector PDF page to a source-derived mm inventory. Explicit two-direction calibration and local font mapping; preserve source geometry/paint. Report unsupported objects and block incomplete construction. Does not infer native dimension semantics or operate CAD."""
    return await asyncio.to_thread(jobs.pdf_inventory,job_id,inside(source,ROOT),calibration,font_map,page)


@mcp.tool()
async def workbench_export_pdf(job_id:str,source:str,paper_mm:list[float],window_mm:list[float],scale:float,margin_mm:float=10) -> dict:
    """Export saved output-root DXF to vector PDF at explicit 1:scale, paper mm and model window. No auto-fit, source edits or CAD access."""
    return await asyncio.to_thread(jobs.export_pdf,job_id,source,paper_mm,window_mm,scale,margin_mm)


@mcp.tool()
async def cad_start(operation_id:str,explicit_request:bool=False,progid:str='AutoCAD.Application') -> dict:
    """Start AutoCAD only for an explicit application-start task with live writes enabled. Reuse a running app; never restart or automatically launch on failed attach."""
    return await _cad('start',operation_id,explicit_request,progid)


@mcp.tool()
async def cad_save_as(operation_id:str,document_token:str,path:str) -> dict:
    """Save the bound active document to a new absolute DWG path via ActiveX. Requires live writes and token; no overwrite. Returns refreshed document token and file hash."""
    return await _cad('save_as',operation_id,document_token,path)


@mcp.tool()
async def cad_new_document(operation_id:str,explicit_request:bool=False,units:int=4,template:str|None=None) -> dict:
    """Create and bind a separate CAD drawing for an explicit new-document task. Preserve existing documents; require live writes. Optional template is an absolute local DWT."""
    return await _cad('new_document',operation_id,explicit_request,units,template)


@mcp.tool()
async def cad_open_document(operation_id:str,path:str,explicit_request:bool=False,read_only:bool=False) -> dict:
    """Open an explicitly requested absolute local DWG/DXF in CAD and bind its token. Preserve all other documents; never overwrite or launch CAD on failed attach."""
    return await _cad('open_document',operation_id,path,explicit_request,read_only)


@mcp.tool()
async def cad_activate_document(document_name:str,explicit_request:bool=False) -> dict:
    """Activate an exactly identified already-open CAD document for an explicit task. Does not open, close, save or alter its entities."""
    return await _cad('activate_document',document_name,explicit_request)


@mcp.tool()
async def cad_close_document(operation_id:str,document_token:str,explicit_request:bool=False) -> dict:
    """Close only a saved document opened or created by this MCP session. Refuse preexisting documents and unsaved edits; no discard, implicit SaveAs or application shutdown."""
    return await _cad('close_document',operation_id,document_token,explicit_request)


@mcp.tool()
async def cad_preview(operation_id:str,document_token:str,path:str,render_png:bool=True) -> dict:
    """Export a native model-space WMF/BMP and a readable PNG using verified coordinate mapping. Requires current token and a new absolute destination. No desktop capture, drawing save or entity changes."""
    result=await _cad('preview',operation_id,document_token,path)
    if not result.get('ok') or not render_png:return result
    def rasterize():
        from pathlib import Path
        import hashlib,io
        from .native_preview import render_wmf
        target=Path(result['path']).with_suffix('.png');stream=io.BytesIO()
        if result['format']=='wmf':metadata=render_wmf(result['path'],stream)
        else:
            from PIL import Image
            im=Image.open(result['path']);im.save(stream,format='PNG')
            metadata={'size':list(im.size),'renderer':'Native CAD bitmap'}
        data=stream.getvalue()
        if target.exists():
            if target.read_bytes()!=data:raise ValueError('NATIVE_PREVIEW_PNG_CHANGED: existing PNG not overwritten')
        else:target.write_bytes(data)
        return {**metadata,'path':str(target),'sha256':hashlib.sha256(data).hexdigest()}
    try:return {**result,'png':await asyncio.to_thread(rasterize)}
    except Exception as exc:return {**result,'ok':False,'error':str(exc),'native_export_succeeded':True}


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
    """Solve axis-aligned rectangles only. Uniform clearance also offsets room boundaries; this is not furniture functional design. Verify wall placement, facing and use spaces separately through furnished_plan."""
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
async def cad_presentation_snapshot(document_token:str,max_entities:int=20000) -> dict:
    """Read actual layer/entity lineweights, polyline widths, block references and display variables.

    Two read passes verify a stable snapshot. No save, export, selection or setting
    change. Unsupported properties remain explicit issues. No native plot claim.
    """
    return await _cad('presentation_snapshot',document_token,max_entities)


@mcp.tool()
async def cad_mutate(operation_id:str,document_token:str,operation:str,arguments:dict) -> dict:
    """Authorized live line/circle/arc/polyline/text/dimension/properties/save; arc angles are degrees. Requires session write flag and document token. Interrupted operations stay uncertain and are never automatically replayed."""
    return await _cad("mutate",operation_id,document_token,operation,arguments)


@mcp.tool()
def cad_operation(operation_id:str) -> dict:
    """Read the durable live-write journal; a started operation must be checked before retrying."""
    return cad.journal.get(operation_id) or {"ok":False,"error":"Unknown operation"}


def main():
    try:mcp.run(transport="stdio")
    finally:cad_thread.shutdown(wait=False)

if __name__=="__main__":main()
