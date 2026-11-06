"""Original regression exercises for PDF presentation failures, no project assets."""
import json
import math
from pathlib import Path
import sys

import ezdxf
import pytest
from luomu_cad.reference_geometry import PageTransform
from luomu_cad.reference_presentation import (
    stroke_attributes, measured_text_attributes, font_ink_bounds, add_solid_fill,
)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from redraw_delivery import audit_reference, sha, review_findings
from preflight import runtime_identity


def test_pdf_hairline_is_not_replaced_by_uniform_thick_layer(tmp_path):
    doc=ezdxf.new();m=doc.modelspace()
    hair=m.add_line((0,0),(100,0),dxfattribs=stroke_attributes((.9,.9,.9),0))
    thick=m.add_line((0,5),(100,5),dxfattribs=stroke_attributes((.1,.2,.3),.72,.5))
    path=tmp_path/'lineweights.dxf';doc.saveas(path);lines=list(ezdxf.readfile(path).modelspace())
    assert lines[0].dxf.lineweight==0
    assert lines[1].dxf.lineweight==25 # .72 pt = .254 mm, representable as .25 mm
    assert lines[0].rgb==(230,230,230)
    assert abs(lines[1].transparency-.5)<=1/255
    with pytest.raises(ValueError):stroke_attributes((0,0,0),100)


@pytest.mark.parametrize('direction',[(1,0),(0,1),(0,-1),(-1,0),(.6,.8)])
def test_text_fits_independent_measured_bounds_after_reflection(direction,tmp_path):
    # Original source glyph ink rectangle is 20 by 8 page units. PDF font size
    # could be 12: it must not become CAD cap height=120 at scale 10.
    t=PageTransform(10,(0,0))
    attrs=measured_text_attributes(t,source_ink_bounds=(1,-2,21,6),source_origin=(40,50),
        source_direction=direction,target_ink_bounds=(.1,-.25,2.1,.75))
    assert attrs['height']==80 and attrs['width']==1.25
    doc=ezdxf.new();e=doc.modelspace().add_text('Ab',dxfattribs=attrs)
    path=tmp_path/'text.dxf';doc.saveas(path);e=ezdxf.readfile(path).modelspace().query('TEXT')[0]
    angle=math.radians(e.dxf.rotation);u=(math.cos(angle),math.sin(angle));v=(-u[1],u[0])
    origin=t.point((40,50));d=(direction[0],-direction[1])
    for tx,ty,sx,sy in [(.1,-.25,1,-2),(2.1,.75,21,6)]:
        actual=[e.dxf.insert[k]+u[k]*tx*e.dxf.height*e.dxf.width+v[k]*ty*e.dxf.height for k in (0,1)]
        expected=[origin[0]+(d[0]*sx-d[1]*sy)*10,origin[1]+(d[1]*sx+d[0]*sy)*10]
        assert actual==pytest.approx(expected)


def test_font_measurement_uses_existing_real_glyphs():
    import matplotlib
    path=Path(matplotlib.get_data_path())/'fonts/ttf/DejaVuSans.ttf'
    bounds=font_ink_bounds('Abg',path)
    assert bounds[2]>bounds[0] and bounds[3]>bounds[1]
    with pytest.raises(ValueError,match='glyph'):font_ink_bounds('\U0010ffff',path)
    with pytest.raises(ValueError):font_ink_bounds('test',path.with_name('missing.ttf'))


def test_fill_holes_and_fill_only_semantics_survive_roundtrip(tmp_path):
    doc=ezdxf.new();doc.units=4
    loops=[{'role':'outer','points':[(0,0),(100,0),(100,100),(0,100)]},
           {'role':'hole','points':[(20,20),(30,20),(30,30),(20,30)]}]
    hatch=add_solid_fill(doc.modelspace(),loops,dxfattribs=stroke_attributes((.5,.5,.5),0))
    path=tmp_path/'fill.dxf';doc.saveas(path)
    source=tmp_path/'source.json';source.write_text(json.dumps(loops))
    inv={'schema_version':1,'source_sha256':sha(source),'page':0,'view':'Original fill-only polygon',
         'units':4,'delivery_target':'offline_dxf','objects':[{'id':'fill','kind':'HATCH','source_locator':'polygon 1',
         'tolerance':.01,'presentation':{'linetype':'CONTINUOUS','rgb':[128,128,128],'opacity':1,'lineweight':0},
         'expected':{'solid':True,'hatch_style':0,'loops':[
             {'points':[[x,y,0] for x,y in l['points']],'closed':True,'external':l['role']=='outer'} for l in loops]}}]}
    mapping={'fill':hatch.dxf.handle}
    assert len(ezdxf.readfile(path).modelspace())==1 # No spurious outline entities
    assert audit_reference(path,inv,mapping,source)['checks_passed']
    hatch.paths.paths.pop();doc.saveas(path)
    assert 'REFERENCE_GEOMETRY:fill' in audit_reference(path,inv,mapping,source)['errors']


