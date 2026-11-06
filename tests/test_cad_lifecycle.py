"""Lifecycle protocol tests; the fake document bytes are not native CAD evidence."""
from pathlib import Path
from types import ModuleType,SimpleNamespace
import sys
import pytest
from luomu_cad.cad import CAD,_retry_rejected
from luomu_cad.cad import _ready_document,_ready_documents,_wmf_drawing_records


def wmf(draw=True):
    import struct
    header=struct.pack('<HHHIHIH',1,9,0x300,0,0,0,0)
    record=struct.pack('<IHhh',5,0x0213,100,100) if draw else b''
    return header+record+struct.pack('<IH',3,0)


class Model:
    def __init__(self):self.items=[SimpleNamespace(Handle='A')]
    @property
    def Count(self):return len(self.items)
    def Item(self,index):return self.items[index]


class Selections:
    def __init__(self):self.created=[]
    def Add(self,name):
        selection=SimpleNamespace(name=name,items=[],deleted=False)
        selection.AddItems=lambda items:selection.items.extend(items)
        selection.Delete=lambda:setattr(selection,'deleted',True)
        self.created.append(selection)
        return selection


class Document:
    def __init__(self,app,name,path='',read_only=False):
        self.app=app;self.Name=name;self.FullName=path;self.ReadOnly=read_only
        self.HWND=id(self)
        self.Saved=True;self.commands='';self.units=4;self.close_calls=[]
        self.ModelSpace=Model();self.SelectionSets=Selections()
        self.regens=[]
        self.ActiveViewport=SimpleNamespace(Direction=(0.,0.,1.),Target=(0.,0.,0.),Center=(0.,0.),Height=300.,Width=600.)
        self.frames={'FRAME':3,'IMAGEFRAME':1,'DWFFRAME':2,'PDFFRAME':2,'DGNFRAME':2,'XCLIPFRAME':2,'WIPEOUTFRAME':0}
        self.frame_selection=1
    def GetVariable(self,name):return {'CMDNAMES':self.commands,'INSUNITS':self.units,'VIEWTWIST':0.,'SCREENSIZE':(1200,600),'TILEMODE':1,'FRAMESELECTION':self.frame_selection,**self.frames}[name]
    def SetVariable(self,name,value):
        if name=='INSUNITS':self.units=value;self.Saved=False
        elif name=='FRAMESELECTION':self.frame_selection=value
        elif name=='FRAME':
            assert value in (0,1,2)
            self.frames={key:value for key in self.frames}
        else:
            assert name=='XCLIPFRAME';self.frames[name]=value
            values={value for key,value in self.frames.items() if key!='FRAME'}
            self.frames['FRAME']=next(iter(values)) if len(values)==1 else 3
    def Activate(self):self.app.ActiveDocument=self
    def Close(self,save):
        self.close_calls.append(save);self.app.Documents.items.remove(self)
        self.app.ActiveDocument=self.app.Documents.items[-1] if self.app.Documents.items else None
    def SaveAs(self,path):
        Path(path).write_bytes(b'AC1032mock');self.FullName=path;self.Name=Path(path).name;self.Saved=True
    def Export(self,stem,extension,selection):
        assert selection.items
        if extension=='wmf':Path(stem+'.wmf').write_bytes(wmf())
        else:
            from PIL import Image
            image=Image.new('RGB',(30,20),'white');image.putpixel((10,10),(0,0,0));image.save(stem+'.bmp')
    def Regen(self,mode):self.regens.append(mode)


class Documents:
    def __init__(self,app):self.app=app;self.items=[];self.opens=[];self.adds=[]
    def __iter__(self):return iter(self.items)
    def Item(self,index):return self.items[index]
    @property
    def Count(self):return len(self.items)
    def Add(self,template=None):
        self.adds.append(template)
        doc=Document(self.app,'Drawing'+str(len(self.items)+1)+'.dwg')
        self.items.append(doc);doc.Activate();return doc
    def Open(self,path,read_only):
        self.opens.append((path,read_only))
        doc=Document(self.app,Path(path).name,path,read_only)
        self.items.append(doc);doc.Activate();return doc


@pytest.fixture
def environment(tmp_path,monkeypatch):
    monkeypatch.setenv('LUOMU_CAD_LIVE_WRITES','1')
    app=SimpleNamespace(HWND=98,ActiveDocument=None)
    app.views=[];app.ZoomExtents=lambda:app.views.append('extents');app.ZoomPrevious=lambda:app.views.append('previous')
    app.ZoomScaled=lambda scale,mode:app.views.append(('scaled',scale,mode))
    app.Documents=Documents(app)
    original=app.Documents.Add();original.FullName=str(tmp_path/'customer.dwg');original.Name='customer.dwg';original.Saved=False
    app.Documents.adds.clear()
    cad=CAD(tmp_path/'journal',attach=lambda _:app)
    cad.connect()
    return cad,app,original


