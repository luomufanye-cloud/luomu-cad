"""Native service protocol tests; fake objects are not AutoCAD acceptance evidence."""
from pathlib import Path
from types import SimpleNamespace as Obj
import copy
import pytest

from luomu_cad.native_delivery import capture,service_context,inspect,measure_native,check_style,parse_entity_data
from luomu_cad.cad import CAD


class Table:
    def __init__(self,items):self.items=items
    @property
    def Count(self):return len(self.items)
    def Item(self,index):
        if isinstance(index,str):return next(row for row in self.items if row.Name==index)
        return self.items[index]


def retry(fn,**kw):return fn()


def line(handle='1'):
    return Obj(Handle=handle,ObjectName='AcDbLine',Layer='WALL',Lineweight=-1,
        Linetype='ByLayer',LinetypeScale=1.,Visible=True,Color=256,
        StartPoint=[0.,0.,0.],EndPoint=[1000.,0.,0.],Length=1000.)


def document(path):
    layer=Obj(Name='WALL',Handle='A0',Lineweight=25,Linetype='Continuous',Color=7,LayerOn=True,Freeze=False,Plottable=True)
    layer.GetXData=lambda name:(None,None)
    doc=Obj(Name=path.name,FullName=str(path),HWND=45,Saved=True,
        ModelSpace=Table([line()]),Layers=Table([layer]),Blocks=Table([]),TextStyles=Table([]))
    doc.vars={'INSUNITS':4,'DBMOD':0,'CMDNAMES':'','LWDISPLAY':False,'LWDEFAULT':25,
        'LTSCALE':1.,'PSLTSCALE':1,'PSTYLEMODE':1}
    doc.GetVariable=lambda name:doc.vars[name]
    return doc


def env(tmp_path):
    path=tmp_path/'native.dwg';path.write_bytes(b'AC1032protocol-fake')
    doc=document(path);app=Obj(HWND=89,Version='24.3',ActiveDocument=doc,Documents=Table([doc]))
    cad=CAD(tmp_path/'journal',attach=lambda _:app);cad.connect()
    def entity_data(token,handles):
        return {'records':[{'entget':'((0 . "LAYER") (5 . "A0"))' if h=='A0' else '((0 . "LINE") (5 . "'+h+'") (10 0 0 0) (11 1000 0 0))'} for h in handles]}
    cad.native_entity_data=entity_data
    return cad,doc,path


def test_native_double_read_and_context(tmp_path):
    cad,doc,path=env(tmp_path)
    with pytest.raises(ValueError,match='PROVENANCE_REQUIRED'):cad.delivery_snapshot(cad.bound_token,path)
    cad._record_native_provenance(doc,'actual-protocol-save','save')
    snapshot=cad.delivery_snapshot(cad.bound_token,path)
    assert snapshot['stable_read_verified'] and snapshot['facts']['modelspace_count']==1
    with pytest.raises(ValueError,match='PREVIEW_REQUIRED'):
        inspect(service_context(snapshot),path,{'units':4,'entity_counts':{'AcDbLine':1},'modelspace_handles':['1']})
    with pytest.raises(ValueError,match='LIVE_MCP'):
        inspect(snapshot,path,{})
    snapshot['preview']={'native_preview':True,'sha256':'protocol-preview'}
    result=inspect(service_context(snapshot),path,{'units':4,'entity_counts':{'AcDbLine':1},'modelspace_handles':['1']})
    assert result['native_save_or_open_verified'] and not result['reopened']
    assert result['visual_coverage_verified'] is False  # nonempty Export is insufficient
    assert measure_native(result,{'kind':'length','handles':['1'],'range':[1000,1000]})['passed']
    assert check_style(result,{'basis':'test contract','layers':{'WALL':{'lineweight_mm':[.25,.25],'linetypes':['Continuous']}}})['passed']


