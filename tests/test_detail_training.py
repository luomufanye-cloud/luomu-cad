import importlib.util
from luomu_cad.storage import ROOT

spec=importlib.util.spec_from_file_location('waterproof_training',ROOT/'scripts/train_waterproof_continuity.py')
training=importlib.util.module_from_spec(spec)
spec.loader.exec_module(training)


def test_saved_line_arc_path_connects_and_detects_broken_variants(tmp_path):
    good=training.draw(tmp_path/'good.dxf',render=False)
    gap=training.draw(tmp_path/'gap.dxf','floor_gap',render=False)
    missing=training.draw(tmp_path/'missing.dxf','missing_upstand',render=False)
    assert good['ok'] and good['all_marked_members_connected']
    assert not gap['ok'] and not gap['end_to_end_connected']
    assert not missing['ok'] and not missing['end_to_end_connected']
    assert {'LINE','ARC'}=={e['type'] for e in good['native_geometry']}
    assert not good['engineering_approval']


def test_readback_uses_actual_saved_geometry_after_external_edit(tmp_path):
    import ezdxf
    path=tmp_path/'edited.dxf'
    training.draw(path,render=False)
    doc=ezdxf.readfile(path)
    line=next(e for e in doc.modelspace().query('LINE') if e.dxf.layer=='MEMBRANE' and e.dxf.end.x==280)
    line.dxf.start=(50,0,0)
    doc.saveas(path)
    assert not training.endpoint_check(path)['ok']
