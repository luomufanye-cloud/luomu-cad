"""Offline wall-floor waterproof continuity exercise, with explicit broken variants.

All coordinates are arbitrary schematic units. This is not a dimensioned
construction detail, a material-thickness check or a watertightness test.
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import ezdxf
from luomu_cad.storage import ROOT,atomic_json
from luomu_cad.qa import render_dxf,file_hash

TOP=(0.,180.)
FLOOR=(280.,0.)


def key(point):return tuple(round(float(v),6) for v in tuple(point)[:2])


def endpoint_check(path):
    """Measure saved native LINE/ARC endpoints, never trust labels or input flags."""
    doc=ezdxf.readfile(path)
    graph=defaultdict(set)
    records=[]
    for entity in doc.modelspace():
        if entity.dxf.layer!='MEMBRANE':continue
        if entity.dxftype()=='LINE':
            a,b=key(entity.dxf.start),key(entity.dxf.end)
        elif entity.dxftype()=='ARC':
            center=entity.dxf.center
            radius=float(entity.dxf.radius)
            if not math.isfinite(radius) or radius<=0:raise ValueError('Invalid schematic arc radius')
            def endpoint(angle):
                angle=math.radians(angle)
                return key((center.x+radius*math.cos(angle),center.y+radius*math.sin(angle)))
            a,b=endpoint(entity.dxf.start_angle),endpoint(entity.dxf.end_angle)
        else:raise ValueError('Exercise only supports native lines/arcs on the marked path')
        if a==b:raise ValueError('Zero-length path member')
        graph[a].add(b)
        graph[b].add(a)
        records.append({'handle':entity.dxf.handle,'type':entity.dxftype(),'start':a,'end':b})
    visited,pending=set(),[TOP]
    while pending:
        point=pending.pop()
        if point in visited:continue
        visited.add(point)
        pending.extend(graph.get(point,set())-visited)
    connected=TOP in graph and FLOOR in visited
    all_connected=bool(graph) and set(graph)<=visited
    branches=[p for p,neighbours in graph.items() if len(neighbours)>2]
    return {'ok':connected and all_connected and not branches,'end_to_end_connected':connected,
            'all_marked_members_connected':all_connected,'unexpected_branch_points':branches,
            'native_geometry':records,'schematic_units':True,'engineering_approval':False,
            'limits':'Endpoint continuity of a marked teaching path only; no thickness, adhesion, material compatibility, water test or project compliance assessment'}


def draw(path,variant='continuous',render=True):
    if variant not in {'continuous','floor_gap','missing_upstand'}:raise ValueError('Unknown training variant')
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    doc=ezdxf.new('R2013')
    doc.units=0
    for layer,color,weight in [('BASE',8,25),('MEMBRANE',1,35),('NOTE',7,13)]:doc.layers.add(layer,color=color,lineweight=weight)
    font=Path('C:/Windows/Fonts/msyh.ttc')
    doc.styles.new('TRAIN',dxfattribs={'font':str(font) if font.exists() else 'Arial.ttf'})
    m=doc.modelspace()
    def text(value,at,height=7):m.add_text(value,dxfattribs={'insert':at,'height':height,'style':'TRAIN','layer':'NOTE'})
    m.add_lwpolyline([(-45,-45),(300,-45),(300,0),(0,0),(0,200),(-45,200)],close=True,dxfattribs={'layer':'BASE'})
    if variant!='missing_upstand':m.add_line(TOP,(0,20),dxfattribs={'layer':'MEMBRANE'})
    m.add_arc((20,20),20,180,270,dxfattribs={'layer':'MEMBRANE'})
    m.add_line((40 if variant=='floor_gap' else 20,0),FLOOR,dxfattribs={'layer':'MEMBRANE'})
    text('墙地交界防水连续性 · 原理示意训练',(-45,230),10)
    text('基层（示意）',(100,-28))
    text('红线仅代表训练路径，不表示材料层厚',(-45,215),7)
    text('坐标无工程单位；不是施工采用图',(-45,-75),8)
    text({'continuous':'训练题：路径连续','floor_gap':'错误题：转角与大面间断开','missing_upstand':'错误题：缺少上翻路径'}[variant],(-45,-92),8)
    m.add_line((8,9),(80,65),dxfattribs={'layer':'NOTE'})
    text('转角过渡（示意）',(82,65),7)
    doc.saveas(path)
    result=endpoint_check(path)
    result.update(path=str(path.resolve()),sha256=file_hash(path),variant=variant)
    if render:result['preview']=render_dxf(path,path.with_suffix('.png'))
    return result


def main():
    directory=ROOT/'runtime/training/waterproof-continuity'
    results={v:draw(directory/(v+'.dxf'),v) for v in ['continuous','floor_gap','missing_upstand']}
    success=results['continuous']['ok'] and not results['floor_gap']['ok'] and not results['missing_upstand']['ok']
    report={'ok':success,'topic':'墙地交界标记路径连续性','drawing_type':'unitless original schematic training','results':results,
            'not_checked':['工程尺寸和标高','具体材料层厚与相容性','接缝和收头构造完整性','现场试验及规范符合性']}
    atomic_json(directory/'exercise.json',report)
    print(json.dumps({'ok':success,'report':str(directory/'exercise.json'),
                      'cases':{k:v['ok'] for k,v in results.items()}},ensure_ascii=False,indent=2))
    return 0 if success else 1

if __name__=='__main__':sys.exit(main())