@pytest.mark.parametrize('attack',['path','disk','dirty','dbmod','busy','unknown','duplicate','property','nonfinite','normal'])
def test_native_rejects_actual_state_changes(tmp_path,attack):
    cad,doc,path=env(tmp_path);cad._record_native_provenance(doc,'actual-protocol-save','save')
    if attack=='path':doc.FullName=str(tmp_path/'other.dwg')
    elif attack=='disk':path.write_bytes(b'AC1032externally-replaced-while-memory-saved')
    elif attack=='dirty':doc.Saved=False
    elif attack=='dbmod':doc.vars['DBMOD']=20
    elif attack=='busy':doc.vars['CMDNAMES']='LINE'
    elif attack=='unknown':doc.ModelSpace.items[0].ObjectName='AcDbProxyEntity'
    elif attack=='duplicate':doc.ModelSpace.items.append(line())
    elif attack=='property':del doc.ModelSpace.items[0].StartPoint
    elif attack=='nonfinite':doc.ModelSpace.items[0].Length=float('nan')
    elif attack=='normal':doc.ModelSpace.items[0].StartPoint=[1,2,3]
    with pytest.raises((ValueError,RuntimeError)):cad.delivery_snapshot(cad.bound_token,path)


def dimension(handle='D'):
    row=line(handle);row.ObjectName='AcDbRotatedDimension'
    row.__dict__.update(Measurement=1000.,TextOverride='',TextPosition=[500.,100.,0.],LinearScaleFactor=1.,
        PrimaryUnitsPrecision=0,DecimalSeparator=46,UnitsFormat=2,TextPrefix='',TextSuffix='',
        ToleranceDisplay=0,AltUnits=False,RoundDistance=0.,Rotation=0.,TextHeight=25.,TextStyle='Standard',
        ScaleFactor=1.,DimensionLineWeight=-1,ExtensionLineWeight=-1)
    return row


def dimension_doc(tmp_path):
    doc=document(tmp_path/'native.dwg');doc.ModelSpace.items=[dimension()]
    text=Obj(ObjectName='AcDbMText',InsertionPoint=[500.,100.,0.],AttachmentPoint=5,TextString='1000',Handle='TX',StyleName='Standard')
    block=Table([text]);block.Name='*D1';block.Origin=[0,0,0];block.IsXRef=False
    doc.Blocks=Table([block]);doc.TextStyles=Table([Obj(Name='Standard',FontFile='test.ttf',BigFontFile='',Height=0.,Width=1.,ObliqueAngle=0.,TextGenerationFlag=0,GetFont=lambda:('TestFont',False,False,0,34),GetXData=lambda name:([1001,1000,1071],['ACAD','TestFont',34]))])
    return doc


def test_native_dimension_measurement_and_actual_display(tmp_path):
    doc=dimension_doc(tmp_path);facts=capture(doc,retry)
    assert facts['model'][0]['native_display']['value']==1000
    assert not facts['model'][0]['extension_origins_available']


@pytest.mark.parametrize('attack',['missing','nan','bool','override','scale','display','attachment','unmapped'])
def test_native_dimension_fail_closed(tmp_path,attack):
    doc=dimension_doc(tmp_path);dim=doc.ModelSpace.items[0];text=doc.Blocks.items[0].items[0]
    if attack=='missing':del dim.Measurement
    elif attack=='nan':dim.Measurement=float('nan')
    elif attack=='bool':dim.Measurement=True
    elif attack=='override':dim.TextOverride='999'
    elif attack=='scale':dim.LinearScaleFactor=2
    elif attack=='display':text.TextString='999'
    elif attack=='attachment':text.AttachmentPoint=1
    elif attack=='unmapped':text.InsertionPoint=[400,100,0]
    with pytest.raises(ValueError):capture(doc,retry)


def test_native_changes_between_reads(tmp_path,monkeypatch):
    cad,doc,path=env(tmp_path);cad._record_native_provenance(doc,'save','save')
    import luomu_cad.native_delivery as native
    original=native.capture;calls=[]
    def changed(*args,**kwargs):
        calls.append(True)
        if len(calls)==2:doc.ModelSpace.items[0].EndPoint=[1100,0,0]
        return original(*args,**kwargs)
    monkeypatch.setattr(native,'capture',changed)
    with pytest.raises(ValueError,match='CHANGED_DURING'):cad.delivery_snapshot(cad.bound_token,path)


def test_fixed_native_reader_rejects_expression_injection(tmp_path):
    cad,doc,path=env(tmp_path)
    for handles in [['1) (command "ERASE")'],[],['1','1'],[True]]:
        with pytest.raises(ValueError,match='hexadecimal'):CAD.native_entity_data(cad,cad.bound_token,handles)


def test_native_full_precision_serialization():
    groups=parse_entity_data('((0 . "LINE") (10 "~REAL~792.9457580290988000" "~REAL~0.0000000000000000" 0))')
    assert groups[1][1][0]==pytest.approx(792.9457580290988,abs=1e-12)
    for invalid in ['((10 1 2)', '(foo)', '((42 . "~REAL~nan"))', '(())']:
        with pytest.raises(ValueError):parse_entity_data(invalid)


