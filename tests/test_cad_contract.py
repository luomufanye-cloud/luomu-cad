import pytest
from luomu_cad.cad import CAD,vector


class FakeDocument:
    FullName="C:/drawings/example.dwg"
    Name="example.dwg"
    def __init__(self):self.commands=""
    def GetVariable(self,name):return {"CMDNAMES":self.commands,"INSUNITS":4}[name]


class FakeApp:
    HWND=123
    def __init__(self):
        self.ActiveDocument=FakeDocument()
        self.Documents=[self.ActiveDocument]


@pytest.fixture
def live(tmp_path):
    app=FakeApp()
    return CAD(tmp_path,attach=lambda _:app),app


def test_readonly_attach_and_document_binding(live):
    cad,app=live
    result=cad.connect()
    assert result["connected"] and result["units"]==4
    assert cad.state(result["document_token"]) is app.ActiveDocument
    app.ActiveDocument=FakeDocument()
    app.ActiveDocument.FullName="C:/drawings/changed.dwg"
    with pytest.raises(ValueError,match="DOCUMENT_CHANGED"):cad.state()


def test_writes_require_flag_token_and_idle_document(live,monkeypatch):
    cad,app=live
    token=cad.connect()["document_token"]
    monkeypatch.delenv("LUOMU_CAD_LIVE_WRITES",raising=False)
    with pytest.raises(ValueError,match="LIVE_WRITES_DISABLED"):
        cad.mutate("write-1",token,"line",{"start":[0,0],"end":[10,0]})
    monkeypatch.setenv("LUOMU_CAD_LIVE_WRITES","1")
    with pytest.raises(ValueError,match="TOKEN_MISMATCH"):
        cad.mutate("write-1","other","line",{})
    app.ActiveDocument.commands="LINE"
    with pytest.raises(ValueError,match="CAD_BUSY"):cad.mutate("write-1",token,"line",{})
    assert not list(cad.root.glob("*.json"))


@pytest.mark.parametrize("progid",["Other.Application","AutoCAD.Application.;anything","AutoCAD.Application.25.Test"])
def test_unsupported_app_cannot_be_launched(live,progid):
    cad,_=live
    with pytest.raises(ValueError):cad.application(progid)


def test_no_raw_commands_or_gui_routes(live,monkeypatch):
    cad,_=live
    token=cad.connect()["document_token"]
    monkeypatch.setenv("LUOMU_CAD_LIVE_WRITES","1")
    for operation in ["send_command","eval_lisp","screenshot","launch","delete"]:
        with pytest.raises(ValueError,match="Unsupported"):cad.mutate("escape",token,operation,{})


def test_points_reject_invalid_coordinates():
    for value in [[True,0],[float("nan"),0],[0],[0,1,2,3]]:
        with pytest.raises(ValueError):vector(value)


def test_committed_write_is_read_back_and_uncertain_write_is_never_replayed(live,monkeypatch):
    import sys
    from types import ModuleType,SimpleNamespace
    cad,app=live
    token=cad.connect()["document_token"]
    monkeypatch.setenv("LUOMU_CAD_LIVE_WRITES","1")
    pythoncom=ModuleType("pythoncom")
    pythoncom.VT_ARRAY=8192
    pythoncom.VT_R8=5
    win32=ModuleType("win32com")
    client=ModuleType("win32com.client")
    client.VARIANT=lambda _,values:tuple(values)
    win32.client=client
    monkeypatch.setitem(sys.modules,"pythoncom",pythoncom)
    monkeypatch.setitem(sys.modules,"win32com",win32)
    monkeypatch.setitem(sys.modules,"win32com.client",client)
    created=[]
    def line(start,end):
        entity=SimpleNamespace(Handle=str(len(created)+1),ObjectName="AcDbLine",StartPoint=start,EndPoint=end)
        created.append(entity)
        return entity
    app.ActiveDocument.ModelSpace=SimpleNamespace(AddLine=line)
    app.ActiveDocument.HandleToObject=lambda handle:next(e for e in created if e.Handle==handle)
    first=cad.mutate("line-1",token,"line",{"start":[0,0],"end":[100,0]})
    repeat=cad.mutate("line-1",token,"line",{"start":[0,0],"end":[100,0]})
    assert first["handle"]==repeat["handle"] and repeat["replayed"] and len(created)==1
    with pytest.raises(ValueError,match="JOB_CONFLICT"):
        cad.mutate("line-1",token,"line",{"start":[0,0],"end":[200,0]})
    def interrupted(start,end):
        line(start,end)
        raise ConnectionError("Connection interrupted after entity creation")
    app.ActiveDocument.ModelSpace.AddLine=interrupted
    with pytest.raises(ConnectionError):cad.mutate("line-2",token,"line",{"start":[0,0],"end":[200,0]})
    with pytest.raises(ValueError,match="WRITE_UNCERTAIN"):cad.mutate("line-2",token,"line",{"start":[0,0],"end":[200,0]})
    assert len(created)==2


def test_bad_parameters_do_not_start_live_operation(live,monkeypatch):
    cad,_=live
    token=cad.connect()["document_token"]
    monkeypatch.setenv("LUOMU_CAD_LIVE_WRITES","1")
    for arguments in [{"center":[0,0],"radius":-1},{"center":[0,0],"radius":float("nan")},{"radius":1}]:
        with pytest.raises(ValueError):cad.mutate("invalid-circle",token,"circle",arguments)
    assert cad.journal.get("invalid-circle") is None
