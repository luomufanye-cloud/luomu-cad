"""Original mock wall penetration section; assigned dimensions are not installation specifications."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import ezdxf
from luomu_cad.storage import ROOT,atomic_json
from luomu_cad.qa import render_dxf,file_hash


def draw(path,variant):
    doc=ezdxf.new('R2013');doc.units=4
    m=doc.modelspace()
    for name,color in [('BASE',8),('MORTAR',3),('MEMBRANE',1),('TILE',4),('PIPE',5),('SEAL',2),('NOTE',7)]:doc.layers.add(name,color=color)
    def line(layer,a,b):m.add_line(a,b,dxfattribs={'layer':layer})
    # All mock geometry in mm. Pipe OD32, annulus6, backing12 and mortar3 are assigned inputs.
    for x,layer in [(0,'BASE'),(12,'BASE'),(15,'MEMBRANE'),(15.2032,'MEMBRANE'),(18.2032,'MORTAR'),(28.2032,'TILE')]:
        for a,b in [(0,28),(72,100)]:line(layer,(x,a),(x,b))
    for y in [34,66]:line('PIPE',(-20,y),(55,y))
    seal_x=5 if variant=='buried_seal' else 15
    line('SEAL',(seal_x,28),(seal_x,34))
    if variant!='missing_upper_seal':line('SEAL',(seal_x,66),(seal_x,72))
    # Separate movement-joint diagram: ordinary membrane stops at joint edges.
    line('MEMBRANE',(85,15),(120,15));line('MEMBRANE',(130,15),(165,15))
    if variant=='rigid_bridge':line('MEMBRANE',(120,15),(130,15))
    else:
        for a,b in [((110,16),(121,16)),((121,16),(121,8)),((121,8),(129,8)),((129,8),(129,16)),((129,16),(140,16))]:line('SEAL',a,b)
    for i,s in enumerate(['MOCK SECTION - mm - NOT A CONSTRUCTION SPEC',variant,'Backing12 / bond3 / membrane0.2032 / bond3 / tile10','Assigned pipe OD32 / opening44 / seal annulus6','Right: separate movement-joint topology, no capacity inferred']):
        m.add_text(s,dxfattribs={'height':3,'insert':(-20,125-i*5),'layer':'NOTE'})
    doc.saveas(path)


def inspect(path):
    d=ezdxf.readfile(path);m=d.modelspace()
    seals=list(m.query('LINE[layer=="SEAL"]'))
    pipe=list(m.query('LINE[layer=="PIPE"]'))
    ys=sorted(e.dxf.start.y for e in pipe)
    issues=[]
    if d.units!=4 or ys!=[34,66]:issues.append('units or mock pipe OD')
    for a,b in [(28,34),(66,72)]:
        if not any(abs(e.dxf.start.x-15)<1e-6 and abs(e.dxf.end.x-15)<1e-6 and sorted([e.dxf.start.y,e.dxf.end.y])==[a,b] for e in seals):issues.append('missing seal at membrane plane '+str((a,b)))
    for e in m.query('LINE[layer=="MEMBRANE"]'):
        if e.dxf.start.x<=120 and e.dxf.end.x>=130:issues.append('rigid membrane bridges movement joint')
    return {'ok':not issues,'issues':issues,'pipe_od_mm':ys[-1]-ys[0],'engineering_approval':False}


def main():
    out=ROOT/'runtime/training/penetration-section';out.mkdir(parents=True,exist_ok=True)
    results={}
    for v in ['normal','missing_upper_seal','buried_seal','rigid_bridge']:
        p=out/(v+'.dxf');draw(p,v);r=inspect(p);assert r['ok']==(v=='normal'),r
        results[v]={**r,'sha256':file_hash(p)}
    # Source p7 gives about20% total movement, not200% break elongation; screening only.
    movement=[]
    for width,demand,expected in [(10,1.5,True),(10,2.5,False),(15,2.5,True)]:
        capacity=width*.20;ok=demand<=capacity;assert ok==expected
        movement.append({'assigned_width_mm':width,'assigned_total_movement_mm':demand,'arithmetic_screen_mm':capacity,'screen_pass':ok,'joint_design_approved':False})
    answers=[
        {'question':'Bare stainless drain flange with thin-set only?','answer':'Use the specified KERDI-FIX interface after removing grease; fleece flange is a different branch.'},
        {'question':'Rubber pipe-seal opening proves fit on any nominal pipe?','answer':'No. Identify actual OD and sealing surface; catalogue opening alone does not establish assembly compatibility.'},
        {'question':'Continuous rigid mortar and membrane across an existing expansion joint?','answer':'Separate the membrane and detail a flexible joint; preserve movement through finishes.'},
        {'question':'200% break elongation used as permissible movement?','answer':'Incorrect; table distinguishes about20% permissible total movement from about200% failure elongation.'},
        {'question':'Sealant skins after10min, so flood immediately?','answer':'Incorrect; skinning, through cure, mortar set and assembly test readiness are distinct.'},
        {'question':'6mm sealant is guaranteed fully cured after48h from3mm/day?','answer':'No. Arithmetic alone is not a cure guarantee; exposure geometry, conditions and system instructions control.'},
        {'question':'Work at3C because cured material tolerates below0C?','answer':'Incorrect; application minimum5C in the selected table differs from cured-service limits.'},
        {'question':'Water loss after covering a failed interface?','answer':'Locate leak path, expose and repair the matching interface, repeat applicable cure and assembly test before covering.'}]
    result={'ok':True,'geometry':results,'movement_screens':movement,'answered_cases':answers,'preview':render_dxf(out/'normal.dxf',out/'normal.png'),'assigned_inputs':'All dimensions except membrane8mil are mock training inputs; no manufacturer pipe-fit or joint sizing certification','actual_water_test_performed':False,'whole_pipe_topic_complete':False,'cad_contacted':False}
    atomic_json(out/'results.json',result)
    print(json.dumps({'ok':True,'path':str(out/'results.json'),'geometry_cases':4,'answered_cases':len(answers)},ensure_ascii=False))


if __name__=='__main__':main()