def test_native_definition_without_optional_measurement_cache(tmp_path):
    doc=dimension_doc(tmp_path);del doc.ModelSpace.items[0].Measurement
    records={'D':'((0 . "DIMENSION") (5 . "D") (2 . "*D1") (70 . 32) (13 0 0 0) (14 1000 0 0) (50 . 0))',
        'TX':'((0 . "MTEXT") (5 . "TX") (1 . "1000") (10 500 100 0) (40 . 25) (71 . 5))'}
    records['A0']='((0 . "LAYER") (5 . "A0"))'
    facts=capture(doc,retry,entity_data=records.__getitem__)
    row=facts['model'][0]
    assert row['Measurement']==1000 and row['measurement_source']=='actual_native_definition'
    assert row['ExtLine2Point']==[1000,0,0] and row['native_geometry_block']=='*D1'
    assert 'activex_measurement_error' in row and facts['dimension_blocks']['*D1']['entities']
    records['D']=records['D'].replace('(14 1000 0 0)','(14 999 0 0)')
    with pytest.raises(ValueError,match='DISPLAY_MISMATCH'):capture(doc,retry,entity_data=records.__getitem__)


@pytest.mark.parametrize('extra',[{'safety_clearance':100},{'manufacturing_tolerance':.01}])
def test_native_measurement_unknown_customer_expectations_rejected(tmp_path,extra):
    facts=capture(document(tmp_path/'native.dwg'),retry)
    with pytest.raises(ValueError,match='Unsupported native measurement'):
        measure_native({'actual':facts},{'kind':'length','handles':['1'],'range':[1000,1000],**extra})
    with pytest.raises(ValueError):check_style({'actual':facts},{'basis':'test','layers':{},**extra})


def test_native_original_source_compare_is_executable(tmp_path):
    import ezdxf
    from luomu_cad.native_correspondence import compare
    doc=ezdxf.new();doc.units=4;doc.layers.new('WALL',dxfattribs={'lineweight':25})
    e=doc.modelspace().add_line((0,0),(1000,0),dxfattribs={'layer':'WALL'})
    memory=document(tmp_path/'native.dwg');memory.ModelSpace.items[0].Handle=e.dxf.handle
    row=capture(memory,retry)['model'][0]
    row['native_entity_groups']=[(0,'LINE'),(5,e.dxf.handle),(10,[0,0,0]),(11,[1000,0,0])]
    facts=capture(memory,retry);facts['model'][0]=row
    facts['layers'][0]['transparency_xdata']=[None,None]
    assert compare({'actual':facts},doc)['passed']
    row['EndPoint']=[999,0,0]
    assert not compare({'actual':facts},doc)['passed']
    row['EndPoint']=[1000,0,0];row['native_entity_groups'].append((39,1))
    with pytest.raises(ValueError,match='thickness'):compare({'actual':facts},doc)


@pytest.mark.parametrize('bad',[None,True,float('nan')])
def test_invalid_measurement_cannot_use_optional_cache_fallback(tmp_path,bad):
    doc=dimension_doc(tmp_path);doc.ModelSpace.items[0].Measurement=bad
    records={'D':'((0 . "DIMENSION") (5 . "D") (2 . "*D1") (42 . -1) (70 . 32) (13 0 0 0) (14 1000 0 0) (50 . 0))'}
    records['A0']='((0 . "LAYER") (5 . "A0"))'
    with pytest.raises(ValueError,match='MEASUREMENT_PROPERTY_INVALID'):
        capture(doc,retry,entity_data=records.__getitem__)


