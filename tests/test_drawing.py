import json
from pathlib import Path
import ezdxf
import pytest
from luomu_cad.jobs import Jobs
from luomu_cad.qa import audit_dxf, snapshots, file_hash
from luomu_cad.storage import ROOT, Journal, workspace_lock
from luomu_cad.optimizer import optimize_layout


@pytest.fixture
def spec():
    return json.loads((ROOT/"examples/two-room.json").read_text(encoding="utf-8"))


def test_saved_plan_geometry_and_incremental_patch(tmp_path,spec):
    jobs=Jobs(tmp_path)
    first=jobs.generate("original",spec)
    assert first["ok"]
    assert set(first["room_areas_m2"])=={"R1","R2"}
    assert first["room_areas_m2"]["R1"]==pytest.approx(27.74375)
    before=snapshots(first["artifacts"]["dxf"]["path"])
    changed=jobs.patch("wider-door","original",first["revision"],"M2",{"width":1000})
    assert changed["ok"] and changed["unrelated_entities_unchanged"]
    assert changed["revision"]!=first["revision"]
    after=snapshots(changed["artifacts"]["dxf"]["path"])
    for group in ("opening:M1","opening:C1","opening:C2","wall:EXT","room:R1"):
        assert all(before[h]==after[h] for h in first["owners"][group])
    new_spec=json.loads(Path(changed["artifacts"]["spec"]["path"]).read_text(encoding="utf-8"))
    assert next(o for o in new_spec["openings"] if o["id"]=="M2")["width"]==1000
    assert jobs.generate("original",spec)["revision"]==first["revision"]
    assert file_hash(first["artifacts"]["dxf"]["path"])==first["revision"]
    with pytest.raises(ValueError,match="STALE_REVISION"):
        jobs.patch("stale","original","old","M1",{"width":1000})


@pytest.mark.parametrize("change",["nan","overlap","corner","duplicate","room-outside","self-intersection"])
def test_invalid_geometry_is_rejected_before_write(tmp_path,spec,change):
    if change=="nan":spec["walls"][0]["thickness"]=float("nan")
    elif change=="overlap":spec["openings"].append({**spec["openings"][0],"id":"M9"})
    elif change=="corner":spec["openings"][0]["offset"]=8500
    elif change=="duplicate":spec["walls"][1]["id"]="EXT"
    elif change=="self-intersection":spec["walls"][0]["axis"]=[[0,0],[9000,6000],[0,6000],[9000,0]]
    elif change=="room-outside":spec["rooms"][0]["at"]=[-10000,0]
    with pytest.raises(ValueError):Jobs(tmp_path).generate("bad",spec)
    assert not list(tmp_path.rglob("*.dxf"))


def test_auditor_detects_inserted_defects(tmp_path):
    doc=ezdxf.new()
    doc.units=4
    model=doc.modelspace()
    model.add_line((0,0),(0,0))
    model.add_line((0,0),(100,0))
    model.add_line((100,0),(0,0))
    model.add_lwpolyline([(0,0),(10,10),(0,10),(10,0)],close=True)
    path=tmp_path/"defects.dxf"
    doc.saveas(path)
    report=audit_dxf(path)
    assert not report["ok"]
    assert {"zero_length","duplicate_line","self_intersection"} <= {f["kind"] for f in report["findings"]}


def test_uncertain_job_and_concurrent_writer_never_replay(tmp_path):
    journal=Journal(tmp_path/"jobs")
    journal.begin("uncertain",{"op":"write"})
    with pytest.raises(ValueError,match="WRITE_UNCERTAIN"):journal.begin("uncertain",{"op":"write"})
    with workspace_lock(tmp_path):
        with pytest.raises(RuntimeError,match="WORKSPACE_BUSY"):
            with workspace_lock(tmp_path):pytest.fail("entered second writer")


def test_layout_clearance_and_obstacles():
    answer=optimize_layout({"width":5000,"height":4000,"clearance":500,
        "items":[{"id":"desk","width":1500,"height":800},{"id":"sofa","width":2000,"height":900}],
        "obstacles":[{"x":4000,"y":0,"width":1000,"height":1000}]})
    assert answer["ok"]
    a,b=answer["items"]
    assert a["x"]+a["width"]+500<=b["x"] or b["x"]+b["width"]+500<=a["x"] or a["y"]+a["height"]+500<=b["y"] or b["y"]+b["height"]+500<=a["y"]


@pytest.mark.parametrize("constraint",[
    {"boundary":[[0,0],[6000,0],[4000,4000],[0,4000]]},
    {"reserved_areas":[{"id":"future-entry","x":4000,"y":0,"width":1500,"height":4000}]},
])
def test_unrepresented_site_constraints_are_not_silently_dropped(constraint):
    spec={"width":6000,"height":4000,"items":[{"id":"display","width":1500,"height":800}],**constraint}
    with pytest.raises(ValueError,match="Unsupported layout constraints"):
        optimize_layout(spec)


def test_unimplemented_rotation_is_rejected():
    with pytest.raises(ValueError,match="Unsupported item constraint"):
        optimize_layout({"width":6000,"height":4000,"items":[{"id":"display","width":1500,"height":800,"rotation":45}]})


def test_rectangular_reserved_entrance_can_be_explicitly_kept_clear():
    result=optimize_layout({"width":6000,"height":4000,"clearance":300,
        "items":[{"id":"display","width":1500,"height":800},{"id":"counter","width":2000,"height":800}],
        "obstacles":[{"id":"entry-corridor","x":4000,"y":0,"width":1500,"height":4000}]})
    assert result["ok"]
    assert all(item["x"]+item["width"]+300<=4000 for item in result["items"])
