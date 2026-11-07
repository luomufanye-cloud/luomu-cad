"""Windows AutoCAD adapter, instantiated only inside the MCP server worker.

Uses documented ActiveX methods. Explicit start and SaveAs are separate from
read-only attach; no raw command or desktop-control route.
"""
import math
import os
import time
from pathlib import Path
from .storage import ROOT, Journal, digest, workspace_lock

DIMENSION_STYLE_FIELDS={'TextHeight','ArrowheadSize','TextGap','ExtensionLineOffset',
                        'ExtensionLineExtend','ScaleFactor','LinearScaleFactor'}
FRAME_FIELDS=('FRAME','IMAGEFRAME','DWFFRAME','PDFFRAME','DGNFRAME','XCLIPFRAME','WIPEOUTFRAME')


def vector(values):
    if not isinstance(values,(list,tuple)) or len(values) not in (2,3):
        raise ValueError("Coordinate requires 2 or 3 components")
    values=list(values)+([0.] if len(values)==2 else [])
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e9 for v in values):
        raise ValueError("Coordinates must be finite")
    return tuple(float(v) for v in values)


def _validate_progid(progid):
    if not isinstance(progid,str) or not (progid=='AutoCAD.Application' or
        (progid.startswith('AutoCAD.Application.') and all(p.isdigit() for p in progid.split('.')[2:]))):
        raise ValueError('Invalid AutoCAD ProgID')


def _retry_rejected(call,timeout=45):
    """Retry explicit RPC rejection or pywin32's pre-call member lookup failure.

    Callers wrap one COM step, never an entire create/export/save transaction.
    Dynamic __getattr__ swallows GetIDsOfNames RPC errors and raises AttributeError
    before the requested method is invoked; ordinary Python AttributeError is not
    a retryable transport condition.
    """
    deadline=time.monotonic()+timeout
    delay=.1
    while True:
        try:return call()
        except Exception as exc:
            codes=[getattr(exc,'hresult',None)]
            info=getattr(exc,'excepinfo',None)
            if isinstance(info,(list,tuple)) and len(info)>5:codes.append(info[5])
            rejected=any(isinstance(code,int) and (code&0xffffffff) in {0x80010001,0x8001010A} for code in codes)
            if isinstance(exc,AttributeError):
                frame=exc.__traceback__
                while frame and frame.tb_next:frame=frame.tb_next
                if frame:
                    code=frame.tb_frame.f_code
                    rejected=(code.co_name=='__getattr__' and
                              code.co_filename.replace('\\','/').lower().endswith('/win32com/client/dynamic.py'))
            if not rejected or time.monotonic()>=deadline:raise
            time.sleep(min(delay,max(0,deadline-time.monotonic())))
            delay=min(1.,delay*2)


def _ready_document(doc,timeout=45):
    """Refresh early-bound COM metadata after Add/Open or an active-tab change.

    AutoCAD can return an IDispatch before its document type information is ready.
    Pywin32 then caches a wrapper named Add/<unknown> with missing members. Only
    that read-only initialization phase is retried; Add/Open is never repeated.
    """
    if not hasattr(doc,'_oleobj_'):return doc
    from win32com.client import dynamic
    deadline=time.monotonic()+timeout
    while True:
        try:
            ready=_retry_rejected(lambda:dynamic.Dispatch(doc._oleobj_,userName='AcadDocument'))
            _retry_rejected(lambda:(str(ready.Name),str(ready.FullName),int(ready.HWND),ready.GetVariable('INSUNITS')))
            return ready
        except AttributeError as exc:
            member=str(exc).rsplit('.',1)[-1]
            if member not in {'Name','FullName','HWND','GetVariable'} or time.monotonic()>=deadline:raise
            time.sleep(.2)


def _ready_documents(collection,timeout=45):
    """Refresh read-only collection metadata after a document has closed."""
    if not hasattr(collection,'_oleobj_'):return collection
    from win32com.client import dynamic
    deadline=time.monotonic()+timeout
    while True:
        try:
            ready=_retry_rejected(lambda:dynamic.Dispatch(collection._oleobj_,userName='AcadDocuments'))
            _retry_rejected(lambda:(int(ready.Count),getattr(ready,'Item')))
            return ready
        except AttributeError as exc:
            if str(exc).rsplit('.',1)[-1] not in {'Count','Item'} or time.monotonic()>=deadline:raise
            time.sleep(.2)


def _wmf_drawing_records(data):
    """Count drawable WMF records; palette-only files are not valid previews."""
    import struct
    offset=22 if data[:4]==b'\xd7\xcd\xc6\x9a' else 0
    if len(data)<offset+18:raise ValueError('Truncated WMF header')
    header_words=struct.unpack_from('<H',data,offset+2)[0]
    if header_words!=9:raise ValueError('Invalid WMF header size')
    offset+=18;count=0
    drawing={0x0213,0x0324,0x0325,0x0538,0x0418,0x041b,0x061c,0x0817,
             0x081a,0x0830,0x0521,0x0a32,0x041f,0x0940,0x0b41,0x0f43,0x0922,0x0b23}
    while offset+6<=len(data):
        words,kind=struct.unpack_from('<IH',data,offset)
        if words<3 or offset+words*2>len(data):raise ValueError('Invalid WMF record extent')
        if kind in drawing:count+=1
        offset+=words*2
        if kind==0:return count
    raise ValueError('WMF end record missing')