def test_full_source_preview_requires_actual_equivalence_and_file_binding(tmp_path):
    import ezdxf
    from luomu_cad.native_correspondence import correspondence_preview
    from luomu_cad.qa import file_hash
    doc=ezdxf.new();doc.units=4;doc.layers.new('WALL',dxfattribs={'lineweight':25})
    e=doc.modelspace().add_line((0,0),(1000,0),dxfattribs={'layer':'WALL'})
    source=tmp_path/'original.dxf';doc.saveas(source)
    memory=document(tmp_path/'native.dwg');memory.ModelSpace.items[0].Handle=e.dxf.handle
    facts=capture(memory,retry);facts['model'][0]['native_entity_groups']=[(0,'LINE'),(5,e.dxf.handle)]
    facts['layers'][0]['transparency_xdata']=[None,None]
    native=tmp_path/'native.dwg';native.write_bytes(b'AC1032protocol-fake-not-real-native')
    snapshot={'path':str(native),'file_sha256':file_hash(native),'snapshot_sha256':'protocol-facts','facts':facts}
    result=correspondence_preview(snapshot,source,tmp_path/'full.png')
    assert result['full_model_coverage_verified'] and not result['native_export']
    assert result['source_model_bbox']==[0,0,1000,0]
    assert result['settings']['window_mm'][0]<0 and result['settings']['window_mm'][2]>1000
    assert result['native_file_sha256']==file_hash(native) and result['source_file_sha256']==file_hash(source)
    facts['model'][0]['EndPoint']=[999,0,0]
    with pytest.raises(ValueError,match='geometry differs'):correspondence_preview(snapshot,source,tmp_path/'wrong.png')
    native.write_bytes(b'externally replaced')
    with pytest.raises(ValueError,match='Native file changed'):correspondence_preview(snapshot,source,tmp_path/'changed.png')


def native_font_style(doc):
    details=['',False,False,1,0]
    style=Obj(Name='TEST',FontFile='old.ttf')
    style.GetFont=lambda:tuple(details)
    def setfont(*values):details[:]=values;doc.Saved=False
    style.SetFont=setfont
    style.GetXData=lambda name:([1001,1000,1071],['ACAD',details[0],34])
    doc.TextStyles=Table([style])
    return style,details


def write_metadata_font(path,family='Controlled Family',localized=''):
    from fontTools.ttLib import TTFont,newTable
    font=TTFont();table=newTable('name');table.names=[]
    table.setName(family,1,3,1,0x409)
    if localized:table.setName(localized,1,3,1,0x804)
    font['name']=table;font.save(path);font.close()


def test_explicit_single_native_font_configuration_and_readback(tmp_path,monkeypatch):
    cad,doc,path=env(tmp_path);style,details=native_font_style(doc)
    font=tmp_path/'controlled.ttf';write_metadata_font(font)
    args=('font-op',cad.bound_token,'TEST',str(font),'Controlled Family',34)
    with pytest.raises(ValueError,match='Explicit existing text-style'):cad.configure_text_style(*args)
    with pytest.raises(ValueError,match='LIVE_WRITES_DISABLED'):cad.configure_text_style(*args,explicit_request=True)
    monkeypatch.setenv('LUOMU_CAD_LIVE_WRITES','1')
    result=cad.configure_text_style(*args,explicit_request=True)
    assert result['ok'] and not result['saved'] and not result['saved_automatically'] and not result['regenerated']
    assert details==['Controlled Family',False,False,0,34]
    assert result['actual']['font_xdata'][1][-1]==34 and cad.configure_text_style(*args,explicit_request=True)['replayed']
    details[1]=True
    with pytest.raises(ValueError,match='READBACK_MISMATCH'):cad.configure_text_style(*args,explicit_request=True)


def test_font_mapping_must_match_actual_native_packed_flags(tmp_path,monkeypatch):
    cad,doc,path=env(tmp_path);native_font_style(doc)
    monkeypatch.setenv('LUOMU_CAD_LIVE_WRITES','1')
    font=tmp_path/'controlled.ttf';write_metadata_font(font)
    with pytest.raises(ValueError,match='PACKED_SOURCE_FLAGS_MISMATCH'):
        cad.configure_text_style('wrong-source-flags',cad.bound_token,'TEST',str(font),'Controlled Family',999,explicit_request=True)
    assert not doc.Saved


def test_generated_fontfile_omission_uses_actual_property_put_get(tmp_path,monkeypatch):
    import sys
    cad,doc,path=env(tmp_path);style,details=native_font_style(doc)
    class MissingGenerated(Obj):
        def __getattribute__(self,name):
            if name=='FontFile':raise AttributeError('IAcadTextStyle has no generated FontFile')
            return super().__getattribute__(name)
        def __setattr__(self,name,value):
            if name=='FontFile':raise AttributeError('IAcadTextStyle has no generated FontFile')
            super().__setattr__(name,value)
    wrapped=MissingGenerated(**{k:v for k,v in style.__dict__.items() if k!='FontFile'})
    calls=[];stored=['old.ttf']
    class Dispatch:
        def GetIDsOfNames(self,name):assert name=='FontFile';return 12
        def Invoke(self,dispid,lcid,flags,result,*values):
            calls.append(flags)
            if flags==4:stored[0]=values[0];return None
            assert flags==2;return stored[0]
    wrapped._oleobj_=Dispatch();doc.TextStyles=Table([wrapped])
    monkeypatch.setitem(sys.modules,'pythoncom',Obj(DISPATCH_PROPERTYGET=2,DISPATCH_PROPERTYPUT=4))
    monkeypatch.setenv('LUOMU_CAD_LIVE_WRITES','1')
    font=tmp_path/'controlled.ttf';write_metadata_font(font)
    result=cad.configure_text_style('raw-put',cad.bound_token,'TEST',str(font),'Controlled Family',34,explicit_request=True)
    assert result['ok'] and 4 in calls and 2 in calls and Path(stored[0])==font