def test_create_save_close_reopen_preserves_customer(environment,tmp_path):
    cad,app,original=environment
    new=cad.new_document('create',True,4)
    assert app.Documents.Count==2 and new['created']
    assert cad.new_document('create',True,4)['replayed'] and len(app.Documents.adds)==1
    created=app.ActiveDocument
    with pytest.raises(ValueError,match='UNSAVED_CHANGES'):cad.close_document('close',new['document_token'],True)
    target=tmp_path/'test.dwg'
    saved=cad.save_as('save',new['document_token'],str(target))
    assert cad.close_document('close',saved['document_token'],True)['closed']
    assert created.close_calls==[False] and app.Documents.Count==1
    assert cad.close_document('close',saved['document_token'],True)['replayed']
    reopened=cad.open_document('reopen',str(target),True)
    assert reopened['opened'] and cad.open_document('reopen',str(target),True)['replayed']
    assert len(app.Documents.opens)==1
    cad.close_document('close-again',reopened['document_token'],True)
    restored=cad.activate_document(original.FullName,True)
    assert app.ActiveDocument is original and not restored['saved'] and not original.close_calls


def test_existing_document_is_not_acquired_for_close(environment,tmp_path):
    cad,app,original=environment
    Path(original.FullName).write_bytes(b'AC1032customer')
    original.Saved=True
    opened=cad.open_document('existing',original.FullName,True)
    assert opened['already_open'] and not app.Documents.opens
    with pytest.raises(ValueError,match='NOT_OWNED'):cad.close_document('close',opened['document_token'],True)
    assert not original.close_calls


def test_action_gates_validation_and_busy_are_before_mutation(environment,tmp_path,monkeypatch):
    cad,app,original=environment
    with pytest.raises(ValueError,match='Explicit'):cad.new_document('denied')
    monkeypatch.delenv('LUOMU_CAD_LIVE_WRITES')
    with pytest.raises(ValueError,match='DISABLED'):cad.new_document('denied',True)
    monkeypatch.setenv('LUOMU_CAD_LIVE_WRITES','1')
    for units in [-1,True,25,4.5]:
        with pytest.raises(ValueError,match='INSUNITS'):cad.new_document('invalid',True,units)
    with pytest.raises(ValueError,match='Template'):cad.new_document('template',True,4,'https://untrusted/template.dwt')
    with pytest.raises(ValueError,match='Existing absolute'):cad.open_document('path','relative.dwg',True)
    original.commands='LINE'
    with pytest.raises(ValueError,match='CAD_BUSY'):cad.new_document('busy',True)
    assert app.Documents.Count==1 and not app.Documents.adds
    assert not list(cad.root.glob('*.json'))


def test_explicit_template_read_only_and_same_session_instance(environment,tmp_path):
    cad,app,original=environment
    template=tmp_path/'metric.dwt';template.write_bytes(b'template')
    result=cad.new_document('template',True,4,str(template))
    assert result['template']==str(template.resolve())
    # connect/list must keep the instance selected by start rather than consult ROT again.
    cad.attach=lambda _:(_ for _ in ()).throw(AssertionError('Unexpected ROT lookup'))
    assert cad.connect()['document_token']==result['document_token']
    assert len(cad.list_documents()['documents'])==2
    source=tmp_path/'readonly.dwg';source.write_bytes(b'AC1032mock')
    opened=cad.open_document('readonly',str(source),True,True)
    assert opened['read_only']
    with pytest.raises(ValueError,match='DOCUMENT_READ_ONLY'):cad.mutate('write',opened['document_token'],'line',{'start':[0,0],'end':[1,0]})
    with pytest.raises(ValueError,match='DOCUMENT_READ_ONLY'):cad.save_as('readonly-save',opened['document_token'],str(tmp_path/'unsafe.dwg'))
    assert cad.close_document('readonly-close',opened['document_token'],True)['closed']
    assert not (tmp_path/'unsafe.dwg').exists()


def test_interrupted_open_is_not_repeated(environment,tmp_path):
    cad,app,_=environment
    source=tmp_path/'sample.dwg';source.write_bytes(b'AC1032mock')
    calls=[]
    def broken(*args):calls.append(args);raise ConnectionError('lost reply')
    app.Documents.Open=broken
    with pytest.raises(ConnectionError):cad.open_document('open',str(source),True)
    with pytest.raises(ValueError,match='WRITE_UNCERTAIN'):cad.open_document('open',str(source),True)
    assert len(calls)==1


