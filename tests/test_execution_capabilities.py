import math
import re
from pathlib import Path
from types import SimpleNamespace
import ezdxf
import pytest
from luomu_cad.jobs import Jobs
from luomu_cad.curved_walls import draw,verify
from luomu_cad.pdf_export import render_pdf
from luomu_cad.cad import CAD
from luomu_cad.qa import file_hash


def curve(sweep=180):
    return {'walls':[{'id':'C1','center':[1000,2000],'radius':3000,'thickness':240,
                     'start_angle':330,'sweep_angle':sweep,
                     'openings':[{'id':'O1','offset':1000,'arc_width':900}]}]}


def test_arc_wall_geometry_and_gap_are_native_and_read_back(tmp_path):
    jobs=Jobs(tmp_path)
    result=jobs.curved_walls('curve-1',curve())
    assert result['ok'] and result['readback']['checked_entities']==8
    path=result['artifacts']['dxf']['path'];doc=ezdxf.readfile(path)
    arcs=list(doc.modelspace().query('ARC'));caps=list(doc.modelspace().query('LINE'))
    assert len(arcs)==4 and len(caps)==4
    assert sorted({a.dxf.radius for a in arcs})==[2880,3120]
    # Independent arc-length check against the requested axis length minus 900 mm.
    inner=[a for a in arcs if a.dxf.radius==2880]
    total_angle=sum((a.dxf.end_angle-a.dxf.start_angle)%360 for a in inner)
    assert math.radians(total_angle)*3000==pytest.approx(math.pi*3000-900)
    assert all((c.dxf.end-c.dxf.start).magnitude==pytest.approx(240) for c in caps)
    assert jobs.curved_walls('curve-1',curve())['artifacts']==result['artifacts']
    arcs[0].dxf.radius+=1;doc.saveas(path)
    with pytest.raises(ValueError,match='ARTIFACT_CHANGED'):jobs.curved_walls('curve-1',curve())


def test_full_ring_gap_has_no_spurious_seam(tmp_path):
    spec=curve(360);doc,_,_,expected=draw(spec)
    assert len(doc.modelspace().query('ARC'))==2 and len(doc.modelspace().query('LINE'))==2
    path=tmp_path/'ring.dxf';doc.saveas(path);assert verify(path,expected)['ok']
    spec['walls'][0]['openings']=[]
    doc,_,_,_=draw(spec);assert len(doc.modelspace().query('CIRCLE'))==2


@pytest.mark.parametrize('change',[
    {'radius':100}, {'sweep_angle':361}, {'thickness':float('nan')},
    {'openings':[{'id':'O','offset':0,'width':900}]},
    {'openings':[{'id':'O','offset':9000,'arc_width':900}]},
    {'openings':[{'id':'O','offset':0,'arc_width':math.pi*3000}]},
])
def test_invalid_curved_wall_inputs_are_rejected(change):
    spec=curve();spec['walls'][0].update(change)
    with pytest.raises(ValueError):draw(spec)


def test_pdf_has_requested_paper_and_scale_and_preserves_dxf(tmp_path):
    doc=ezdxf.new();doc.units=4
    doc.modelspace().add_line((0,0),(10000,0))
    doc.modelspace().add_circle((5000,3000),1000)
    source=tmp_path/'input.dxf';doc.saveas(source);before=file_hash(source)
    result=Jobs(tmp_path).export_pdf('print',str(source),[297,210],[-500,-500,10500,6500],50)
    data=Path(result['artifacts']['pdf']['path']).read_bytes()
    box=re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]',data)
    assert box and [float(box[1]),float(box[2])]==pytest.approx([297/25.4*72,210/25.4*72],abs=.001)
    assert result['settings']['drawing_on_paper_mm']==[220,140]
    assert file_hash(source)==before
    assert b'/Subtype /Image' not in data # Vector output, not a screenshot PDF.
    assert Jobs(tmp_path).export_pdf('print',str(source),[297,210],[-500,-500,10500,6500],50)['ok']
    with pytest.raises(ValueError,match='fit paper'):render_pdf(source,[297,210],[-500,-500,10500,6500],10)


class NotRunning(Exception):
    hresult=-2147221021


def test_explicit_start_reuses_existing_and_never_restarts(tmp_path,monkeypatch):
    monkeypatch.setenv('LUOMU_CAD_LIVE_WRITES','1')
    app=SimpleNamespace(HWND=9);created=[]
    cad=CAD(tmp_path,attach=lambda _:app,launcher=lambda _:created.append('unexpected'))
    with pytest.raises(ValueError,match='Explicit'):cad.start('start',False)
    result=cad.start('start',True)
    assert result['already_running'] and not result['cad_started'] and not created
    assert cad.start('start',True)['replayed']


