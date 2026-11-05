"""Pipe-collar catalogue reading and seam/test diagnosis exercises, not site approval."""
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import ezdxf
from luomu_cad.storage import ROOT, atomic_json
from luomu_cad.qa import render_dxf, file_hash


def draw(path,variant):
    doc=ezdxf.new('R2013')
    doc.units=4
    m=doc.modelspace()
    for layer,color in [('COLLAR',1),('OPENING',5),('SHEET_A',3),('SHEET_B',6),('NOTE',7)]:
        doc.layers.add(layer,color=color)
    # Catalogue SI dimensions: KM5117/22; not a measured pipe-fit specification.
    m.add_circle((0,0),75,dxfattribs={'layer':'COLLAR'})
    if variant!='missing_opening':
        m.add_circle((0,0),110 if variant=='unit_error' else 11,dxfattribs={'layer':'OPENING'})
    overlap=40 if variant=='short_overlap' else 52  # explicit mock panel position
    m.add_lwpolyline([(200,0),(400+overlap,0),(400+overlap,80),(200,80)],close=True,dxfattribs={'layer':'SHEET_A'})
    m.add_lwpolyline([(400,0),(600,0),(600,80),(400,80)],close=True,dxfattribs={'layer':'SHEET_B'})
    for i,label in enumerate(['CATALOGUE / MOCK SEAM STUDY - mm',variant,'Collar OD150 / opening22; seam overlap52 adopted',
                              'Collar ring is not the full installed node; no pipe fit inferred']):
        m.add_text(label,dxfattribs={'height':8,'insert':(-100,145-i*18),'layer':'NOTE'})
    doc.saveas(path)


def measure(path):
    doc=ezdxf.readfile(path)
    m=doc.modelspace()
    outer=list(m.query('CIRCLE[layer=="COLLAR"]'))
    inner=list(m.query('CIRCLE[layer=="OPENING"]'))
    issues=[]
    if len(outer)!=1 or len(inner)!=1:return {'ok':False,'issues':['missing catalogue circle']}
    od=2*outer[0].dxf.radius
    hole=2*inner[0].dxf.radius
    if doc.units!=4 or abs(od-150)>1e-6 or abs(hole-22)>1e-6:
        issues.append('catalogue SI dimension/units mismatch')
    if hole>=od:issues.append('opening is not inside collar')
    a=list(m.query('LWPOLYLINE[layer=="SHEET_A"]'))[0]
    b=list(m.query('LWPOLYLINE[layer=="SHEET_B"]'))[0]
    overlap=min(max(p[0] for p in a.get_points()),max(p[0] for p in b.get_points()))-max(min(p[0] for p in a.get_points()),min(p[0] for p in b.get_points()))
    # Manufacturer describes 2in/50mm; use52mm in this training to satisfy either expression.
    if overlap<50.8:issues.append('seam overlap below conservative training threshold')
    return {'ok':not issues,'issues':issues,'outer_mm':od,'opening_mm':hole,
        'measured_overlap_mm':overlap,'ring_area_mm2':math.pi*((od/2)**2-(hole/2)**2),
        'engineering_approval':False}


def diagnose(case):
    if not case['plug_verified']:return 'repair_test_plug_before_assessing_membrane'
    if case['hours_since_last_bond']<24:return 'defer_water_test_for_mortar_cure'
    if case['cold_conditions']:return 'extend_cure_and_verify_actual_conditions_no_fixed_time_pass'
    if not case['level_marked'] or case['observed_hours']<24:return 'incomplete_mock_test_record'
    if case['water_loss']:return 'investigate_plug_and_assembly_not_unique_membrane_diagnosis'
    return 'mock_test_record_passes_given_conditions'


def main():
    out=ROOT/'runtime/training/membrane-interfaces'
    out.mkdir(parents=True,exist_ok=True)
    geometry={}
    for variant in ['normal','unit_error','missing_opening','short_overlap']:
        path=out/(variant+'.dxf')
        draw(path,variant)
        result=measure(path)
        assert result['ok']==(variant=='normal'),result
        geometry[variant]={**result,'sha256':file_hash(path)}
    preview=render_dxf(out/'normal.dxf',out/'normal.png')
    good=dict(plug_verified=True,hours_since_last_bond=26,cold_conditions=False,level_marked=True,observed_hours=24,water_loss=False)
    questions=[('normal',{},'mock_test_record_passes_given_conditions'),
        ('leaking_plug',{'plug_verified':False},'repair_test_plug_before_assessing_membrane'),
        ('early_start',{'hours_since_last_bond':10},'defer_water_test_for_mortar_cure'),
        ('cold_same_schedule',{'cold_conditions':True},'extend_cure_and_verify_actual_conditions_no_fixed_time_pass'),
        ('no_level_mark',{'level_marked':False},'incomplete_mock_test_record'),
        ('short_observation',{'observed_hours':3},'incomplete_mock_test_record'),
        ('drop_without_cause',{'water_loss':True},'investigate_plug_and_assembly_not_unique_membrane_diagnosis')]
    answers=[]
    for name,change,expected in questions:
        given={**good,**change}
        answer=diagnose(given)
        assert answer==expected,(name,answer)
        answers.append({'case':name,'mock_input':given,'answer':answer})
    completed=datetime(2026,11,5,8)
    band=[]
    for offset,expected in [(0,True),(10,True),(15,False)]:
        left,right=125/2-offset,125/2+offset
        ok=min(left,right)>=52  # self-selected margin; not a factory tolerance
        assert ok==expected
        assert abs(left+right-125)<1e-9
        band.append({'catalogue_si_width_mm':125,'butt_seam_gap_mm':0,
            'mock_center_offset_mm':offset,'left_lap_mm':left,'right_lap_mm':right,
            'adopted_min_lap_mm':52,'ok':ok})
    result={'geometry':geometry,'mock_test_diagnosis':answers,'preview':preview,
        'band_centering_calculation':band,
        'time_calculation':{'last_bond_completed':completed.isoformat(),
                            'room_temperature_earliest_start':(completed+timedelta(hours=24)).isoformat(),
                            'adopted24h_observation_end':(completed+timedelta(hours=48)).isoformat()},
        'mil_conversion':{'4mil_mm':4*0.0254,'8mil_mm':8*0.0254},
        'scope':'Selected catalogue dimensions, mock seam geometry and mock inspection diagnosis; not installed collar qualification',
        'actual_water_test_performed':False,'cad_contacted':False}
    atomic_json(out/'results.json',result)
    print(json.dumps({'ok':True,'geometry_cases':len(geometry),'diagnostic_cases':len(answers),'path':str(out/'results.json')},ensure_ascii=False))


if __name__=='__main__':main()
