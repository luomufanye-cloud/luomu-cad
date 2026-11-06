import copy
import json
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from luomu_cad.cli import unpack
from luomu_cad.jobs import Jobs
from luomu_cad.plan import validate_spec,new_document,draw_groups,measured_check
from luomu_cad.storage import ROOT


def furnished():
    spec=json.loads((ROOT/'examples/two-room.json').read_text(encoding='utf-8'))
    spec.update(deliverable='furnished_plan',floor_boundary=[[0,0],[9000,0],[9000,6000],[0,6000]],
        furniture_requirements={'R1':['sofa'],'R2':['bed']},
        furniture=[{'id':'s1','kind':'sofa','room':'R1','at':[975,1500],'width':1800,'depth':850,'rotation':90,
                    'placement':{'mode':'wall','wall':'EXT','gap':0},'clearances':{'front':600},'clearance_basis':'Synthetic design input, mm'},
                   {'id':'b1','kind':'bed','room':'R2','at':[6500,3875],'width':1800,'depth':2000,
                    'placement':{'mode':'wall','wall':'EXT','gap':0},'clearances':{'front':600,'left':600,'right':500},'clearance_basis':'Synthetic design input, mm'}],
        clear_zones=[{'id':'passage','at':[3500,1500],'width':900,'depth':3000}])
    return spec


def test_original_tool_error_is_preserved():
    original='Openings overlap or leave less than 1 mm between them'
    result=SimpleNamespace(structuredContent=None,isError=True,content=[SimpleNamespace(type='text',text=original)])
    assert unpack(result)=={'ok':False,'error':original,'error_type':'MCP_TOOL_ERROR'}


@pytest.mark.parametrize('scale',[25,50,100])
def test_paper_text_height_and_reading_direction_all_four_sides(tmp_path,scale):
    spec=furnished();spec['sheet']['scale']=scale
    spec.update(deliverable='geometry_plan',furniture=[],furniture_requirements={})
    spec['openings']=[dict(id=f'D{i}',kind='window',wall='EXT',offset=offset,width=700)
                      for i,offset in enumerate([1000,10000,16000,25000])]
    spec=validate_spec(spec);doc=new_document();owners,_=draw_groups(doc,spec)
    path=tmp_path/'directions.dxf';doc.saveas(path);saved=ezdxf.readfile(path)
    for dim in saved.modelspace().query('DIMENSION'):
        settings=dim.override()
        assert settings.get('dimtxt')/scale==3.5
        assert settings.get('dimclrt')==7 and settings.get('dimlfac')==1
        a,b=dim.dxf.defpoint2,dim.dxf.defpoint3
        assert b.x>=a.x-0.01 and (abs(a.x-b.x)>0.01 or b.y>=a.y)
        for text in dim.virtual_entities():
            if text.dxftype()=='MTEXT':
                direction=text.get_text_direction()
                angle=direction.angle_deg%360
                assert angle<90.001 or angle>359.999
    assert measured_check(path,spec,owners)['ok']


def test_main_envelope_not_balcony_axis_extents():
    spec=furnished()
    spec['walls'].append({'id':'balcony','axis':[[6000,0],[6000,-2000],[8000,-2000],[8000,0]],'thickness':100})
    spec['chains']={'wall_ids':['EXT'],'sides':['bottom','left']}
    spec=validate_spec(spec);doc=new_document();owners,_=draw_groups(doc,spec)
    assert sorted(doc.entitydb[h].get_measurement() for h in owners['overall-dim'])==[6250,9250]


def test_furniture_saved_readback_and_scoped_patch(tmp_path):
    spec=furnished();spec['chains']={'wall_ids':['EXT'],'levels':['openings','axes','overall'],
        'axis_x':[0,5000,9000],'axis_y':[0,6000],'sides':['bottom','left']}
    job=Jobs(tmp_path)
    original=job.generate('furnished',spec)
    assert original['ok'] and original['delivery_scope']['furniture_count']==2
    changed=job.patch('changed','furnished',original['revision'],'M2',{'width':800,'swing_side':'right'})
    assert changed['ok'] and changed['unrelated_entities_unchanged']
    assert changed['owners']['furniture:s1']==original['owners']['furniture:s1']
    doc=ezdxf.readfile(original['artifacts']['dxf']['path'])
    doc.entitydb[original['owners']['furniture:s1'][0]].dxf.insert=(100,100)
    path=tmp_path/'tampered.dxf';doc.saveas(path)
    assert not measured_check(path,validate_spec(spec),original['owners'])['ok']