def test_start_launches_once_and_requires_write_scope(tmp_path,monkeypatch):
    apps=[]
    def attach(_):
        if not apps:raise NotRunning()
        return apps[0]
    def launch(_):
        app=SimpleNamespace(HWND=42,Visible=False);apps.append(app);return app
    cad=CAD(tmp_path,attach=attach,launcher=launch)
    monkeypatch.delenv('LUOMU_CAD_LIVE_WRITES',raising=False)
    with pytest.raises(ValueError,match='DISABLED'):cad.start('start',True)
    monkeypatch.setenv('LUOMU_CAD_LIVE_WRITES','1')
    assert cad.start('start',True)['cad_started'] and apps[0].Visible
    assert cad.start('start',True)['replayed'] and len(apps)==1


def test_start_does_not_turn_other_connection_errors_into_launch(tmp_path,monkeypatch):
    monkeypatch.setenv('LUOMU_CAD_LIVE_WRITES','1');calls=[]
    def attach(_):raise ConnectionError('transport failure')
    cad=CAD(tmp_path,attach=attach,launcher=lambda _:calls.append(1))
    with pytest.raises(ConnectionError):cad.start('start',True)
    assert not calls and cad.journal.get('start') is None


def test_interrupted_start_is_not_replayed(tmp_path,monkeypatch):
    monkeypatch.setenv('LUOMU_CAD_LIVE_WRITES','1');calls=[]
    def attach(_):raise NotRunning()
    def launch(_):calls.append(1);raise ConnectionError('interrupted after creation')
    cad=CAD(tmp_path,attach=attach,launcher=launch)
    with pytest.raises(ConnectionError):cad.start('start',True)
    with pytest.raises(ValueError,match='WRITE_UNCERTAIN'):cad.start('start',True)
    assert len(calls)==1


def test_save_as_refreshes_token_and_never_overwrites(tmp_path,monkeypatch):
    from test_cad_contract import FakeApp
    app=FakeApp();doc=app.ActiveDocument
    # Native API stub checks the protocol only; these bytes are not a real DWG.
    def save(path):
        Path(path).write_bytes(b'AC1032'+b'protocol-fixture');doc.FullName=path;doc.Name=Path(path).name
    doc.SaveAs=save
    cad=CAD(tmp_path/'journal',attach=lambda _:app);token=cad.connect()['document_token']
    monkeypatch.setenv('LUOMU_CAD_LIVE_WRITES','1')
    target=tmp_path/'copy.dwg'
    result=cad.save_as('save-new',token,str(target))
    assert result['document_token']!=token and result['native_format_signature']=='AC1032'
    assert cad.save_as('save-new',token,str(target))['replayed']
    with pytest.raises(ValueError,match='exists'):cad.save_as('other',result['document_token'],str(target))
    target.write_bytes(b'changed')
    with pytest.raises(ValueError,match='CHANGED'):cad.save_as('save-new',token,str(target))


def test_source_inventory_builds_native_geometry_and_dimensions(tmp_path):
    from test_redraw_delivery import fixture
    _,_,source,inventory,_=fixture(tmp_path)
    before=file_hash(source)
    result=Jobs(tmp_path/'jobs').redraw('reference-1',source,inventory)
    assert result['ok'] and result['reference_check']['source_objects']==4
    assert result['complete_redraw_accepted'] is False
    doc=ezdxf.readfile(result['artifacts']['dxf']['path'])
    assert len(doc.modelspace().query('DIMENSION'))==1
    assert doc.modelspace().query('DIMENSION')[0].get_measurement()==pytest.approx(3000)
    assert file_hash(source)==before
    assert Jobs(tmp_path/'jobs').redraw('reference-1',source,inventory)['ok']
    inventory['source_sha256']='0'*64
    with pytest.raises(ValueError,match='SOURCE_HASH'):Jobs(tmp_path/'jobs').redraw('wrong-source',source,inventory)


def test_native_arc_converts_degrees_once(tmp_path,monkeypatch):
    import sys
    from types import ModuleType
    from test_cad_contract import FakeApp
    app=FakeApp();cad=CAD(tmp_path,attach=lambda _:app);token=cad.connect()['document_token']
    monkeypatch.setenv('LUOMU_CAD_LIVE_WRITES','1')
    com=ModuleType('pythoncom');com.VT_ARRAY=8192;com.VT_R8=5
    win=ModuleType('win32com');client=ModuleType('win32com.client');client.VARIANT=lambda _,v:v;win.client=client
    for name,module in [('pythoncom',com),('win32com',win),('win32com.client',client)]:monkeypatch.setitem(sys.modules,name,module)
    calls=[];entity=SimpleNamespace(Handle='ARC1',ObjectName='AcDbArc')
    def arc(*args):calls.append(args);return entity
    app.ActiveDocument.ModelSpace=SimpleNamespace(AddArc=arc)
    app.ActiveDocument.HandleToObject=lambda _:entity
    args={'center':[0,0],'radius':3000,'start_angle':330,'end_angle':90}
    assert cad.mutate('arc',token,'arc',args)['handle']=='ARC1'
    assert calls[0][2:]==pytest.approx((11*math.pi/6,math.pi/2))
    assert cad.mutate('arc',token,'arc',args)['replayed'] and len(calls)==1
    with pytest.raises(ValueError):cad.mutate('bad-arc',token,'arc',{**args,'start_angle':float('nan')})
    assert cad.journal.get('bad-arc') is None
