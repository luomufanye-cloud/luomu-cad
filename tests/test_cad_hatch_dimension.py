import sys
from types import ModuleType, SimpleNamespace

import pytest

from luomu_cad.cad import CAD


class FakeDocument:
    FullName = "C:/drawings/example.dwg"
    Name = "example.dwg"

    def GetVariable(self, name):
        return {"CMDNAMES": "", "INSUNITS": 4, "LWDEFAULT": 25}[name]


class FakeApp:
    HWND = 123

    def __init__(self):
        self.ActiveDocument = FakeDocument()
        self.Documents = [self.ActiveDocument]


@pytest.fixture
def live(tmp_path, monkeypatch):
    app = FakeApp()
    cad = CAD(tmp_path, attach=lambda _: app)
    token = cad.connect()["document_token"]
    monkeypatch.setenv("LUOMU_CAD_LIVE_WRITES", "1")
    pythoncom = ModuleType("pythoncom")
    pythoncom.VT_ARRAY = 8192
    pythoncom.VT_R8 = 5
    pythoncom.VT_DISPATCH = 9
    win32 = ModuleType("win32com")
    client = ModuleType("win32com.client")
    client.VARIANT = lambda _, values: tuple(values)
    win32.client = client
    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    monkeypatch.setitem(sys.modules, "win32com", win32)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    doc = app.ActiveDocument
    objects = {
        "B1": SimpleNamespace(Handle="B1", ObjectName="AcDbPolyline", Closed=True),
        "C1": SimpleNamespace(Handle="C1", ObjectName="AcDbCircle"),
        "OPEN": SimpleNamespace(Handle="OPEN", ObjectName="AcDbPolyline", Closed=False),
        "LINE": SimpleNamespace(Handle="LINE", ObjectName="AcDbLine"),
    }
    created = []

    class Hatch(SimpleNamespace):
        def AppendOuterLoop(self, items):
            self.outer.append(items)

        def AppendInnerLoop(self, items):
            self.inner.append(items)

        def Evaluate(self):
            self.evaluated = True

    def add_hatch(kind, pattern, associative):
        entity = Hatch(Handle="H%d" % len(created), ObjectName="AcDbHatch", kind=kind, pattern=pattern,
                       associative=associative, outer=[], inner=[], evaluated=False)
        created.append(entity)
        objects[entity.Handle] = entity
        return entity

    def add_dim(kind):
        def make(*args):
            entity = SimpleNamespace(Handle="D%d" % len(created), ObjectName=kind, args=args, Update=lambda: None)
            created.append(entity)
            objects[entity.Handle] = entity
            return entity
        return make

    def add_shape(kind):
        def make(*args):
            entity = SimpleNamespace(Handle="S%d" % len(created), ObjectName=kind, args=args)
            created.append(entity)
            objects[entity.Handle] = entity
            return entity
        return make

    doc.ModelSpace = SimpleNamespace(AddHatch=add_hatch, AddDimAligned=add_dim("AcDbAlignedDimension"),
                                     AddDimRotated=add_dim("AcDbRotatedDimension"),
                                     AddLightWeightPolyline=add_shape("AcDbPolyline"), AddCircle=add_shape("AcDbCircle"))
    doc.HandleToObject = lambda handle: objects[handle]
    doc.ActiveLayer = SimpleNamespace(Name="0")
    doc.Layers = SimpleNamespace(Item=lambda name: SimpleNamespace(Name=name, Lineweight=25))
    return cad, token, created


def test_hatch_fills_closed_boundary_with_inner_loops(live):
    cad, token, created = live
    result = cad.mutate("h-1", token, "hatch", {"boundary": "B1", "inner": ["C1"], "pattern": "ANSI31", "scale": 2, "angle": 0})
    hatch = created[0]
    assert result["entity_type"] == "AcDbHatch" and hatch.kind == 1 and hatch.associative
    assert len(hatch.outer) == 1 and len(hatch.inner) == 1 and hatch.evaluated
    assert hatch.PatternScale == 2.0 and hatch.PatternAngle == 0.0


def test_hatch_points_draw_outline_and_circle_islands_in_one_write(live):
    cad, token, created = live
    result = cad.mutate("h-pts", token, "hatch", {"points": [[0, 0], [10, 0], [10, 5]], "inner_circles": [[5, 2, 1]],
                                                   "boundary_layer": "OUT", "layer": "HATCH", "pattern": "SOLID"})
    hatch = next(e for e in created if e.ObjectName == "AcDbHatch")
    assert len(result["outline_handles"]) == 2 and hatch.evaluated and len(hatch.inner) == 1
    assert not hasattr(hatch, "PatternScale") and hatch.Layer == "HATCH"
    assert all(e.Layer == "OUT" for e in created if e.ObjectName != "AcDbHatch")


@pytest.mark.parametrize("arguments", [
    {"boundary": "B1", "points": [[0, 0], [1, 0], [1, 1]]},
    {"points": [[0, 0], [1, 0]]},
    {"points": [[0, 0], [1, 0], [1, 1]], "inner_circles": [[0, 0, -1]]},
    {"boundary": "OPEN"},
    {"boundary": "LINE"},
    {"boundary": "B1", "pattern": "BRICK-CUSTOM"},
    {"boundary": "B1", "scale": 0},
    {"boundary": "B1", "inner": "C1"},
    {"pattern": "ANSI31"},
])
def test_bad_hatch_requests_never_start_a_write(live, arguments):
    cad, token, created = live
    with pytest.raises(ValueError):
        cad.mutate("h-bad", token, "hatch", arguments)
    assert cad.journal.get("h-bad") is None and not created


def test_rotated_dimension_keeps_measured_value_in_override(live):
    cad, token, created = live
    cad.mutate("d-1", token, "dimension", {"start": [0, 0], "end": [0, 400], "at": [-50, 0], "rotation": 90, "text_override": "%%c<>"})
    dim = created[0]
    assert dim.ObjectName == "AcDbRotatedDimension" and dim.TextOverride == "%%c<>"
    assert abs(dim.args[3] - 1.5707963267948966) < 1e-12


@pytest.mark.parametrize("override", ["%%c400", "<><>", "a\n<>", 5])
def test_dimension_override_cannot_replace_measurement(live, override):
    cad, token, created = live
    with pytest.raises(ValueError):
        cad.mutate("d-bad", token, "dimension", {"start": [0, 0], "end": [10, 0], "at": [5, 5], "text_override": override})
    assert cad.journal.get("d-bad") is None and not created