@pytest.mark.parametrize('defect',['empty','requirement','wall','door','clearance','duplicate','wrong_room','overlap'])
def test_incomplete_or_conflicting_furniture_rejected(defect):
    spec=furnished()
    if defect=='empty':spec['furniture']=[]
    if defect=='requirement':spec['furniture_requirements']['R1'].append('table')
    if defect=='wall':spec['furniture'][0]['at']=[4900,1500]
    if defect=='door':spec['furniture'][0]['at']=[1000,200]
    if defect=='clearance':spec['furniture'][0]['at']=[3000,1500]
    if defect=='duplicate':spec['furniture'].append(spec['furniture'][0])
    if defect=='wrong_room':spec['furniture'][0]['room']='R2'
    if defect=='overlap':spec['furniture'].append({**spec['furniture'][0],'id':'extra'})
    with pytest.raises(ValueError):validate_spec(spec)


@pytest.mark.parametrize('side',['left','right'])
def test_swing_side_changes_leaf_not_door_location(side):
    spec=furnished();spec['furniture']=[];spec['deliverable']='geometry_plan';spec['furniture_requirements']={}
    spec['openings'][0]['swing_side']=side
    doc=new_document();owners,_=draw_groups(doc,validate_spec(spec))
    leaf=next(doc.entitydb[h] for h in owners['opening:M1'] if doc.entitydb[h].dxftype()=='LINE')
    assert tuple(leaf.dxf.start)==(1000,0,0)
    assert leaf.dxf.end.y==(1000 if side=='left' else -1000)


def test_sliding_door_has_door_entities_and_schedule():
    spec=furnished();spec['openings'][0]['kind']='sliding_door'
    doc=new_document();owners,_=draw_groups(doc,validate_spec(spec))
    entities=[doc.entitydb[h] for h in owners['opening:M1']]
    assert len([e for e in entities if e.dxftype()=='LWPOLYLINE' and e.dxf.layer=='DOOR'])==2
    assert not [e for e in entities if e.dxftype()=='ARC']


@pytest.mark.parametrize('defect,error',[
    ('missing','PLACEMENT_REQUIRED'),('floating','WALL_PLACEMENT'),
    ('wrong_wall','WALL_PLACEMENT'),('wrong_gap','WALL_PLACEMENT'),
    ('free_reason','PLACEMENT_REASON'),('use_missing','USE_SPACE_REQUIRED'),
    ('use_zero','USE_SPACE_REQUIRED'),('use_wall','USE_SPACE'),
    ('use_obstacle','USE_SPACE'),('window','WALL_PLACEMENT')])
def test_declared_relationships_reject_invalid_layout(defect,error):
    spec=furnished();bed=spec['furniture'][1]
    if defect=='missing':bed.pop('placement')
    if defect=='floating':bed['at']=[6500,2500]
    if defect=='wrong_wall':bed['placement']['wall']='INT'
    if defect=='wrong_gap':bed['placement']['gap']=100
    if defect=='free_reason':bed['placement']={'mode':'freestanding'}
    if defect=='use_missing':bed.pop('clearances')
    if defect=='use_zero':bed['clearances']={'front':0}
    if defect=='use_wall':bed['clearances']['back']=100
    if defect=='use_obstacle':
        spec['furniture'].append({'id':'chair','kind':'chair','at':[7000,3400],'width':400,'depth':400,
            'room':'R2','placement':{'mode':'freestanding','reason':'Synthetic counterexample'},
            'clearances':{'front':100},'clearance_basis':'Synthetic design input'})
    if defect=='window':spec['openings'].append({'id':'C3','wall':'EXT','kind':'window','offset':16000,'width':1000})
    with pytest.raises(ValueError,match=error):validate_spec(spec)


def test_intentional_freestanding_layout_and_wall_gap_are_supported():
    spec=furnished();bed=spec['furniture'][1]
    bed['at'][1]-=25;bed['placement']['gap']=25
    assert validate_spec(spec)
    sofa=spec['furniture'][0];sofa['at']=[1600,1500]
    sofa['placement']={'mode':'freestanding','reason':'Living area divider with a route behind the sofa'}
    sofa['clearances']['back']=600
    assert validate_spec(spec)


def test_readback_rejects_reversed_bed_with_same_bounding_box(tmp_path):
    spec=validate_spec(furnished());doc=new_document();owners,_=draw_groups(doc,spec)
    bed=doc.entitydb[owners['furniture:b1'][0]]
    bed.dxf.rotation=180;bed.dxf.insert=(8300,5875,0)
    path=tmp_path/'reversed.dxf';doc.saveas(path)
    assert not measured_check(path,spec,owners)['ok']