class CAD:
    def __init__(self,root=None,attach=None,launcher=None):
        self.app=None
        self.document=None
        self.bound_token=None
        self.attach=attach
        self.launcher=launcher
        self.com_initialized=False
        self.root=root or ROOT/"runtime/live-operations"
        self.journal=Journal(self.root)
        # Ownership exists only for documents opened/created by this server session.
        self.owned_documents=[]

    def _explicit_document_action(self,explicit_request):
        if explicit_request is not True:raise ValueError('Explicit document action required')
        if os.environ.get('LUOMU_CAD_LIVE_WRITES')!='1':raise ValueError('LIVE_WRITES_DISABLED')
        if self.app is None:self.app=self.application()
        count=_retry_rejected(lambda:self._document_collection().Count)
        if count and _retry_rejected(lambda:self._active_document().GetVariable('CMDNAMES')):
            raise ValueError('CAD_BUSY: no command cancellation attempted')

    def _active_document(self):
        return _ready_document(_retry_rejected(lambda:self.app.ActiveDocument))

    def _document_collection(self):
        return _ready_documents(_retry_rejected(lambda:self.app.Documents))

    def _application_version(self):
        try:
            version=_retry_rejected(lambda:self.app.Version,timeout=2)
            return str(version) if version is not None else None
        except Exception:
            # Optional identity metadata must not turn a completed start into a failure.
            return None

    def _bind(self,doc):
        doc=_ready_document(doc)
        self.document=doc
        self.bound_token=self.identity(doc)
        if self.identity(self._active_document())!=self.bound_token:
            raise ValueError('DOCUMENT_NOT_ACTIVE')
        return _retry_rejected(lambda:{'ok':True,'document':str(doc.Name),'path':str(doc.FullName),
                'document_token':self.bound_token,'units':int(doc.GetVariable('INSUNITS')),
                'saved':bool(doc.Saved)})

    def _documents(self):
        # AutoCAD's collection enumerator can be transiently unavailable after
        # Close, even while Count/Item are valid; avoid the COM enumerator cache.
        collection=self._document_collection()
        count=_retry_rejected(lambda:collection.Count)
        return [_ready_document(_retry_rejected(lambda:collection.Item(i))) for i in range(count)]

    def _view_state(self,doc):
        def read():
            viewport=doc.ActiveViewport
            return {'direction':list(viewport.Direction),'target':list(viewport.Target),
                    'center':list(viewport.Center),'height':float(viewport.Height),'width':float(viewport.Width),
                    'twist_angle_radians':float(doc.GetVariable('VIEWTWIST')),
                    'screen_size_pixels':list(doc.GetVariable('SCREENSIZE')),'tilemode':int(doc.GetVariable('TILEMODE')),
                    'frames':{name:int(doc.GetVariable(name)) for name in FRAME_FIELDS},
                    'frame_selection':int(doc.GetVariable('FRAMESELECTION')),
                    'frame_selection_type':type(doc.GetVariable('FRAMESELECTION')).__name__}
        return _retry_rejected(read)

    def _set_frame_variable(self,doc,name,value):
        if name not in (*FRAME_FIELDS,'FRAMESELECTION'):raise ValueError('Unknown preview frame setting')
        current=_retry_rejected(lambda:doc.GetVariable(name))
        if current==value:return
        import pythoncom
        import win32com.client
        if isinstance(current,bool):
            variant=win32com.client.VARIANT(pythoncom.VT_BOOL,bool(value))
        elif isinstance(current,int):
            variant=win32com.client.VARIANT(pythoncom.VT_I2,int(value))
        else:raise TypeError('Unexpected system-variable type for '+name+': '+type(current).__name__)
        _retry_rejected(lambda:doc.SetVariable(name,variant))
        if int(_retry_rejected(lambda:doc.GetVariable(name)))!=int(value):
            raise RuntimeError('FRAME_SETTING_READBACK_FAILED: '+name)

    def _document_checkpoint(self,operation_id,doc,owned):
        checkpoint=_retry_rejected(lambda:{'document_token':self.identity(doc),
            'document_window':int(doc.HWND),'application_window':int(self.app.HWND),
            'owned':owned,'path':str(doc.FullName),'name':str(doc.Name)})
        self.journal.set(operation_id,{'checkpoint':checkpoint})

    def _resume_document(self,operation_id,request):
        old=self.journal.get(operation_id)
        if old is None:return None
        if old.get('request_hash')!=digest(request):
            raise ValueError('JOB_CONFLICT: job_id was used with different inputs')
        checkpoint=old.get('checkpoint')
        if old.get('status')!='started' or not checkpoint:return None
        if int(_retry_rejected(lambda:self.app.HWND))!=checkpoint['application_window']:
            raise ValueError('RECOVERY_APPLICATION_CHANGED')
        matches=[d for d in self._documents() if self.identity(d)==checkpoint['document_token']
                 and int(_retry_rejected(lambda:d.HWND))==checkpoint['document_window']]
        if len(matches)!=1:raise ValueError('RECOVERY_DOCUMENT_CHANGED')
        doc=matches[0]
        if _retry_rejected(lambda:doc.GetVariable('CMDNAMES')):raise ValueError('CAD_BUSY: recovery does not cancel commands')
        _retry_rejected(lambda:doc.Activate())
        if checkpoint['owned'] and not self._owned(doc):self.owned_documents.append(doc)
        return doc,checkpoint

    def _owned(self,doc):
        for owned in self.owned_documents:
            if owned is doc:return True
            # COM wrappers can differ after enumerating Documents; compare IUnknown.
            if hasattr(owned,'_oleobj_') and hasattr(doc,'_oleobj_') and owned._oleobj_==doc._oleobj_:
                return True
        return False

    def new_document(self,operation_id,explicit_request=False,units=4,template=None):
        if isinstance(units,bool) or not isinstance(units,int) or not 0<=units<=24:
            raise ValueError('INSUNITS must be an integer in 0..24')
        if template is not None:
            candidate=Path(template)
            if not candidate.is_absolute() or candidate.suffix.lower()!='.dwt' or not candidate.is_file():
                raise ValueError('Template must be an existing absolute local .dwt path')
            template=str(candidate.resolve())
        self._explicit_document_action(explicit_request)
        request={'operation':'new_document','units':units,'template':template}
        with workspace_lock(self.root):
            resumed=self._resume_document(operation_id,request)
            fresh,old=(True,{}) if resumed else self.journal.begin(operation_id,request)
            if not fresh:
                matches=[d for d in self._documents() if self.identity(d)==old['document_token']]
                if len(matches)!=1:raise ValueError('CREATED_DOCUMENT_NO_LONGER_OPEN')
                return {**old,'replayed':True}
            # Documents.Add's optional template is resolved by AutoCAD itself.
            if resumed:doc=resumed[0]
            else:
                collection=self._document_collection()
                doc=_retry_rejected(lambda:collection.Add(template) if template else collection.Add())
                self.journal.set(operation_id,{'phase':'document_returned_awaiting_identity',
                    'application_window':int(_retry_rejected(lambda:self.app.HWND))})
                doc=_ready_document(doc)
                self.owned_documents.append(doc)
                self._document_checkpoint(operation_id,doc,True)
            _retry_rejected(lambda:doc.SetVariable('INSUNITS',units))
            result={**self._bind(doc),'operation_id':operation_id,'created':True,'template':template,'resumed':bool(resumed)}
            self.journal.set(operation_id,{'status':'completed','result':result})
            return result

    def open_document(self,operation_id,path,explicit_request=False,read_only=False):
        target=Path(path)
        if not target.is_absolute() or target.suffix.lower() not in {'.dwg','.dxf'} or not target.is_file():
            raise ValueError('Existing absolute local DWG/DXF path required')
        if not isinstance(read_only,bool):raise ValueError('read_only must be boolean')
        target=target.resolve()
        self._explicit_document_action(explicit_request)
        request={'operation':'open_document','path':str(target),'read_only':read_only}
        with workspace_lock(self.root):
            resumed=self._resume_document(operation_id,request)
            fresh,old=(True,{}) if resumed else self.journal.begin(operation_id,request)
            if not fresh:
                matches=[d for d in self._documents() if self.identity(d)==old['document_token']]
                if len(matches)!=1:raise ValueError('OPENED_DOCUMENT_NO_LONGER_OPEN')
                return {**old,'replayed':True}
            existing=_retry_rejected(lambda:[d for d in self._documents() if str(d.FullName) and Path(str(d.FullName)).resolve()==target])
            if resumed:
                doc=resumed[0]
                opened=resumed[1]['owned']
            elif existing:
                doc=existing[0]
                if _retry_rejected(lambda:bool(doc.ReadOnly))!=read_only:raise ValueError('DOCUMENT_READ_ONLY_MODE_MISMATCH')
                _retry_rejected(lambda:doc.Activate())
                opened=False
            else:
                collection=self._document_collection()
                doc=_retry_rejected(lambda:collection.Open(str(target),read_only))
                self.journal.set(operation_id,{'phase':'document_returned_awaiting_identity',
                    'application_window':int(_retry_rejected(lambda:self.app.HWND))})
                doc=_ready_document(doc)
                self.owned_documents.append(doc)
                opened=True
            if not resumed:self._document_checkpoint(operation_id,doc,opened)
            result={**self._bind(doc),'operation_id':operation_id,'opened':opened,
                    'already_open':not opened,'read_only':_retry_rejected(lambda:bool(doc.ReadOnly)),'resumed':bool(resumed)}
            if Path(result['path']).resolve()!=target:raise RuntimeError('OPENED_DOCUMENT_PATH_MISMATCH')
            self.journal.set(operation_id,{'status':'completed','result':result})
            return result

    def activate_document(self,document_name,explicit_request=False):
        if not isinstance(document_name,str) or not document_name:raise ValueError('Exact document name or path required')
        self._explicit_document_action(explicit_request)
        matches=_retry_rejected(lambda:[d for d in self._documents() if document_name in {str(d.Name),str(d.FullName)}])
        if len(matches)!=1:raise ValueError('DOCUMENT_NOT_FOUND_OR_AMBIGUOUS')
        _retry_rejected(lambda:matches[0].Activate())
        return {**self._bind(matches[0]),'activated':True}

    def close_document(self,operation_id,document_token,explicit_request=False):
        self._explicit_document_action(explicit_request)
        request={'operation':'close_document','document':document_token}
        with workspace_lock(self.root):
            recorded=self.journal.get(operation_id)
            if recorded and recorded.get('status')=='started' and recorded.get('phase')=='document_closed':
                if recorded.get('request_hash')!=digest(request):raise ValueError('JOB_CONFLICT: job_id was used with different inputs')
                remaining=self._documents()
                if any(self.identity(d)==document_token for d in remaining):raise ValueError('CLOSE_NOT_CONFIRMED')
                result={**recorded['close_result'],'remaining_documents':len(remaining),'recovered':True}
                self.journal.set(operation_id,{'status':'completed','result':result})
                return result
            if recorded:
                fresh,old=self.journal.begin(operation_id,request)
                if any(self.identity(d)==document_token for d in self._documents()):
                    raise ValueError('CLOSED_DOCUMENT_REOPENED')
                return {**old,'replayed':True}
            doc=self.state(document_token)
            if not self._owned(doc):raise ValueError('DOCUMENT_NOT_OWNED: only documents opened or created in this session may be closed')
            if not _retry_rejected(lambda:bool(doc.Saved)):raise ValueError('UNSAVED_CHANGES: save to an explicit destination before closing')
            self.journal.begin(operation_id,request)
            closed_name,closed_path=_retry_rejected(lambda:(str(doc.Name),str(doc.FullName)))
            owned=[item for item in self.owned_documents if item is not doc]
            # Saved was checked; False prevents SaveAs dialogs or accidental writes.
            _retry_rejected(lambda:doc.Close(False))
            close_result={'ok':True,'operation_id':operation_id,'closed':True,'document':closed_name,
                          'path':closed_path,'document_token':document_token}
            self.journal.set(operation_id,{'phase':'document_closed','close_result':close_result})
            self.document=None;self.bound_token=None;self.owned_documents=owned
            if any(self.identity(d)==document_token for d in self._documents()):
                raise RuntimeError('DOCUMENT_CLOSE_READBACK_FAILED')
            result={**close_result,'remaining_documents':_retry_rejected(lambda:self._document_collection().Count)}
            self.journal.set(operation_id,{'status':'completed','result':result})
            return result

    def preview(self,operation_id,document_token,path):
        target=Path(path)
        if not target.is_absolute() or target.suffix.lower() not in {'.wmf','.bmp'}:raise ValueError('Absolute .wmf or .bmp destination required')
        format_name=target.suffix.lower()[1:]
        target=target.resolve()
        if not target.parent.is_dir():raise ValueError('Destination parent must already exist')
        doc=self.state(document_token)
        if _retry_rejected(lambda:doc.GetVariable('CMDNAMES')):raise ValueError('CAD_BUSY: no command cancellation attempted')
        request={'operation':'preview','document':document_token,'path':str(target)}
        with workspace_lock(self.root):
            if self.journal.get(operation_id):
                fresh,old=self.journal.begin(operation_id,request)
                if not target.is_file() or __import__('hashlib').sha256(target.read_bytes()).hexdigest()!=old['sha256']:
                    raise ValueError('PREVIEW_ARTIFACT_CHANGED')
                return {**old,'replayed':True}
            if target.exists():raise ValueError('Destination exists; no overwrite attempted')
            if not 1<=_retry_rejected(lambda:doc.ModelSpace.Count)<=100000:raise ValueError('Preview requires 1..100000 model-space entities')
            view_before=self._view_state(doc)
            if view_before['tilemode']!=1:raise ValueError('MODEL_VIEW_REQUIRED: activate a model-space viewport before preview')
            self.journal.begin(operation_id,request)
            import pythoncom
            import win32com.client
            selection=_retry_rejected(lambda:doc.SelectionSets.Add('LUOMU_'+digest(request)[:20]))
            zoom_steps=0
            try:
                # Change only the clip-frame switch. FRAME itself would overwrite
                # every underlay/image/wipeout frame setting in the document.
                self._set_frame_variable(doc,'XCLIPFRAME',0)
                # Hidden clip frames can reappear when WMF/BMP export selects
                # their owners. Disable selectable hidden frames for this export.
                self._set_frame_variable(doc,'FRAMESELECTION',0)
                items=_retry_rejected(lambda:[doc.ModelSpace.Item(i) for i in range(doc.ModelSpace.Count)])
                _retry_rejected(lambda:selection.AddItems(win32com.client.VARIANT(pythoncom.VT_ARRAY|pythoncom.VT_DISPATCH,items)))
                # WMF uses viewport graphics; an unregenerated off-screen drawing
                # can otherwise produce a palette-only file with no geometry.
                _retry_rejected(lambda:self.app.ZoomExtents());zoom_steps+=1
                # Extents alone can clip glyphs at the viewport edge in WMF.
                _retry_rejected(lambda:self.app.ZoomScaled(.9,1));zoom_steps+=1
                _retry_rejected(lambda:doc.Regen(0))
                view_export=self._view_state(doc)
                _retry_rejected(lambda:doc.Export(str(target.with_suffix('')),format_name,selection))
            finally:
                # Delete removes only the temporary selection set, never its entities.
                try:_retry_rejected(lambda:selection.Delete())
                finally:
                    try:
                        for _ in range(zoom_steps):_retry_rejected(lambda:self.app.ZoomPrevious())
                    finally:
                        self._set_frame_variable(doc,'XCLIPFRAME',view_before['frames']['XCLIPFRAME'])
                        self._set_frame_variable(doc,'FRAMESELECTION',view_before['frame_selection'])
                        # FRAME=3 is a derived mixed-setting value; restore a
                        # uniform master value only if no subordinate changed.
                        restored={name:int(_retry_rejected(lambda:doc.GetVariable(name))) for name in FRAME_FIELDS}
                        if all(restored[name]==view_before['frames'][name] for name in FRAME_FIELDS if name!='FRAME'):
                            if restored['FRAME']!=view_before['frames']['FRAME'] and view_before['frames']['FRAME'] in (0,1,2):
                                self._set_frame_variable(doc,'FRAME',view_before['frames']['FRAME'])
            view_after=self._view_state(doc)
            if view_after['frames']!=view_before['frames']:raise RuntimeError('NATIVE_FRAME_RESTORE_FAILED')
            if view_after['frame_selection']!=view_before['frame_selection']:raise RuntimeError('NATIVE_FRAME_SELECTION_RESTORE_FAILED')
            for key in ('direction','target','center','height','width','twist_angle_radians'):
                before,after=view_before[key],view_after[key]
                if not isinstance(before,list):before,after=[before],[after]
                if len(before)!=len(after) or any(not math.isclose(a,b,rel_tol=1e-7,abs_tol=1e-7) for a,b in zip(before,after)):
                    raise RuntimeError('NATIVE_VIEW_RESTORE_FAILED: '+key)
            data=target.read_bytes()
            details={}
            if format_name=='wmf':
                if len(data)<18 or not (data[:4]==b'\xd7\xcd\xc6\x9a' or data[:6] in (b'\x01\x00\x09\x00\x00\x03',b'\x02\x00\x09\x00\x00\x03')):
                    raise RuntimeError('NATIVE_PREVIEW_FORMAT_INVALID')
                drawing_records=_wmf_drawing_records(data)
                if not drawing_records:raise RuntimeError('NATIVE_PREVIEW_EMPTY: WMF contains no drawable records')
                details['drawing_records']=drawing_records
            else:
                from PIL import Image
                with Image.open(target) as bitmap:
                    if bitmap.format!='BMP':raise RuntimeError('NATIVE_PREVIEW_FORMAT_INVALID')
                    pixels=bitmap.convert('RGB')
                    if all(low==high for low,high in pixels.getextrema()):raise RuntimeError('NATIVE_PREVIEW_EMPTY: BMP contains one solid color')
                    details['pixel_size']=list(bitmap.size)
            result={'ok':True,'operation_id':operation_id,'path':str(target),'document_token':document_token,
                    'sha256':__import__('hashlib').sha256(data).hexdigest(),'format':format_name,
                    'native_preview':True,'entity_count':len(items),**details,'view_restored':True,
                    'view_before':view_before,'view_export':view_export,'view_after':view_after}
            self.journal.set(operation_id,{'status':'completed','result':result})
            return result

    def start(self,operation_id,explicit_request=False,progid='AutoCAD.Application'):
        _validate_progid(progid)
        if explicit_request is not True:raise ValueError('Explicit application-start task required')
        if os.environ.get('LUOMU_CAD_LIVE_WRITES')!='1':raise ValueError('LIVE_WRITES_DISABLED')
        with workspace_lock(self.root):
            # application validates the ProgID and only attempts read-only attach.
            try:app=self.app if self.app is not None else self.application(progid)
            except Exception as exc:
                if getattr(exc,'hresult',None)!=-2147221021:raise
                app=None
            fresh,old=self.journal.begin(operation_id,{'operation':'start','progid':progid})
            if not fresh:
                if app is None:raise ValueError('STARTED_INSTANCE_NO_LONGER_RUNNING')
                if int(_retry_rejected(lambda:app.HWND))!=old['window']:raise ValueError('STARTED_INSTANCE_CHANGED')
                return {**old,'replayed':True}
            started=False
            if app is None:
                if self.launcher:app=self.launcher(progid)
                else:
                    import win32com.client
                    app=win32com.client.DispatchEx(progid)
                # Retain this exact instance before waiting for initialization.
                self.app=app
                _retry_rejected(lambda:setattr(app,'Visible',True));started=True
            # Bind only the application; document selection remains explicit.
            self.app=app
            if started:self.document=None;self.bound_token=None
            result={'ok':True,'cad_started':started,'already_running':not started,
                    'window':int(_retry_rejected(lambda:app.HWND)),'progid':progid,'operation_id':operation_id,
                    'application_version':self._application_version()}
            self.journal.set(operation_id,{'status':'completed','result':result})
            return result

    def save_as(self,operation_id,document_token,path):
        target=Path(path)
        if not target.is_absolute() or target.suffix.lower()!='.dwg':raise ValueError('Absolute .dwg destination required')
        target=target.resolve()
        if not target.parent.is_dir():raise ValueError('Destination parent must already exist')
        request={'operation':'save_as','document':document_token,'path':str(target)}
        with workspace_lock(self.root):
            old=self.journal.get(operation_id)
            if old:
                fresh,result=self.journal.begin(operation_id,request)
                if result['sha256']!=__import__('hashlib').sha256(target.read_bytes()).hexdigest():raise ValueError('SAVED_ARTIFACT_CHANGED')
                self.state(result['document_token'])
                return {**result,'replayed':True}
            doc=self.state(document_token,write=True)
            if target.exists():raise ValueError('Destination exists; no overwrite attempted')
            self.journal.begin(operation_id,request)
            # ActiveX SaveAs changes the document name, so refresh the token afterward.
            _retry_rejected(lambda:doc.SaveAs(str(target)))
            data=target.read_bytes()
            if len(data)<6 or data[:2]!=b'AC' or not data[2:6].isdigit():raise RuntimeError('DWG_HEADER_READBACK_FAILED')
            if Path(_retry_rejected(lambda:doc.FullName)).resolve()!=target:raise RuntimeError('DWG_DOCUMENT_PATH_MISMATCH')
            self.bound_token=self.identity(doc)
            result={'ok':True,'operation_id':operation_id,'path':str(target),
                    'sha256':__import__('hashlib').sha256(data).hexdigest(),'document_token':self.bound_token,
                    'source_document_token':document_token,'native_format_signature':data[:6].decode('ascii')}
            self.journal.set(operation_id,{'status':'completed','result':result})
            return result

    def versions(self):
        if os.name!="nt":
            return {"ok":True,"versions":[],"platform":"non-Windows"}
        import winreg
        found=[]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,"") as key:
            index=0
            while True:
                try:
                    name=winreg.EnumKey(key,index)
                except OSError:
                    break
                index+=1
                if name=="AutoCAD.Application" or name.startswith("AutoCAD.Application."):
                    found.append(name)
        return {"ok":True,"versions":sorted(found),"running_not_implied":True}

    def application(self,progid="AutoCAD.Application"):
        _validate_progid(progid)
        if self.attach:
            return self.attach(progid)
        if os.name!="nt":
            raise RuntimeError("CAD_UNAVAILABLE: live AutoCAD requires Windows")
        import pythoncom
        import win32com.client
        if not self.com_initialized:
            pythoncom.CoInitialize()
            self.com_initialized=True
        # GetActiveObject attaches only; it cannot launch the application.
        return _retry_rejected(lambda:win32com.client.GetActiveObject(progid))

    def identity(self,doc):
        return _retry_rejected(lambda:digest({"window":int(self.app.HWND),
            "document_window":int(getattr(doc,'HWND',0)),"document":str(doc.FullName or doc.Name)}))

    def connect(self,document_name=None,progid="AutoCAD.Application"):
        _validate_progid(progid)
        if self.app is None:self.app=self.application(progid)
        active=self._active_document()
        if document_name and document_name not in {str(active.Name),str(active.FullName)}:
            raise ValueError("DOCUMENT_MISMATCH: requested drawing is not active; no tab switch attempted")
        self.document=active
        self.bound_token=self.identity(active)
        return {"ok":True,"connected":True,"document":str(active.Name),"path":str(active.FullName),"document_token":self.bound_token,
                "units":int(active.GetVariable("INSUNITS")),"commands":str(active.GetVariable("CMDNAMES")),"writes_enabled":os.environ.get("LUOMU_CAD_LIVE_WRITES")=="1",
                'application_version':self._application_version()}

    def state(self,token=None,write=False):
        if self.document is None:
            raise RuntimeError("CAD_NOT_CONNECTED: call cad_connect")
        if self.identity(self._active_document())!=self.bound_token:
            raise ValueError("DOCUMENT_CHANGED: reconnect and read before continuing")
        if token is not None and token!=self.bound_token:
            raise ValueError("DOCUMENT_TOKEN_MISMATCH")
        if write:
            if os.environ.get("LUOMU_CAD_LIVE_WRITES")!="1":
                raise ValueError("LIVE_WRITES_DISABLED")
            if token!=self.bound_token:
                raise ValueError("Writes require the current document token")
            if _retry_rejected(lambda:getattr(self.document,'ReadOnly',False)):
                raise ValueError('DOCUMENT_READ_ONLY')
            if _retry_rejected(lambda:self.document.GetVariable("CMDNAMES")):
                raise ValueError("CAD_BUSY: no command cancellation attempted")
        return self.document

    def list_documents(self,progid="AutoCAD.Application"):
        _validate_progid(progid)
        if self.app is None:self.app=self.application(progid)
        return {"ok":True,"documents":[{"name":str(d.Name),"path":str(d.FullName)} for d in self._documents()]}

    def performance_snapshot(self, document_token):
        """Read bounded diagnostic data; no regeneration, selection or setting writes."""
        doc=self.state(document_token)
        started=time.monotonic()
        variables={};unavailable={}
        for name in ('INSUNITS','CMDACTIVE','CMDNAMES','GFXDX12','LINESMOOTHING','OSMODE',
                     'SELECTIONPREVIEW','SELECTIONEFFECT','PREVIEWFILTER','HPQUICKPREVIEW',
                     'COMMANDPREVIEW','ROLLOVERTIPS','UCSDETECT','VTENABLE'):
            try:variables[name]=_retry_rejected(lambda:doc.GetVariable(name),timeout=2)
            except Exception as exc:unavailable[name]=type(exc).__name__+': '+str(exc)
        result={'ok':True,'document_token':self.bound_token,
                'document_path':str(_retry_rejected(lambda:doc.FullName)),
                'saved':bool(_retry_rejected(lambda:doc.Saved)),
                'modelspace_objects':int(_retry_rejected(lambda:doc.ModelSpace.Count)),
                'variables':variables,'unavailable':unavailable,
                'read_seconds':time.monotonic()-started,'settings_changed':False,
                'interaction_recovery_accepted':False,'root_cause_verified':False}
        # A user tab switch during the reads invalidates the snapshot.
        self.state(document_token)
        return result

    def read(self,offset=0,limit=20,document_token=None):
        if isinstance(offset,bool) or not isinstance(offset,int) or offset<0 or not isinstance(limit,int) or not 1<=limit<=200:
            raise ValueError("offset>=0 and limit 1..200 required")
        doc=self.state(document_token)
        model=_retry_rejected(lambda:doc.ModelSpace)
        result=[]
        for i in range(offset,min(model.Count,offset+limit)):
            entity=_retry_rejected(lambda:model.Item(i))
            item=_retry_rejected(lambda:{"handle":str(entity.Handle),"type":str(entity.ObjectName),"layer":str(entity.Layer)})
            for key in ("StartPoint","EndPoint","Center","InsertionPoint","Coordinates","Radius","StartAngle","EndAngle","TextString","Measurement","Closed",*sorted(DIMENSION_STYLE_FIELDS)):
                try:
                    value=getattr(entity,key)
                    if isinstance(value,(tuple,list)):
                        value=list(value)
                    if isinstance(value,(list,str,int,float,bool)):
                        item[key]=value
                except Exception:
                    pass
            result.append(item)
        return {"ok":True,"document_token":self.bound_token,"entities":result,"total":model.Count,"next_offset":offset+len(result) if offset+len(result)<model.Count else None}

    def mutate(self,operation_id,document_token,operation,arguments):
        # Validation precedes journal start. A started but uncommitted call is never replayed.
        doc=self.state(document_token,write=True)
        allowed={"line","circle","arc","polyline","text","dimension","properties","save"}
        if operation not in allowed:
            raise ValueError("Unsupported live operation")
        fields={"line":{"start","end","layer"},"circle":{"center","radius","layer"},"polyline":{"points","closed","layer"},"text":{"at","text","height","layer"},"dimension":{"start","end","at","layer"},"properties":{"handle","changes"},"save":set()}
        fields['arc']={'center','radius','start_angle','end_angle','layer'}
        fields['dimension'].add('style')
        if set(arguments)-fields[operation]:raise ValueError("Unexpected operation arguments")
        for key in ("start","end","center","at"):
            if key in arguments:vector(arguments[key])
        for key in ("radius","height"):
            if key in arguments and (isinstance(arguments[key],bool) or not isinstance(arguments[key],(int,float)) or not math.isfinite(arguments[key]) or arguments[key]<=0):
                raise ValueError("Positive finite radius/height required")
        required={"line":{"start","end"},"circle":{"center","radius"},"polyline":{"points"},"text":{"at","text","height"},"dimension":{"start","end","at"},"properties":{"handle","changes"},"save":set()}
        required['arc']={'center','radius','start_angle','end_angle'}
        if required[operation]-arguments.keys():raise ValueError("Missing operation arguments")
        if operation=='arc':
            for name in ('start_angle','end_angle'):
                value=arguments[name]
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('Finite arc angles in degrees required')
            if (arguments['end_angle']-arguments['start_angle'])%360==0:raise ValueError('Use circle for a full circular arc')
        if operation in {"line","dimension"} and vector(arguments["start"])==vector(arguments["end"]):
            raise ValueError("Zero length line")
        if operation=='dimension':
            style=arguments.get('style',{})
            if not isinstance(style,dict) or style.keys()-DIMENSION_STYLE_FIELDS:
                raise ValueError('Unsupported dimension style properties')
            for value in style.values():
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
                    raise ValueError('Dimension style values must be positive finite numbers')
        if operation=="polyline":
            if not isinstance(arguments["points"],list) or not 2<=len(arguments["points"])<=1000:raise ValueError("Polyline requires 2..1000 points")
            if any(vector(pt)[2]!=0 for pt in arguments["points"]):raise ValueError("Only XY polylines supported")
        if operation=="properties":
            changes=arguments["changes"]
            if not isinstance(changes,dict) or not changes or changes.keys()-{"layer","text","height","color"}:raise ValueError("Invalid property changes")
            if "height" in changes and (not isinstance(changes["height"],(int,float)) or isinstance(changes["height"],bool) or not math.isfinite(changes["height"]) or changes["height"]<=0):raise ValueError("Positive finite height required")
            if "color" in changes and (isinstance(changes["color"],bool) or not isinstance(changes["color"],int) or not 0<=changes["color"]<=256):raise ValueError("Invalid color")
            _retry_rejected(lambda:doc.HandleToObject(str(arguments["handle"])))
        layer=arguments.get("layer") or arguments.get("changes",{}).get("layer")
        if layer:
            _retry_rejected(lambda:doc.Layers.Item(str(layer)))  # Verify existing layer before any mutation.
        if operation=="save" and not doc.FullName:raise ValueError("Automatic SaveAs disabled")
        with workspace_lock(self.root):
            fresh,old=self.journal.begin(operation_id,{"document":document_token,"operation":operation,"arguments":arguments})
            if not fresh:
                if old.get("handle"):
                    entity=_retry_rejected(lambda:doc.HandleToObject(old["handle"]))
                    if str(entity.Handle)!=old["handle"]:
                        raise RuntimeError("READBACK_FAILED")
                return {**old,"replayed":True}
            import pythoncom
            import win32com.client
            def variant(values):
                return win32com.client.VARIANT(pythoncom.VT_ARRAY|pythoncom.VT_R8,values)
            def p(value):
                return variant(vector(value))
            model=_retry_rejected(lambda:doc.ModelSpace)
            entity=None
            if operation=="line":
                entity=_retry_rejected(lambda:model.AddLine(p(arguments["start"]),p(arguments["end"])))
            elif operation=="circle":
                radius=float(arguments["radius"])
                if not math.isfinite(radius) or radius<=0:
                    raise ValueError("Positive finite radius required")
                entity=_retry_rejected(lambda:model.AddCircle(p(arguments["center"]),radius))
            elif operation=="polyline":
                points=[vector(v) for v in arguments["points"]]
                if not 2<=len(points)<=1000 or any(v[2]!=0 for v in points):
                    raise ValueError("Polyline requires 2..1000 XY points")
                entity=_retry_rejected(lambda:model.AddLightWeightPolyline(variant([v for pt in points for v in pt[:2]])))
                _retry_rejected(lambda:setattr(entity,"Closed",bool(arguments.get("closed",False))))
            elif operation=='arc':
                entity=_retry_rejected(lambda:model.AddArc(p(arguments['center']),float(arguments['radius']),
                                    math.radians(arguments['start_angle']%360),math.radians(arguments['end_angle']%360)))
            elif operation=="text":
                height=float(arguments["height"])
                if not math.isfinite(height) or height<=0:
                    raise ValueError("Positive text height required")
                entity=_retry_rejected(lambda:model.AddText(str(arguments["text"]),p(arguments["at"]),height))
            elif operation=="dimension":
                entity=_retry_rejected(lambda:model.AddDimAligned(p(arguments["start"]),p(arguments["end"]),p(arguments["at"])))
                for key,value in arguments.get('style',{}).items():
                    _retry_rejected(lambda:setattr(entity,key,float(value)))
                if arguments.get('style'):_retry_rejected(lambda:entity.Update())
            elif operation=="properties":
                changes=arguments["changes"]
                mapping={"layer":"Layer","text":"TextString","height":"Height","color":"Color"}
                if not changes or set(changes)-mapping.keys():
                    raise ValueError("Only layer/text/height/color changes supported")
                entity=_retry_rejected(lambda:doc.HandleToObject(str(arguments["handle"])))
                for key,value in changes.items():
                    _retry_rejected(lambda:setattr(entity,mapping[key],value))
            elif operation=="save":
                if not doc.FullName:
                    raise ValueError("Unsaved drawing: automatic SaveAs disabled")
                _retry_rejected(lambda:doc.Save())
            result={"ok":True,"operation_id":operation_id,"operation":operation,"document_token":document_token,"handle":str(entity.Handle) if entity is not None else None}
            if entity is not None:
                if operation!="properties" and arguments.get("layer"):_retry_rejected(lambda:setattr(entity,"Layer",str(arguments["layer"])))
                readback=_retry_rejected(lambda:doc.HandleToObject(entity.Handle))
                result["entity_type"]=_retry_rejected(lambda:str(readback.ObjectName))
                if operation=='dimension' and arguments.get('style'):
                    result['dimension_style']=_retry_rejected(lambda:{key:float(getattr(readback,key)) for key in arguments['style']})
                    if any(not math.isclose(result['dimension_style'][key],float(value),rel_tol=1e-9,abs_tol=1e-9)
                           for key,value in arguments['style'].items()):raise RuntimeError('DIMENSION_STYLE_READBACK_FAILED')
            self.journal.set(operation_id,{"status":"completed","result":result})
            return result