def test_created_document_checkpoint_resumes_without_second_add(environment,monkeypatch):
    cad,app,original=environment
    bind=cad._bind
    def interrupted(_):raise ConnectionError('interrupted after Add and units')
    monkeypatch.setattr(cad,'_bind',interrupted)
    with pytest.raises(ConnectionError):cad.new_document('resume',True)
    checkpoint=cad.journal.get('resume')['checkpoint']
    assert checkpoint['owned'] and app.Documents.Count==2
    # A new MCP session recovers the exact HWND and token from its journal.
    recovered=CAD(cad.root,attach=lambda _:app)
    result=recovered.new_document('resume',True)
    assert result['resumed'] and len(app.Documents.adds)==1
    assert recovered._owned(app.ActiveDocument)
    assert not original.close_calls


def test_open_checkpoint_resumes_exact_document(environment,tmp_path,monkeypatch):
    cad,app,_=environment
    source=tmp_path/'sample.dwg';source.write_bytes(b'AC1032mock')
    monkeypatch.setattr(cad,'_bind',lambda _:(_ for _ in ()).throw(ConnectionError('readback lost')))
    with pytest.raises(ConnectionError):cad.open_document('resume-open',str(source),True)
    recovered=CAD(cad.root,attach=lambda _:app)
    assert recovered.open_document('resume-open',str(source),True)['resumed']
    assert len(app.Documents.opens)==1


def test_completed_close_recovers_a_failed_postcheck_without_closing_again(environment,tmp_path,monkeypatch):
    cad,app,_=environment
    source=tmp_path/'sample.dwg';source.write_bytes(b'AC1032mock')
    opened=cad.open_document('open-close-recovery',str(source),True)
    document=app.ActiveDocument
    monkeypatch.setattr(cad,'_documents',lambda:(_ for _ in ()).throw(AttributeError('<unknown>.Item')))
    with pytest.raises(AttributeError):cad.close_document('close-recovery',opened['document_token'],True)
    assert document.close_calls==[False]
    assert cad.journal.get('close-recovery')['phase']=='document_closed'
    recovered=CAD(cad.root,attach=lambda _:app)
    result=recovered.close_document('close-recovery',opened['document_token'],True)
    assert result['recovered'] and result['closed'] and document.close_calls==[False]


def test_native_preview_nonempty_selection_cleanup_and_no_overwrite(environment,tmp_path,monkeypatch):
    cad,app,original=environment
    com=ModuleType('pythoncom');com.VT_ARRAY=8192;com.VT_DISPATCH=9;com.VT_BOOL=11;com.VT_I2=2
    win=ModuleType('win32com');client=ModuleType('win32com.client');client.VARIANT=lambda _,v:v;win.client=client
    for name,module in [('pythoncom',com),('win32com',win),('win32com.client',client)]:monkeypatch.setitem(sys.modules,name,module)
    target=tmp_path/'native.wmf';token=cad.bound_token
    result=cad.preview('preview',token,str(target))
    assert result['native_preview'] and result['entity_count']==1
    assert result['drawing_records']==1 and app.views==['extents',('scaled',.9,1),'previous','previous']
    assert original.regens==[0]
    assert result['view_export']['direction']==[0.,0.,1.]
    assert result['view_before']==result['view_after']
    assert result['view_before']['frames']['XCLIPFRAME']==2
    assert result['view_export']['frames']['XCLIPFRAME']==0
    assert result['view_after']['frames']==original.frames
    assert result['view_export']['frame_selection']==0 and original.frame_selection==1
    assert original.SelectionSets.created[0].deleted
    assert original.ModelSpace.Count==1 and original.Saved is False
    assert cad.preview('preview',token,str(target))['replayed']
    with pytest.raises(ValueError,match='exists'):cad.preview('other',token,str(target))
    original.ModelSpace.items=[]
    with pytest.raises(ValueError,match='1..100000'):cad.preview('empty',token,str(tmp_path/'empty.wmf'))
    assert len(original.SelectionSets.created)==1
    original.ModelSpace.items=[SimpleNamespace(Handle='B')]
    bitmap=cad.preview('bitmap',token,str(tmp_path/'native.bmp'))
    assert bitmap['pixel_size']==[30,20] and bitmap['format']=='bmp'