@pytest.mark.parametrize('fault',['weight','rgb','opacity','width','font','mirrored_text'])
def test_presentation_corruption_rejected_even_with_correct_coordinates(tmp_path,fault):
    from test_redraw_delivery import fixture
    doc,path,source,inv,mapping=fixture(tmp_path)
    e=doc.entitydb[mapping['title']]
    if fault=='weight':e.dxf.lineweight=13
    if fault=='rgb':e.rgb=(100,100,100)
    if fault=='opacity':e.transparency=.5
    if fault=='width':e.dxf.width=.72
    if fault=='font':doc.styles.get(e.dxf.style).dxf.font='unavailable.ttf'
    if fault=='mirrored_text':e.dxf.text_generation_flag=2
    doc.saveas(path)
    assert not audit_reference(path,inv,mapping,source)['checks_passed']


def test_mixed_background_review_is_not_visual_equivalence(tmp_path):
    from PIL import Image
    from test_redraw_delivery import fixture
    _,path,source,inv,mapping=fixture(tmp_path)
    ref=audit_reference(path,inv,mapping,source)
    for name in ('source','output'):Image.new('RGB',(20,20),'white').save(tmp_path/(name+'.png'))
    item={'reviewed':True,'observations':'Original controlled review fixture','unresolved':[],
          **{k:{'path':k+'.png','sha256':sha(tmp_path/(k+'.png')),'background_rgb':[255,255,255]} for k in ('source','output')}}
    review={k:ref[k] for k in ('source_sha256','drawing_sha256','inventory_sha256')}
    review.update(reviewer='Test fixture',regions={r:item for r in inv['review_regions']})
    assert not review_findings(review,ref,inv,tmp_path)
    item['output']['background_rgb']=[0,0,0]
    assert any('BACKGROUND_MISMATCH' in e for e in review_findings(review,ref,inv,tmp_path))


def test_runtime_version_is_actual_import_not_folder_label(tmp_path):
    (tmp_path/'pyproject.toml').write_text('[project]\nversion="0.0.0"\n')
    identity=runtime_identity(tmp_path)
    assert identity['source_version']=='0.0.0'
    assert not identity['versions_match']
    assert identity['runtime_version']!='0.0.0'
    import subprocess
    result=subprocess.run([sys.executable,str(Path(__file__).parents[1]/'scripts/preflight.py'),
                           '--mode','reference','--require-version','0.0.0'],capture_output=True,text=True)
    assert result.returncode==2
    report=json.loads(result.stdout)
    assert not report['ok'] and 'Version mismatch' in report['next_action']


def test_fit_points_are_not_a_bezier_conversion(tmp_path):
    doc=ezdxf.new();doc.units=4;doc.layers.get('0').dxf.lineweight=0
    controls=[[0,0,0],[20,30,0],[50,30,0],[70,0,0]]
    e=doc.modelspace().add_spline(controls,degree=3)
    path=tmp_path/'wrong-curve.dxf';doc.saveas(path)
    source=tmp_path/'curve.json';source.write_text(json.dumps(controls))
    inv={'schema_version':1,'source_sha256':sha(source),'page':0,'view':'Original cubic',
        'units':4,'delivery_target':'offline_dxf','objects':[{'id':'curve','kind':'SPLINE',
        'source_locator':'Bezier 1','tolerance':.001,'expected':{'degree':3,'control_points':controls,'knots':[0,0,0,0,1,1,1,1]},
        'presentation':{'linetype':'CONTINUOUS','rgb':[255,255,255],'opacity':1,'lineweight':0}}]}
    assert 'REFERENCE_GEOMETRY:curve' in audit_reference(path,inv,{'curve':e.dxf.handle},source)['errors']


def test_invalid_source_inventory_replaces_old_pass_report(tmp_path):
    import subprocess
    from test_redraw_delivery import fixture
    _,path,source,inv,mapping=fixture(tmp_path)
    inv['objects'][0]['presentation'].pop('lineweight')
    for name,value in [('source.json',inv),('mapping.json',{'reference_map':mapping})]:
        (tmp_path/name).write_text(json.dumps(value))
    report=tmp_path/'report.json';report.write_text('{"complete_redraw_accepted":true}')
    result=subprocess.run([sys.executable,str(Path(__file__).parents[1]/'scripts/verify_redraw.py'),str(path),
        str(tmp_path/'mapping.json'),'--reference-inventory',str(tmp_path/'source.json'),'--source',str(source),
        '--report',str(report)],capture_output=True)
    assert result.returncode==1
    data=json.loads(report.read_text())
    assert not data['complete_redraw_accepted'] and data['verifier_version']
    assert any('INVALID_REFERENCE_INPUT' in error for error in data['errors'])
