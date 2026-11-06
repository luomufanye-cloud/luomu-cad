import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import ezdxf
import pytest
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from redraw_delivery import audit_reference,review_findings,sha
from verify_redraw import audit
from luomu_cad.reference_geometry import PageTransform


def fixture(tmp_path):
    source=tmp_path/'original-reference.txt';source.write_text('Original exercise: wall 3000; label Plan; upper right quarter arc',encoding='utf-8')
    doc=ezdxf.new('R2018',setup=True);doc.units=4;m=doc.modelspace()
    wall=m.add_line((0,0),(3000,0))
    arc=m.add_arc((1000,1000),500,0,90)
    text=m.add_text('Plan',dxfattribs={'insert':(100,2000),'height':100})
    dim=m.add_linear_dim(base=(0,500),p1=(0,0),p2=(3000,0),override={'dimlfac':1,'dimtxt':100});dim.render()
    # These values belong to the independent exercise definition, not entity readback.
    specs=[('wall','LINE',{'start':[0,0,0],'end':[3000,0,0]}),
           ('door','ARC',{'center':[1000,1000,0],'radius':500,'start_angle':0,'end_angle':90}),
           ('title','TEXT',{'text':'Plan','at':[100,2000,0],'height':100,'rotation':0}),
           ('dimension','DIMENSION',{'start':[0,0,0],'end':[3000,0,0],'measurement':3000,'dimlfac':1,
                                   'line_at':[0,500,0],'display_text':'3000','style':{'dimtxt':100}})]
    inv={'schema_version':1,'source_sha256':sha(source),'page':0,'view':'Original exercise',
         'units':4,'delivery_target':'offline_dxf','review_regions':['full_view','door_and_dimensions'],
         'objects':[{'id':name,'kind':kind,'expected':value,'source_locator':'Exercise object '+name,
                     'tolerance':.01,'presentation':{'linetype':'CONTINUOUS'}} for name,kind,value in specs]}
    mapping=dict(zip([s[0] for s in specs],[e.dxf.handle for e in [wall,arc,text,dim.dimension]]))
    path=tmp_path/'output.dxf';doc.saveas(path)
    return doc,path,source,inv,mapping


def test_independent_reference_and_full_mapping(tmp_path):
    _,path,source,inv,mapping=fixture(tmp_path)
    assert audit_reference(path,inv,mapping,source)['checks_passed']
    mapping.pop('dimension')
    r=audit_reference(path,inv,mapping,source)
    assert 'REFERENCE_OBJECT_MISSING:dimension' in r['errors']
    assert any(e.startswith('UNMAPPED_OUTPUT') for e in r['errors'])


@pytest.mark.parametrize('fault',['mirrored_arc','line_pattern','partial_dimension','extra_static','moved_chain','text_loss','source_hash'])
def test_actual_failure_patterns_are_rejected(tmp_path,fault):
    doc,path,source,inv,mapping=fixture(tmp_path)
    if fault=='mirrored_arc':doc.entitydb[mapping['door']].dxf.start_angle=270
    if fault=='line_pattern':doc.entitydb[mapping['wall']].dxf.linetype='CENTER'
    if fault=='partial_dimension':mapping.pop('dimension')
    if fault=='extra_static':doc.modelspace().add_text('2200')
    if fault=='moved_chain':doc.entitydb[mapping['dimension']].dxf.defpoint=(0,-500,0)
    if fault=='text_loss':doc.entitydb[mapping['title']].dxf.text='???'
    if fault=='source_hash':source.write_text('Another source',encoding='utf-8')
    doc.saveas(path)
    assert not audit_reference(path,inv,mapping,source)['checks_passed']


def test_generator_self_consistency_cannot_override_reference(tmp_path):
    doc,path,source,inv,mapping=fixture(tmp_path)
    entity=doc.entitydb[mapping['dimension']]
    entity.dxf.defpoint2=(0,1000,0);entity.dxf.defpoint3=(3000,1000,0)
    doc.saveas(path)
    self_contract={'source':'generated list','units':4,'texts':['Plan'],
        'dimensions':[{'handle':entity.dxf.handle,'start':[0,1000,0],'end':[3000,1000,0],
                       'measurement':3000,'dimlfac':1,'tolerance':.01}]}
    assert audit(path,self_contract)['checks_passed']
    assert not audit_reference(path,inv,mapping,source)['checks_passed']


