"""Original offline exercises: documented support locations, drain levels and SI hydraulics.

Reference facts are in examples/fan-coil-training.json. Geometry is read back
from saved native DXF entities. Hydraulic inputs are authored training values;
the results never select a real product, approve a drain, or size an anchor.
"""
import copy
import json
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import ezdxf
from luomu_cad.qa import audit_dxf,file_hash,prepare_chinese_font,render_dxf
from luomu_cad.storage import ROOT,atomic_json


def specification():
    return json.loads((ROOT/'examples/fan-coil-training.json').read_text(encoding='utf-8'))


def positive(value,name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
        raise ValueError(f'{name} must be positive and finite')
    return float(value)


def hydraulic_case(load_kw,delta_t_k,density,cp,inside_diameter_mm,kv,other_loss_kpa,gravity=9.81):
    """SI steady liquid heat balance plus explicitly given quadratic resistance.

    Kv uses m3/h at a one-bar differential for water of relative density one;
    pressure is corrected by density/1000. No viscosity/glycol correction,
    valve authority, available pump curve or product rating is established.
    """
    values=[positive(v,n) for v,n in zip(
        [load_kw,delta_t_k,density,cp,inside_diameter_mm,kv,gravity],
        ['load_kw','delta_t_k','density','cp','inside_diameter_mm','kv','gravity'])]
    load_kw,delta_t_k,density,cp,inside_diameter_mm,kv,gravity=values
    if isinstance(other_loss_kpa,bool) or not isinstance(other_loss_kpa,(int,float)) or not math.isfinite(other_loss_kpa) or other_loss_kpa<0:
        raise ValueError('other_loss_kpa must be finite and nonnegative')
    mass_kg_s=load_kw/(cp*delta_t_k)  # kW = kJ/s.
    flow_m3_s=mass_kg_s/density
    flow_m3_h=flow_m3_s*3600
    area_m2=math.pi*(inside_diameter_mm/1000)**2/4
    valve_kpa=(flow_m3_h/kv)**2*(density/1000)*100
    total_kpa=valve_kpa+other_loss_kpa
    return {'mass_kg_s':mass_kg_s,'flow_m3_h':flow_m3_h,'flow_l_h':flow_m3_h*1000,
            'velocity_m_s':flow_m3_s/area_m2,'valve_loss_kpa':valve_kpa,
            'other_loss_kpa':other_loss_kpa,'total_loss_kpa':total_kpa,
            'required_head_m_for_given_losses':total_kpa*1000/(density*gravity),
            'engineering_approval':False,'limits':'Given steady liquid training inputs only; no real pump, pipe, valve authority or product selection approval'}


def readback(path,model,spec=None):
    """Check saved coordinates against the reviewed reference, never against labels."""
    spec=spec or specification()
    if model not in spec['reference']['models']:raise ValueError('No reviewed mounting reference for model')
    rule=spec['reference']['models'][model]
    doc=ezdxf.readfile(path);m=doc.modelspace();issues=[];points={}
    if doc.units!=4:issues.append('DXF units must be mm')
    for e in m.query('POINT'):
        if e.dxf.layer!='SUPPORT':continue
        if not e.has_xdata('LUOMU_TRAIN'):issues.append('untagged support');continue
        label=e.get_xdata('LUOMU_TRAIN')[0].value
        if label in points:issues.append('duplicate support label '+label)
        if abs(e.dxf.location.z)>0.01:issues.append('support outside stated XY exercise plane '+label)
        points[label]=[float(e.dxf.location.x),float(e.dxf.location.y)]
    if set(points)!=set(rule['support_points']):issues.append('support labels or count differ')
    for name,p in rule['support_points'].items():
        if name not in points or math.dist(points[name],p)>0.01:issues.append('support datum mismatch '+name)
    def one(kind,layer):
        found=[e for e in m.query(kind) if e.dxf.layer==layer]
        if len(found)!=1:issues.append(f'expected one {layer}');return None
        return found[0]
    drain=one('LWPOLYLINE','DRAIN');drain_records=[]
    if drain is not None:
        if abs(drain.dxf.elevation)>0.01:issues.append('drain outside stated XY exercise plane')
        pts=[(float(x),float(y)) for x,y in drain.get_points('xy')]
        if len(pts)!=3 or drain.closed or any(abs(v[0])>1e-9 for v in drain.get_points('b')):
            issues.append('expected three-vertex open straight drain exercise')
        if len(pts)==3:
            a,b,c=pts;lift=b[1]-a[1];run=c[0]-b[0]
            slope=(b[1]-c[1])/run if run>0 else None
            if abs(b[0]-a[0])>0.01:issues.append('lift is not immediately vertical in this exercise')
            if not 0<lift<=spec['reference']['maximum_drain_lift_mm']+0.01:issues.append('drain lift exceeds reference or is reversed')
            if slope is None or slope+1e-9<spec['reference']['minimum_downstream_slope']:issues.append('downstream slope below minimum or reversed')
            drain_records={'vertices':pts,'lift_mm':lift,'run_mm':run,'slope':slope}
    level=one('LINE','UNIT_LEVEL')
    if level is not None and abs(level.dxf.start.y-level.dxf.end.y)>0.01:issues.append('unit must be level; pipe slope is separate')
    ceiling=one('LINE','STRUCTURE');outlet=one('POINT','OUTLET_LEVEL')
    if ceiling is not None and outlet is not None and drain_records:
        available=ceiling.dxf.start.y
        if available<rule['minimum_ceiling_space_mm']:issues.append('ceiling space below model reference')
        if abs(outlet.dxf.location.y-drain_records['vertices'][0][1])>0.01:issues.append('outlet and drain elevation datums disagree')
        crest_above_ceiling=drain_records['vertices'][1][1]
        if crest_above_ceiling>=available:issues.append('drain crest collides with structural ceiling')
    native=audit_dxf(path)
    issues.extend('native DXF: '+f['kind'] for f in native['findings'])
    return {'ok':not issues,'issues':issues,'model':model,'support_points_mm':points,'drain':drain_records,
            'native_dimension_measurements':[d['measurement'] for d in native['dimensions']],
            'engineering_approval':False,'scope':'Reference support centres, schematic drain slope/lift/space, unit level and native DXF only; no structural or drainage capacity approval'}


def draw(path,variant='normal',model='FWH06AFN',render=True):
    allowed={'normal','corner_supports','centred_supports','excess_lift','flat_drain','tilted_unit','ceiling_collision'}
    if variant not in allowed:raise ValueError('Unknown exercise variant')
    spec=specification();rule=spec['reference']['models'][model];given=spec['authored_training_inputs']
    doc=ezdxf.new('R2013');doc.units=4;doc.appids.add('LUOMU_TRAIN');m=doc.modelspace()
    for name,color in [('SUPPORT',1),('GUIDE',8),('NOTE',7),('DIM',7),('DRAIN',5),('UNIT_LEVEL',3),('STRUCTURE',8),('OUTLET_LEVEL',7)]:doc.layers.add(name,color=color)
    def note(value,at,height=18):m.add_text(value,dxfattribs={'insert':at,'height':height,'layer':'NOTE'})
    def dim(a,b,base,angle=0):
        m.add_linear_dim(base=base,p1=a,p2=b,angle=angle,dxfattribs={'layer':'DIM'},override={'dimtxt':14,'dimasz':10,'dimexo':6,'dimgap':5}).render()
    w,h=rule['grid'];points=copy.deepcopy(rule['support_points'])
    if variant=='corner_supports':points=dict(zip(points,[[0,h],[w,h],[w,0],[0,0]]))
    if variant=='centred_supports':points={'T':[w/2,h],'R':[w,h/2],'B':[w/2,0],'L':[0,h/2]}
    m.add_lwpolyline([(0,0),(w,0),(w,h),(0,h)],close=True,dxfattribs={'layer':'GUIDE'})
    for label,(x,y) in points.items():
        e=m.add_point((x,y),dxfattribs={'layer':'SUPPORT'});e.set_xdata('LUOMU_TRAIN',[(1000,label)])
        m.add_circle((x,y),8,dxfattribs={'layer':'GUIDE'});note(label,(x+12,y+12),16)
    dim((0,0),(w,0),(0,-65));dim((0,0),(0,h),(-65,0),90)
    if model=='FWH06AFN':
        dim((0,h),points['T'],(0,h+55));dim(points['T'],(w,h),(0,h+55))
        dim((0,0),points['B'],(0,-115));dim(points['B'],(w,0),(0,-115))
        dim((w,0),points['R'],(w+65,0),90);dim(points['R'],(w,h),(w+65,0),90)
        dim((0,0),points['L'],(-120,0),90);dim(points['L'],(0,h),(-120,0),90)
    note(f'{model} 吊杆定位训练 / mm',(0,1100),26)
    note('点与圆圈为定位符号，不是孔槽轮廓；按手册原始朝向',(0,1050),18)
    note('参考：WC66000644-02，PDF35-36页 / Fig4或Fig5',(0,1005),16)
    # This separate view uses false-ceiling elevation zero consistently.
    # Given outlet/building elevations are authored, never read off pixels.
    x0=1250;outlet_z=given['outlet_above_false_ceiling_mm'];lift=1000 if variant=='excess_lift' else given['drain_lift_mm']
    run=given['downstream_run_mm'];slope=0 if variant=='flat_drain' else given['downstream_slope']
    drain=[(x0,outlet_z),(x0,outlet_z+lift),(x0+run,outlet_z+lift-run*slope)]
    m.add_lwpolyline(drain,dxfattribs={'layer':'DRAIN'})
    ceiling=700 if variant=='ceiling_collision' else given['ceiling_space_mm']
    m.add_line((x0,ceiling),(x0+run,ceiling),dxfattribs={'layer':'STRUCTURE'})
    note(f'结构顶 z=+{ceiling}（训练给定）',(x0,ceiling+25),18)
    m.add_line((x0-250,0),(x0+run,0),dxfattribs={'layer':'GUIDE'})
    note('吊顶基准 z=0',(x0-220,25),17)
    m.add_point((x0,outlet_z),dxfattribs={'layer':'OUTLET_LEVEL'})
    m.add_line((x0-200,outlet_z),(x0,outlet_z+(20 if variant=='tilted_unit' else 0)),dxfattribs={'layer':'UNIT_LEVEL'})
    dim(drain[0],drain[1],(x0-100,0),90);dim(drain[1],drain[2],(0,outlet_z+lift+70))
    note(f'设备出口 z=+{outlet_z}',(x0+35,outlet_z-45),17)
    note(f'提升顶 z=+{outlet_z+lift}',(x0+35,outlet_z+lift+20),17)
    note(f'下游端 z=+{outlet_z+lift-run*slope:g}',(x0+run-320,outlet_z+lift-run*slope-50),17)
    note('冷凝水路径：吊顶标高为0，绿色为设备水平基准符号',(x0,-110),18)
    note(f'训练输入：出口标高+{outlet_z} / 结构标高+{ceiling} / 下游坡度{slope*100:g}%',(x0,-155),16)
    note('设备保持水平；排水管另设坡度；蓝线不代表管径',(x0,-200),16)
    note('参考：手册PDF35页 Fig1；未核验排水流量、隔气及支吊架承载力',(x0,-245),15)
    note('训练结果 '+variant,(0,960),20)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);doc.saveas(path);prepare_chinese_font(path)
    result=readback(path,model,spec);result.update(path=str(path.resolve()),sha256=file_hash(path),variant=variant)
    if render:result['preview']=render_dxf(path,path.with_suffix('.png'))
    return result