def test_localized_family_aliases_must_belong_to_same_collection_face(tmp_path):
    from fontTools.ttLib import TTFont,TTCollection,newTable
    from luomu_cad.native_delivery import same_font_family
    def face(english,localized):
        font=TTFont();table=newTable('name');table.names=[]
        table.setName(english,1,3,1,0x409);table.setName(localized,1,3,1,0x804)
        font['name']=table;return font
    collection=TTCollection();collection.fonts=[face('Family A','本地族甲'),face('Family B','本地族乙')]
    path=tmp_path/'two-faces.ttc';collection.save(path);collection.close()
    assert same_font_family(path,'Family A','本地族甲')
    assert not same_font_family(path,'Family A','本地族乙')


def test_native_logical_font_alias_requires_unique_registration_and_physical_face(tmp_path,monkeypatch):
    import luomu_cad.native_delivery as native
    source=tmp_path/'physical-font.ttf';write_metadata_font(source,'Physical Family','本地族')
    monkeypatch.setattr(native,'registered_fonts',lambda:[('Physical Family (TrueType)',source)])
    result=native.verify_font_resource('Physical Family.ttf','本地族',source,'Physical Family')
    assert result['mode']=='unique_windows_registered_logical_face'
    assert result['physical_path']==str(source) and result['face_index']==0
    with pytest.raises(ValueError,match='logical face alias'):
        native.verify_font_resource('Arbitrary.ttf','本地族',source,'Physical Family')
    other=tmp_path/'other-font.ttf';write_metadata_font(other,'Other Family')
    with pytest.raises(ValueError,match='bytes differ'):
        native.verify_font_resource(other,'本地族',source,'Physical Family')
    ambiguous=tmp_path/'duplicate.ttf';ambiguous.write_bytes(source.read_bytes())
    monkeypatch.setattr(native,'registered_fonts',lambda:[('Physical Family (TrueType)',source),('Physical Family (TrueType)',ambiguous)])
    with pytest.raises(ValueError,match='unique Windows'):
        native.verify_font_resource('Physical Family.ttf','本地族',source,'Physical Family')


def test_native_style_checks_dimension_pens_and_real_cached_strokes():
    row={'Handle':'D1','ObjectName':'AcDbRotatedDimension','Layer':'DIM','effective_lineweight_mm':.13,
        'effective_linetype':'Continuous','DimensionLineWeight':-2,'ExtensionLineWeight':-2,'native_geometry_block':'*D1'}
    stroke={'handle':'C1','groups':[(0,'LINE'),(8,'0'),(370,25)]}
    facts={'model':[row],'layers':[{'Name':'0','Lineweight':25,'Linetype':'Continuous'},{'Name':'DIM','Lineweight':13,'Linetype':'Continuous'}],
        'variables':{'LWDEFAULT':25},'dimension_blocks':{'*D1':{'entities':[stroke]}}}
    spec={'basis':'Source-specific .13 dimension pen','layers':{'DIM':{'lineweight_mm':[.13,.13],'linetypes':['Continuous']}}}
    result=check_style({'actual':facts},spec)
    assert not result['passed'] and any('dimension_display_stroke' in finding for finding in result['findings'])
    row['DimensionLineWeight']=13;row['ExtensionLineWeight']=13
    assert not check_style({'actual':facts},spec)['passed']  # cached source still wrong
    stroke['groups'][-1]=(370,13)
    assert check_style({'actual':facts},spec)['passed']
    for inherited in [-1,-2]:
        row['DimensionLineWeight']=inherited;row['ExtensionLineWeight']=inherited
        stroke['groups'][-1]=(370,inherited)
        assert check_style({'actual':facts},spec)['passed']