def test_preview_failure_removes_selection_without_replaying(environment,tmp_path,monkeypatch):
    cad,app,original=environment
    com=ModuleType('pythoncom');com.VT_ARRAY=8192;com.VT_DISPATCH=9;com.VT_BOOL=11;com.VT_I2=2
    win=ModuleType('win32com');client=ModuleType('win32com.client');client.VARIANT=lambda _,v:v;win.client=client
    for name,module in [('pythoncom',com),('win32com',win),('win32com.client',client)]:monkeypatch.setitem(sys.modules,name,module)
    def broken(*args):raise RuntimeError('export failed')
    original.Export=broken
    with pytest.raises(RuntimeError,match='export failed'):cad.preview('broken',cad.bound_token,str(tmp_path/'error.wmf'))
    assert original.SelectionSets.created[0].deleted
    with pytest.raises(ValueError,match='WRITE_UNCERTAIN'):cad.preview('broken',cad.bound_token,str(tmp_path/'error.wmf'))


def test_only_explicit_com_busy_rejection_is_retried(monkeypatch):
    monkeypatch.setattr('luomu_cad.cad.time.sleep',lambda _:None)
    class Busy(Exception):hresult=-2147418111
    count=[0]
    def read():
        count[0]+=1
        if count[0]<3:raise Busy()
        return 8
    assert _retry_rejected(read)==8 and count[0]==3
    def failure():raise ConnectionError('ambiguous')
    with pytest.raises(ConnectionError):_retry_rejected(failure)


def test_pywin32_member_lookup_failure_retries_only_the_single_step(monkeypatch):
    monkeypatch.setattr('luomu_cad.cad.time.sleep',lambda _:None)
    namespace={}
    source='''def __getattr__(self,name):
    self.lookups += 1
    if self.lookups < 3:
        raise AttributeError("AutoCAD.Application."+name)
    return self.method
'''
    exec(compile(source,'C:/runtime/win32com/client/dynamic.py','exec'),namespace)
    class Wrapper:
        __getattr__=namespace['__getattr__']
        def __init__(self):self.lookups=0;self.calls=0
        def method(self):self.calls+=1;return 'done'
    obj=Wrapper()
    assert _retry_rejected(lambda:obj.ZoomPrevious())=='done'
    assert obj.lookups==3 and obj.calls==1
    counts=[]
    def invalid_argument():
        counts.append(1)
        raise AttributeError('AutoCAD.Application.ZoomPrevious')
    with pytest.raises(AttributeError):_retry_rejected(invalid_argument)
    assert len(counts)==1


def test_document_metadata_is_refreshed_without_repeating_add(monkeypatch):
    monkeypatch.setattr('luomu_cad.cad.time.sleep',lambda _:None)
    attempts=[]
    class Early:
        _oleobj_=object()
    class Missing:
        def __getattr__(self,name):raise AttributeError('Add.'+name)
    ready=SimpleNamespace(Name='Drawing2.dwg',FullName='',HWND=2,GetVariable=lambda _:4)
    dynamic=ModuleType('win32com.client.dynamic')
    def wrap(*args,**kwargs):
        attempts.append(1)
        return Missing() if len(attempts)==1 else ready
    dynamic.Dispatch=wrap
    client=ModuleType('win32com.client');client.dynamic=dynamic
    win=ModuleType('win32com');win.client=client
    for name,module in [('win32com',win),('win32com.client',client),('win32com.client.dynamic',dynamic)]:monkeypatch.setitem(sys.modules,name,module)
    assert _ready_document(Early()) is ready and len(attempts)==2


def test_collection_metadata_is_refreshed_after_close(monkeypatch):
    monkeypatch.setattr('luomu_cad.cad.time.sleep',lambda _:None)
    class Early:
        _oleobj_=object()
    class Missing:
        Count=2
        def __getattr__(self,name):raise AttributeError('<unknown>.'+name)
    ready=SimpleNamespace(Count=2,Item=lambda index:index)
    attempts=[];dynamic=ModuleType('win32com.client.dynamic')
    def wrap(*args,**kwargs):
        attempts.append(1);return Missing() if len(attempts)==1 else ready
    dynamic.Dispatch=wrap;client=ModuleType('win32com.client');client.dynamic=dynamic
    win=ModuleType('win32com');win.client=client
    for name,module in [('win32com',win),('win32com.client',client),('win32com.client.dynamic',dynamic)]:monkeypatch.setitem(sys.modules,name,module)
    assert _ready_documents(Early()) is ready and len(attempts)==2


def test_application_version_is_optional_read_only_metadata(environment):
    cad,app,_=environment
    assert cad.connect()['application_version'] is None
    app.Version='24.3s (LMS Tech)'
    assert cad.connect()['application_version']==app.Version
    assert cad.start('version',True)['application_version']==app.Version