def test_cjk_mapping_is_in_the_redraw_gate(tmp_path):
    doc,path,_,_,mapping=fixture(tmp_path)
    doc.styles.new('CJK',dxfattribs={'font':'simsun.ttc'})
    text=doc.entitydb[mapping['title']];text.dxf.text='平面图';text.dxf.style='CJK';doc.saveas(path)
    contract={'source':'original Chinese label','units':4,'texts':['平面图'],'dimensions':[],
              'dimensions_absent_reason':'text-focused diagnostic'}
    assert any('cjk_typeface_missing' in e for e in audit(path,contract)['errors'])
    doc.styles.get('CJK').set_extended_font_data('SimSun');doc.saveas(path)
    assert audit(path,contract)['checks_passed']


def test_legacy_self_check_is_not_default_delivery_pass(tmp_path):
    _,path,_,_,_=fixture(tmp_path)
    contract={'source':'partial legacy fixture','units':4,'dimensions':[],
              'dimensions_absent_reason':'Only title checked','texts':['Plan']}
    con=tmp_path/'legacy.json';con.write_text(json.dumps(contract),encoding='utf-8')
    report=tmp_path/'legacy-report.json'
    cmd=[sys.executable,str(Path(__file__).parents[1]/'scripts/verify_redraw.py'),str(path),str(con),'--report',str(report)]
    assert subprocess.run(cmd,capture_output=True).returncode==1
    assert not json.loads(report.read_text())['complete_redraw_accepted']
    assert subprocess.run(cmd+['--structural-only'],capture_output=True).returncode==0
    assert not json.loads(report.read_text())['complete_redraw_accepted']


def test_cli_full_gate_requires_current_review(tmp_path):
    _,path,source,inv,mapping=fixture(tmp_path)
    ref=audit_reference(path,inv,mapping,source)
    review={k:ref[k] for k in ('source_sha256','drawing_sha256','inventory_sha256')}
    review.update(reviewer='Synthetic review metadata for gate regression; not host acceptance',regions={})
    for name in ('source.png','output.png'):Image.new('RGB',(100,100),'white').save(tmp_path/name)
    for region in inv['review_regions']:
        review['regions'][region]={'reviewed':True,'observations':'Synthetic gate fixture','unresolved':[],
            **{key:{'path':key+'.png','sha256':sha(tmp_path/(key+'.png'))} for key in ('source','output')}}
    assert not review_findings(review,ref,inv,tmp_path)
    invpath=tmp_path/'inventory.json';invpath.write_text(json.dumps(inv),encoding='utf-8')
    con=tmp_path/'mapping.json';con.write_text(json.dumps({'reference_map':mapping}),encoding='utf-8')
    rev=tmp_path/'review.json';rev.write_text(json.dumps(review),encoding='utf-8')
    report=tmp_path/'report.json'
    cmd=[sys.executable,str(Path(__file__).parents[1]/'scripts/verify_redraw.py'),str(path),str(con),
         '--report',str(report),'--reference-inventory',str(invpath),'--source',str(source)]
    assert subprocess.run(cmd,capture_output=True).returncode==1
    assert subprocess.run(cmd+['--review',str(rev)],capture_output=True).returncode==0
    review['drawing_sha256']='0'*64
    assert 'STALE_REVIEW:drawing_sha256' in review_findings(review,ref,inv,tmp_path)
    inv['delivery_target']='live_cad'
    assert 'NATIVE_CAD_REVIEW_REQUIRED' in review_findings(review,ref,inv,tmp_path)


@pytest.mark.parametrize('start',[0,90,180,270])
def test_reflection_transforms_arc_endpoints_and_sweep(start):
    import math
    transform=PageTransform(2,(10,20))
    result=transform.arc((30,40),5,start,start+90)
    doc=ezdxf.new();arc=doc.modelspace().add_arc(**result)
    def point(angle):return transform.point((30+5*math.cos(math.radians(angle)),40+5*math.sin(math.radians(angle))))
    assert arc.start_point.isclose(point(start+90))
    assert arc.end_point.isclose(point(start))
    assert (arc.dxf.end_angle-arc.dxf.start_angle)%360==90


def test_cubic_is_exact_after_reflection_and_readback(tmp_path):
    transform=PageTransform(10,(4,5));controls=[(0,0),(2,3),(5,3),(7,0)]
    doc=ezdxf.new();spline=transform.add_cubic(doc.modelspace(),controls)
    path=tmp_path/'curve.dxf';doc.saveas(path)
    curve=ezdxf.readfile(path).modelspace().query('SPLINE')[0].construction_tool()
    for i in range(101):
        t=i/100;u=1-t
        p=[u**3*controls[0][k]+3*u*u*t*controls[1][k]+3*u*t*t*controls[2][k]+t**3*controls[3][k] for k in (0,1)]
        assert curve.point(t).isclose(transform.point(p),abs_tol=1e-8)
