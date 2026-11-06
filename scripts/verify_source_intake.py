"""Original DXF intake exercise via stdio MCP; no active CAD or external assets."""
import asyncio
import copy
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import ezdxf
from luomu_cad.cli import execute
from luomu_cad.storage import ROOT, atomic_json


async def exercise():
    folder = ROOT/'runtime/verification/source-intake'
    folder.mkdir(parents=True, exist_ok=True)
    doc = ezdxf.new('R2018'); doc.units = 6
    model = doc.modelspace()
    handles = {}
    for name, x in [('A',0),('B',3),('C',7)]:
        line = model.add_line((x,0),(x,5),dxfattribs={'layer':'AXIS'})
        handles[name] = line.dxf.handle
    # Near-axis wall faces deliberately differ from the axis reference.
    for x in (-0.1, 0.1, 2.9, 3.1, 6.9, 7.1):
        model.add_line((x,0),(x,5),dxfattribs={'layer':'WALL-FACE'})
    part = doc.blocks.new('part', base_point=(1,2))
    part.add_lwpolyline([(1,2),(1.6,2),(1.6,2.4),(1,2.4)],close=True)
    assembly = doc.blocks.new('assembly')
    assembly.add_blockref('part',(0,0),dxfattribs={'rotation':90,'xscale':-1})
    assembly.add_blockref('part',(1,0))
    model.add_blockref('assembly',(2,2),dxfattribs={'layer':'COMPONENT'})
    source = folder/'source.dxf'; doc.saveas(source)
    base_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    report = await execute('workbench_source_inventory',{'path':str(source),'box_mm':[-200,-100,7200,5100]})
    assert report['ok'] and report['selected_count'] == 11 and len(report['blocks']) == 3
    assert report['source_sha256'] == base_sha and report['unit']['mm_per_unit'] == 1000
    leaf = next(r for r in report['entities'] if r['type']=='LWPOLYLINE')
    assert all(abs(a-b)<1e-6 for a,b in zip(leaf['bounds_mm'],[1600,1400,2000,2000]))
    saved = ezdxf.readfile(source)
    def read_features(drawing):
        return [{'id':name,'kind':'axis','axis':'x',
                 'coordinate_mm':drawing.entitydb[handle].dxf.start.x*1000}
                for name,handle in handles.items()]
    features = read_features(saved)
    chains = [{'id':'axis-segments','kind':'axis','axis':'x','features':['A','B','C'],
               'segments_mm':[3000,4000],'tolerance_mm':0.01},
              {'id':'axis-total','kind':'axis','axis':'x','features':['A','C'],
               'segments_mm':[7000],'tolerance_mm':0.01}]
    good = await execute('workbench_dimension_chains',{'features':features,'chains':chains})
    assert good['ok']
    shifted = saved.entitydb[handles['B']]
    shifted.dxf.start = (3.12,0,0); shifted.dxf.end = (3.12,5,0)
    changed = folder/'shifted-axis.dxf'; saved.saveas(changed)
    bad = await execute('workbench_dimension_chains',{'features':read_features(ezdxf.readfile(changed)),'chains':chains})
    assert not bad['ok'] and len([i for i in bad['findings'] if i['error']=='length_mismatch']) == 2
    wrong = copy.deepcopy(features); wrong[1]['kind']='face'
    semantic = await execute('workbench_dimension_chains',{'features':wrong,'chains':chains})
    assert not semantic['ok']
    conflict = copy.deepcopy(chains); conflict[1]['segments_mm']=[7100]
    conflicts = await execute('workbench_dimension_chains',{'features':features,'chains':conflict})
    assert any(f['error']=='source_dimension_conflict' for f in conflicts['findings'])
    unitless = ezdxf.readfile(source); unitless.units=0
    unknown = folder/'unitless.dxf'; unitless.saveas(unknown)
    rejected = await execute('workbench_source_inventory',{'path':str(unknown)})
    assert rejected.get('ok') is False
    accepted = await execute('workbench_source_inventory',{'path':str(unknown),'unit_mm':1000,
                             'unit_reason':'Original training input: 7 units represents the stated 7000 mm span'})
    assert accepted['ok']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == base_sha
    # Render the actual saved readback, not a reconstruction from expected coordinates.
    from ezdxf.addons.drawing import matplotlib as drawing
    preview = folder/'source.png'
    drawing.qsave(ezdxf.readfile(source).modelspace(),preview,dpi=160)
    result = {'ok':True,'basis':'original synthetic exercise; not customer geometry or host-model validation',
              'nested_transform_and_unit_readback':True,'shifted_axis_detected':True,
              'face_substitution_detected':True,'conflicting_total_detected':True,
              'unitless_requires_evidence':True,'source_unchanged':True,'cad_contacted':False,
              'inventory':report,'normal_chains':good,'shifted_chains':bad,
              'semantic_failure':semantic,'conflict_failure':conflicts,
              'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,changed,unknown,preview)}}
    atomic_json(folder/'result.json',result)
    return result


if __name__=='__main__':
    print(json.dumps(asyncio.run(exercise()),ensure_ascii=False,indent=2))