def test_frame_variable_uses_returned_boolean_or_short_com_type(environment,monkeypatch):
    cad,app,doc=environment
    com=ModuleType('pythoncom');com.VT_I2=2;com.VT_BOOL=11
    win=ModuleType('win32com');client=ModuleType('win32com.client');client.VARIANT=lambda kind,value:(kind,value);win.client=client
    for name,module in [('pythoncom',com),('win32com',win),('win32com.client',client)]:monkeypatch.setitem(sys.modules,name,module)
    variables={'FRAMESELECTION':True,'XCLIPFRAME':2};writes=[]
    doc.GetVariable=lambda name:variables[name]
    def set_variable(name,variant):
        kind,value=variant
        assert kind==(11 if isinstance(variables[name],bool) else 2)
        writes.append((name,variant));variables[name]=value
    doc.SetVariable=set_variable
    cad._set_frame_variable(doc,'FRAMESELECTION',0)
    cad._set_frame_variable(doc,'XCLIPFRAME',0)
    cad._set_frame_variable(doc,'FRAMESELECTION',1)
    cad._set_frame_variable(doc,'XCLIPFRAME',2)
    assert variables=={'FRAMESELECTION':True,'XCLIPFRAME':2}
    assert writes[0]==('FRAMESELECTION',(11,False))
    assert writes[1]==('XCLIPFRAME',(2,0))
    cad._set_frame_variable(doc,'XCLIPFRAME',2)
    assert len(writes)==4


def test_palette_only_wmf_is_not_a_native_visual_result():
    assert _wmf_drawing_records(wmf())==1
    assert _wmf_drawing_records(wmf(False))==0
    with pytest.raises(ValueError):_wmf_drawing_records(wmf()[:-2])


def test_activate_requires_exact_unique_target(environment):
    cad,app,original=environment
    with pytest.raises(ValueError,match='NOT_FOUND'):cad.activate_document('customer',True)
    assert app.ActiveDocument is original
    with pytest.raises(ValueError,match='Explicit'):cad.activate_document(original.Name)


def test_old_token_does_not_match_another_instance_of_the_same_path(environment):
    cad,app,original=environment
    old_token=cad.bound_token
    replacement=Document(app,original.Name,original.FullName)
    app.ActiveDocument=replacement
    assert replacement.HWND!=original.HWND and cad.identity(replacement)!=old_token
    with pytest.raises(ValueError,match='DOCUMENT_CHANGED'):cad.state(old_token,write=True)
    assert not original.close_calls and not replacement.close_calls


def test_document_listing_does_not_depend_on_com_enumerator(environment,monkeypatch):
    cad,app,original=environment
    monkeypatch.setattr(Documents,'__iter__',lambda _self:(_ for _ in ()).throw(TypeError('no enumerator')))
    assert cad.list_documents()['documents']==[{'name':original.Name,'path':original.FullName}]


def test_native_dimension_paper_style_is_entity_local_and_read_back(environment,monkeypatch):
    cad,app,original=environment
    com=ModuleType('pythoncom');com.VT_ARRAY=8192;com.VT_R8=5
    win=ModuleType('win32com');client=ModuleType('win32com.client');client.VARIANT=lambda _,v:v;win.client=client
    for name,module in [('pythoncom',com),('win32com',win),('win32com.client',client)]:monkeypatch.setitem(sys.modules,name,module)
    entity=SimpleNamespace(Handle='D1',ObjectName='AcDbAlignedDimension',Layer='0',Measurement=3000,updated=False)
    entity.Update=lambda:setattr(entity,'updated',True)
    calls=[]
    def add(*args):calls.append(args);return entity
    original.ModelSpace.AddDimAligned=add
    original.HandleToObject=lambda _:entity
    style={'TextHeight':2.5,'ArrowheadSize':2.5,'TextGap':1,'ScaleFactor':50,'LinearScaleFactor':1,
           'ExtensionLineOffset':1,'ExtensionLineExtend':2}
    arguments={'start':[0,0],'end':[3000,0],'at':[1500,-500],'style':style}
    result=cad.mutate('dim',cad.bound_token,'dimension',arguments)
    assert result['dimension_style']==style and entity.updated and len(calls)==1
    original.ModelSpace.items=[entity]
    readback=cad.read()['entities'][0]
    assert readback['Measurement']==3000 and readback['TextHeight']*readback['ScaleFactor']==125
    assert original.units==4
    for bad in [{'TextOverride':3000},{'TextHeight':0},{'ScaleFactor':float('nan')}]:
        with pytest.raises(ValueError,match='style'):
            cad.mutate('bad',cad.bound_token,'dimension',{**arguments,'style':bad})
    assert len(calls)==1 and cad.journal.get('bad') is None
