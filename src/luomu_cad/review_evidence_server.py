"""A packet-scoped, read-only MCP evidence service; no CAD or command tool."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import io
import math
from pathlib import Path
import uuid

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

SERVER_NAME = 'luomu-cad-review-evidence'
TOOLS = {'review_inventory', 'review_read', 'review_view'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def original_records(packet_path):
    from .review_runner import _prepare,validate_native_evidence
    packet_path,packet,_,_,paths,_=_prepare(packet_path)
    base=packet_path.parent
    rows=[{'file_id':'brief','category':'customer_brief',
           'path':str((base/packet['customer_brief']['path']).resolve()),'sha256':packet['customer_brief']['sha256']}]
    rows += [{'file_id':'artifact:'+r['id'],'category':'artifact','path':str(paths[r['id']]),'sha256':r['sha256']} for r in packet['artifacts']]
    native=validate_native_evidence(packet,base)['bindings']
    for aid,binding in native.items():
        next(r for r in rows if r['file_id']=='artifact:'+aid)['native_artifact_id']=aid
        rows.append({'file_id':'native-snapshot:'+aid,'category':'native_capture',
                     'path':str(binding['snapshot_path']),'sha256':binding['snapshot_file_sha256'],
                     'native_artifact_id':aid})
    for category,name in [('source','raw_sources'),('standard','standard_sources')]:
        rows += [{'file_id':category+':'+str(index),'category':category,'path':str((base/r['path']).resolve()),'sha256':r['sha256']} for index,r in enumerate(packet[name])]
    return rows


def dimension_facts(entity,doc):
    """Separate base style, entity overrides, definition and cached displayed text."""
    base=doc.dimstyles.get(entity.dxf.dimstyle)
    overrides=entity.get_acad_dstyle(base)
    effective={**base.dxf.all_existing_dxf_attribs(),**overrides}
    name=entity.dxf.get('geometry','')
    block=doc.blocks.get(name) if name in doc.blocks else None
    texts=[]
    if block is not None:
        for item in block:
            if item.dxftype() in {'TEXT','MTEXT'}:
                texts.append({'handle':item.dxf.handle,'type':item.dxftype(),'dxf':item.dxf.all_existing_dxf_attribs(),
                              'plain_text':item.plain_text() if item.dxftype()=='MTEXT' else item.dxf.text})
    return {'native_measurement':entity.get_measurement(),
            'dimension_style':base.dxf.all_existing_dxf_attribs(),
            'entity_dimstyle_overrides':overrides,'effective_dimension_style':effective,
            'cached_display':{'block_name':name,'block_exists':block is not None,'texts':texts},
            'definition_text':entity.dxf.get('text','<>'),
            'comparison_is_reviewer_responsibility':True}


def pdf_path_facts(page,user_unit,max_objects=5000):
    """Read exact path definitions in page millimetres, including nested Forms."""
    import ctypes as ct
    import pypdfium2.raw as native
    from .pdf_source import _matrix,_mul,_apply,_segments,_rgba
    rows=[];budget=0;factor=user_unit*25.4/72
    def point(matrix,value):return [v*factor for v in _apply(matrix,value)]
    def walk(container,parent=(1.,0.,0.,1.,0.,0.),prefix='',depth=0):
        nonlocal budget
        if depth>12:raise ValueError('PDF path Form nesting exceeds12')
        count=native.FPDFPage_CountObjects(container) if depth==0 else native.FPDFFormObj_CountObjects(container)
        getter=native.FPDFPage_GetObject if depth==0 else native.FPDFFormObj_GetObject
        if count<0:raise ValueError('PDF path object inventory unreadable')
        for index in range(count):
            budget+=1
            if budget>max_objects:raise ValueError('PDF path inventory exceeds supported object workload')
            obj=getter(container,index);kind=native.FPDFPageObj_GetType(obj)
            matrix=_mul(parent,_matrix(native,obj));locator=prefix+str(index)
            if kind==native.FPDF_PAGEOBJ_FORM:walk(obj,matrix,locator+'.',depth+1)
            elif kind==native.FPDF_PAGEOBJ_PATH:
                count=native.FPDFPath_CountSegments(obj)
                paths=_segments(native,count,lambda i:native.FPDFPath_GetPathSegment(obj,i))
                fill,stroke=ct.c_int(),ct.c_int()
                if not native.FPDFPath_GetDrawMode(obj,fill,stroke):raise ValueError('PDF path paint mode unreadable')
                values=[]
                for path in paths:
                    values.append({'start_mm':point(matrix,path['start']),
                        'segments':[{'kind':segment[0],'points_mm':[point(matrix,p) for p in segment[1:]]} for segment in path['segments']],
                        'closed':path['closed']})
                rows.append({'object_path':locator,'coordinate_system':'PDF page user space, Y up, mm',
                             'stroke_enabled':bool(stroke.value),'fill_mode':fill.value,
                             'stroke_rgba':_rgba(native,obj,True),'paths':values})
    walk(page)
    return rows


def facts(path, raw=None):
    """Read actual bytes/properties, never an acceptance verdict from the producer."""
    raw=path.read_bytes() if raw is None else raw
    suffix=path.suffix.lower()
    if suffix=='.dxf':
        import ezdxf
        if raw.startswith(b'AutoCAD Binary DXF\r\n\x1a\x00'):
            from ezdxf.lldxf.tagger import binary_tags_loader
            from ezdxf.document import Drawing
            doc=Drawing.load(binary_tags_loader(raw,errors='strict'))
        else:
            from ezdxf.filemanagement import dxf_stream_info
            encoding=dxf_stream_info(io.StringIO(raw.decode('utf8',errors='ignore'),newline=None)).encoding
            doc=ezdxf.read(io.StringIO(raw.decode(encoding,errors='strict'),newline=None))
        entities=list(doc.modelspace())
        if len(entities)>5000:raise ValueError('DXF workload exceeds5000 entities; split the authorized review')
        value={'units':doc.units,'entities':[{'type':e.dxftype(),'handle':e.dxf.handle,
            'dxf':e.dxf.all_existing_dxf_attribs(),
            **({'vertices_xyseb':[list(p) for p in e.get_points('xyseb')]} if e.dxftype()=='LWPOLYLINE' else {}),
            **(dimension_facts(e,doc) if e.dxftype()=='DIMENSION' else {})} for e in entities],
            'layers':[layer.dxf.all_existing_dxf_attribs() for layer in doc.layers]}
        return json.loads(json.dumps(value,ensure_ascii=False,default=lambda v:list(v)))
    if suffix=='.pdf':
        import pypdfium2 as pdfium
        from pypdf import PdfReader
        from .delivery import _painted_widths
        reader=PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:raise ValueError('Encrypted PDF cannot be independently inspected')
        doc=pdfium.PdfDocument(raw)
        try:
            if not 1<=len(doc)<=200:raise ValueError('Unsupported PDF page workload')
            pages=[]
            for index in range(len(doc)):
                page=doc[index];text=page.get_textpage()
                user_unit=float(reader.pages[index].get('/UserUnit',1))
                if not math.isfinite(user_unit) or user_unit<=0:raise ValueError('Invalid PDF physical UserUnit')
                widths=_painted_widths(reader.pages[index],reader,user_unit)
                media=reader.pages[index].mediabox
                pages.append({'page':index+1,'size_mm':[round(float(v)*user_unit*25.4/72,6) for v in [media.width,media.height]],
                              'rotation':int(reader.pages[index].get('/Rotate',0)),
                              'text':text.get_text_range(),
                              'painted_strokes':[{'stroke_index':i,'physical_width_mm':w} for i,w in enumerate(widths)],
                              'vector_paths':pdf_path_facts(page,user_unit)})
                text.close();page.close()
            return {'pages':pages}
        finally:doc.close()
    if suffix=='.json':return {'content':json.loads(raw.decode('utf-8-sig'))}
    if suffix in {'.txt','.md','.csv','.xml','.toml','.yaml','.yml'}:
        if len(raw)>2_000_000:raise ValueError('Text workload exceeds2MB')
        return {'text':raw.decode('utf-8-sig')}
    if suffix in {'.png','.jpg','.jpeg','.webp'}:
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as image:return {'size_pixels':list(image.size),'mode':image.mode,'format':image.format}
    raise ValueError('Unsupported original source format; no guessed readback')


class Evidence:
    """The CLI cannot supply paths: every operation selects a locked file ID."""
    def __init__(self, packet_path, lock_path, output):
        self.packet=Path(packet_path).resolve(strict=True)
        self.output=Path(output).resolve(strict=True)
        self.lock_path=Path(lock_path).resolve(strict=True)
        if not self.lock_path.is_relative_to(self.output):raise ValueError('Lock must be inside the owned evidence directory')
        self.lock_hash=digest(self.lock_path)
        self.lock=json.loads(self.lock_path.read_text(encoding='utf8'))
        if self.lock.get('schema_version')!=1 or self.lock.get('packet_path')!=str(self.packet):raise ValueError('Wrong packet lock')
        self.packet_hash=self.lock['packet_sha256']
        from .review_runner import validate_native_evidence
        packet=json.loads(self.packet.read_text(encoding='utf8'))
        self.native=validate_native_evidence(packet,self.packet.parent)['bindings']
        self.records={r['file_id']:r for r in self.lock['files']}
        if len(self.records)!=len(self.lock['files']):raise ValueError('Duplicate locked file IDs')
        original={r['file_id']:r for r in original_records(self.packet)}
        if set(original)!=set(self.records):raise ValueError('Evidence lock changed the original source inventory')
        for fid,record in self.records.items():
            if {k:record.get(k) for k in ('file_id','category','path','sha256','native_artifact_id')}!={k:original[fid].get(k) for k in ('file_id','category','path','sha256','native_artifact_id')}:
                raise ValueError('Evidence lock changed an original source identity')
            if any(row.get('source_sha256')!=record['sha256'] for row in record['previews']):
                raise ValueError('Preview is not bound to the locked original source')
        self.audit=self.output/'evidence-access.jsonl'
        self._check()
        # Keep the exclusively created handle: a later path/symlink swap cannot
        # redirect this service's writes into another user's file.
        self._audit_stream=self.audit.open('x',encoding='utf8')

    def close(self):
        self._audit_stream.close()

    def _check(self, file_id=None):
        if digest(self.lock_path)!=self.lock_hash or digest(self.packet)!=self.packet_hash:
            raise ValueError('Packet or evidence lock changed')
        if file_id is None:return None
        if file_id not in self.records:raise ValueError('Unknown authorized file ID')
        record=self.records[file_id];path=Path(record['path'])
        if path.resolve(strict=True)!=path or not path.is_relative_to(self.packet.parent):
            raise ValueError('Original path escaped its locked source directory')
        if digest(path)!=record['sha256']:raise ValueError('Original source hash changed')
        aid=record.get('native_artifact_id')
        if aid is not None:
            binding=self.native[aid];snapshot=binding['snapshot'];preview=snapshot['correspondence_preview']
            for source,expected in [(binding['snapshot_path'],binding['snapshot_file_sha256']),
                    (Path(snapshot['path']),snapshot['file_sha256']),
                    (binding['source_path'],preview['source_file_sha256']),
                    (binding['preview_path'],binding['preview_sha256'])]:
                if source.resolve(strict=True)!=source or digest(source)!=expected:
                    raise ValueError('Bound native evidence dependency changed')
        return record

    def _native_facts(self,aid):
        binding=self.native[aid];snapshot=binding['snapshot']
        return {'readback_mode':'main_mcp_bound_native_facts','offline_dwg_parsed':False,
            'live_context_provided':False,'live_final_revalidation_required':True,
            'native_file_sha256':snapshot['file_sha256'],'native_fact_digest':snapshot['snapshot_sha256'],
            'snapshot_file_sha256':binding['snapshot_file_sha256'],
            'document_token':snapshot['document_token'],'provenance':snapshot['provenance'],
            'lifecycle':snapshot.get('lifecycle'),'raw_native_facts':snapshot['facts'],
            'preview_kind':'native_source_correspondence','preview_is_native_export':False,
            'preview_is_native_paper_plot':False,'source_artifact_id':binding['source_artifact_id']}

    def _result(self, operation, record, body, *,preview=None):
        response={'ok':True,'operation':operation,'file_id':record['file_id'],
            'source_sha256':record['sha256'],'packet_sha256':self.packet_hash,
            'record_id':str(uuid.uuid4()),**body}
        if preview is not None:response['preview']=preview
        serialized=encoded(response)
        audit={'record_id':response['record_id'],'operation':operation,'file_id':record['file_id'],
            'source_sha256':record['sha256'],'packet_sha256':self.packet_hash,
            'response_sha256':hashlib.sha256(serialized.encode('utf8')).hexdigest()}
        if preview is not None:audit['preview']=preview
        # Only the service writes this append-only run-local evidence stream.
        self._audit_stream.write(encoded(audit)+'\n');self._audit_stream.flush()
        return response

    def inventory(self):
        self._check()
        return {'ok':True,'packet_sha256':self.packet_hash,'files':[
            {'file_id':r['file_id'],'category':r['category'],'sha256':r['sha256'],
             'format':Path(r['path']).suffix.lower().lstrip('.'),
             'preview_indices':list(range(len(r['previews'])))} for r in self.records.values()],
            'acceptance_verdict_provided':False}

    def read(self,file_id):
        record=self._check(file_id)
        raw=Path(record['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=record['sha256']:raise ValueError('Original changed during read')
        aid=record.get('native_artifact_id')
        if aid is not None:
            data=self._native_facts(aid)
            if record['category']=='native_capture':
                # The complete raw facts are read under artifact:dwg; this
                # separate source read proves the capture file/hash/provenance
                # without returning a second large copy or producer pass flags.
                data.pop('raw_native_facts')
        else:data=facts(Path(record['path']),raw)
        self._check(file_id)
        return self._result('read',record,{'facts':data})

    def view(self,file_id,preview_index):
        record=self._check(file_id)
        if type(preview_index) is not int or not 0<=preview_index<len(record['previews']):
            raise ValueError('Unknown authorized preview index')
        preview=record['previews'][preview_index]
        path=Path(preview['path'])
        if path.resolve(strict=True)!=path or not (path.is_relative_to(self.output) or path==Path(record['path'])):
            raise ValueError('Preview escaped its locked input/output directory')
        if digest(path)!=preview['sha256']:raise ValueError('Preview hash changed')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=preview['sha256']:raise ValueError('Preview changed during read')
        self._check(file_id)
        preview_metadata={'index':preview_index,'sha256':preview['sha256']}
        if record.get('native_artifact_id') is not None:
            preview_metadata.update(kind='native_source_correspondence',native_export=False,native_paper_plot=False)
        metadata=self._result('view',record,{},preview=preview_metadata)
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as image:mime=Image.MIME.get(image.format)
        if mime not in {'image/png','image/jpeg','image/webp'}:raise ValueError('Unsupported image MIME')
        return metadata,types.ImageContent(type='image',mimeType=mime,data=base64.b64encode(raw).decode('ascii'))


def create_server(evidence):
    server=Server(SERVER_NAME)

    @server.list_tools()
    async def list_tools():
        readonly=types.ToolAnnotations(readOnlyHint=True,destructiveHint=False,openWorldHint=False)
        return [types.Tool(name='review_inventory',description='List only IDs of the immutable original customer materials and actual artifacts; no arbitrary paths.',annotations=readonly,
            inputSchema={'type':'object','properties':{},'additionalProperties':False}),
            types.Tool(name='review_read',description='Read actual original facts for one authorized file ID; recheck its SHA256 on each read. No drawing, command or acceptance verdict.',annotations=readonly,
            inputSchema={'type':'object','properties':{'file_id':{'type':'string'}},'required':['file_id'],'additionalProperties':False}),
            types.Tool(name='review_view',description='Return the actual image for a locked source/preview ID and index, plus its source and image hashes.',annotations=readonly,
            inputSchema={'type':'object','properties':{'file_id':{'type':'string'},'preview_index':{'type':'integer','minimum':0}},'required':['file_id','preview_index'],'additionalProperties':False})]

    @server.call_tool()
    async def call_tool(name,arguments):
        args=arguments or {}
        if name=='review_inventory' and not args:response=evidence.inventory();image=None
        elif name=='review_read' and set(args)=={'file_id'}:response=evidence.read(args['file_id']);image=None
        elif name=='review_view' and set(args)=={'file_id','preview_index'}:
            response,image=evidence.view(args['file_id'],args['preview_index'])
        else:raise ValueError('Only the three declared read-only tool schemas are authorized')
        blocks=[types.TextContent(type='text',text=encoded(response))]
        if image is not None:blocks.append(image)
        return types.CallToolResult(content=blocks,isError=False)
    return server


async def serve(packet_path,lock_path,output):
    evidence=Evidence(packet_path,lock_path,output);server=create_server(evidence)
    try:
        async with stdio_server() as (read,write):
            await server.run(read,write,server.create_initialization_options())
    finally:evidence.close()


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet',type=Path,required=True)
    parser.add_argument('--lock',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    # Load native numerical/PDF libraries before stdio's background threads start.
    # Importing NumPy's Windows extension while those threads are active can block
    # the loader; this is startup preparation, not a source or CAD operation.
    import importlib
    for dependency in ('ezdxf','pypdfium2','PIL.Image','luomu_cad.delivery','luomu_cad.pdf_source'):importlib.import_module(dependency)
    asyncio.run(serve(args.packet,args.lock,args.output))


if __name__=='__main__':main()