def main():
    spec=specification();g=spec['authored_training_inputs'];r=spec['reference'];directory=ROOT/'runtime/training/fan-coil-installation'
    variants=['normal','corner_supports','centred_supports','excess_lift','flat_drain','tilted_unit','ceiling_collision']
    results={v:draw(directory/(v+'.dxf'),v,render=v in {'normal','corner_supports','flat_drain'}) for v in variants}
    results['different_model']=draw(directory/'different_model.dxf',model='FWH02AFN',render=True)
    base=hydraulic_case(g['heat_load_kw'],g['water_delta_t_k'],g['density_kg_m3'],g['specific_heat_kj_kg_k'],g['hydronic_pipe_inside_diameter_mm'],r['cooling_straight_valve_kv'],g['other_circuit_loss_kpa_at_base_flow'],g['gravity_m_s2'])
    ratio=g['water_delta_t_k']/g['transfer_delta_t_k']
    transfer=hydraulic_case(g['heat_load_kw'],g['transfer_delta_t_k'],g['density_kg_m3'],g['specific_heat_kj_kg_k'],g['hydronic_pipe_inside_diameter_mm'],r['cooling_straight_valve_kv'],g['other_circuit_loss_kpa_at_base_flow']*ratio**2,g['gravity_m_s2'])
    wrong_kv=hydraulic_case(g['heat_load_kw'],g['water_delta_t_k'],g['density_kg_m3'],g['specific_heat_kj_kg_k'],g['hydronic_pipe_inside_diameter_mm'],r['cooling_bypass_valve_kv'],g['other_circuit_loss_kpa_at_base_flow'],g['gravity_m_s2'])
    success=results['normal']['ok'] and results['different_model']['ok'] and all(not results[v]['ok'] for v in variants[1:])
    report={'ok':success,'script_sha256':file_hash(__file__),'spec_sha256':file_hash(ROOT/'examples/fan-coil-training.json'),'reference':r,'authored_inputs':g,'drawings':results,'hydraulics':{'base':base,'smaller_delta_t':transfer,'wrong_bypass_kv_for_straight_branch':wrong_kv,'flow_ratio':transfer['flow_m3_h']/base['flow_m3_h'],'head_ratio':transfer['required_head_m_for_given_losses']/base['required_head_m_for_given_losses']},'engineering_approval':False,'assessment_scope':'Dimensioned mounting centres, stated drain geometry, SI heat balance and given resistance model; actual project not checked'}
    atomic_json(directory/'exercise.json',report)
    print(json.dumps({'ok':success,'report':str(directory/'exercise.json'),'cases':{k:v['ok'] for k,v in results.items()},'base_hydraulics':base,'changed_delta_t_hydraulics':transfer},ensure_ascii=False,indent=2))
    return 0 if success else 1

if __name__=='__main__':sys.exit(main())
