"""Real optional STEP/IFC readback, not tests of model recognition or engineering."""
import copy
import json
import math
from pathlib import Path

import pytest

from luomu_cad.cad_engines import build, inspect_ifc, inspect_step
from luomu_cad.delivery import review
from luomu_cad.qa import file_hash

ROOT=Path(__file__).resolve().parents[1]


def write(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    return {'path':path.name,'sha256':file_hash(path)}


def preview(vertices,faces,path):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.figure import Figure
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    figure=Figure(figsize=(5,4));axis=figure.add_subplot(111,projection='3d')
    axis.add_collection3d(Poly3DCollection([[vertices[i] for i in face] for face in faces],facecolors='#96b5ca',edgecolors='#263844',linewidths=.15))
    low=[min(v[i] for v in vertices) for i in range(3)];high=[max(v[i] for v in vertices) for i in range(3)]
    axis.set_xlim(low[0],high[0]);axis.set_ylim(low[1],high[1]);axis.set_zlim(low[2],high[2])
    axis.set_box_aspect([max(high[i]-low[i],1e-6) for i in range(3)])
    axis.view_init(elev=25,azim=-60);figure.savefig(path,dpi=120)


def contract(base,industry,drawing_type,fmt,path,expected):
    check={'id':'native-kernel','kind':'kernel_geometry','artifact_id':'native','source_locator':'Original explicit native-exchange exercise'}
    requirement={'id':'R-NATIVE','description':'Reopen and measure the exact explicitly specified native-exchange geometry',
                 'industry_id':industry,'source_locator':'Original explicit exercise dimensions and relation counts','checks':[check]}
    brief={'schema_version':1,'scope':'reference_redraw','jurisdiction':'CN','industries':[industry],
           'purpose':'Original kernel acceptance fixture; not a customer engineering or recognition result',
           'requirements':[requirement],'required_sheets':[{'sheet_id':'N01','industry_id':industry,
               'drawing_type':drawing_type,'formats':[fmt],'expected':{fmt:expected}}]}
    c={'schema_version':1,'contract_id':'NATIVE-'+fmt.upper(),'scope':'reference_redraw','jurisdiction':'CN','industries':[industry],
       'producer_id':'kernel-fixture-producer','customer_brief':write(base/'customer-brief.json',brief),
       'standard_assignments':[{'industry_id':industry,'standard_id':'mechanical-cad' if industry=='mechanical' else 'architecture-drawing',
           'review_scope':'reference_only','applicability_basis':'Explicit original exchange exercise, no engineering-compliance assertion',
           'evidence':write(base/'basis.json',{'scope':'Original independent kernel fixture; not adopted normative clauses'})}],
       'artifacts':[{'id':'native','path':str(path.relative_to(base)),'sha256':file_hash(path),'format':fmt,
          'industry_id':industry,'drawing_type':drawing_type,'sheet_id':'N01','expected':expected}],
       'requirements':[{**requirement,'artifact_ids':['native']}]}
    observation={'artifact_id':'native','artifact_sha256':file_hash(path),'locator':'Actual exported native model and kernel-generated mesh preview',
                 'source_locator':requirement['source_locator'],'finding':'Fixture native file was reopened and its explicit measurement contract executed',
                 'preview':{'path':'native-preview.png','sha256':file_hash(base/'native-preview.png')}}
    receipt={'schema_version':1,'contract_id':c['contract_id'],'scope':c['scope'],'reviewer_id':'kernel-fixture-review',
             'customer_brief_sha256':c['customer_brief']['sha256'],'artifact_sha256':{'native':file_hash(path)},
             'unresolved':[],'requirement_inventory_checked':True,'inventory_observation':'One explicit native exchange requirement and one matching file',
             'requirements':[{'requirement_id':'R-NATIVE','verdict':'accepted','finding':'Executed original fixture only; not an image or engineering evaluation',
                              'observations':[observation]}]}
    c['independent_review']=write(base/'fixture-review.json',receipt)
    return c


def wrong_target(base,original,expected):
    """Bind a different independent target so native readback, not stale hashes, rejects it."""
    bad=copy.deepcopy(original)
    brief=json.loads((base/bad['customer_brief']['path']).read_text(encoding='utf8'))
    brief['required_sheets'][0]['expected'][bad['artifacts'][0]['format']]=expected
    bad['customer_brief']=write(base/'wrong-target-brief.json',brief)
    bad['artifacts'][0]['expected']=expected
    receipt=json.loads((base/bad['independent_review']['path']).read_text(encoding='utf8'))
    receipt['customer_brief_sha256']=bad['customer_brief']['sha256']
    bad['independent_review']=write(base/'wrong-target-review.json',receipt)
    return bad


def test_actual_step_delivery_measures_geometry_and_rejects_wrong_source_target(tmp_path):
    cq=pytest.importorskip('cadquery')
    report=build('cadquery',ROOT/'examples/cadquery-part.py',tmp_path/'native')
    path=tmp_path/'native/model.step';shape=cq.importers.importStep(str(path)).val()
    vertices,faces=shape.tessellate(.3);preview([list(v.toTuple()) for v in vertices],faces,tmp_path/'native-preview.png')
    volume=80*50*8-math.pi*6**2*8
    expected={'measurements':{'solid_count':[1,1],'volume_mm3':[volume-.001,volume+.001],'bbox_mm':[[79.999,80.001],[49.999,50.001],[7.999,8.001]]}}
    c=contract(tmp_path,'mechanical','mechanical.part','step',path,expected)
    write(tmp_path/'contract.json',c)
    result=review(c,tmp_path);assert result['accepted_for_delivery'],result['findings']
    assert result['artifacts'][0]['actual']['solid_count']==1
    write(tmp_path/'measured-result.json',result)
    wrong=copy.deepcopy(expected);wrong['measurements']['bbox_mm'][0]=[70,71]
    rejected=review(wrong_target(tmp_path,c,wrong),tmp_path)
    assert not rejected['accepted_for_delivery']
    assert any(r['code']=='ARTIFACT_READBACK_FAILED' for r in rejected['findings'])


def test_actual_ifc_delivery_checks_void_fill_and_independent_wall_volume(tmp_path):
    ifc=pytest.importorskip('ifcopenshell')
    import ifcopenshell.geom
    report=build('ifcopenshell',ROOT/'examples/ifc-openings.py',tmp_path/'native')
    path=tmp_path/'native/model.ifc';actual=inspect_ifc(path)
    wall=next(row for row in actual['elements'] if row['name']=='host_wall')
    model=ifc.open(str(path));settings=ifcopenshell.geom.settings();settings.set(settings.USE_WORLD_COORDS,True)
    verts=[];faces=[]
    for product in model.by_type('IfcElement'):
        if not product.Representation:continue
        geometry=ifcopenshell.geom.create_shape(settings,product).geometry
        offset=len(verts);verts.extend([geometry.verts[i:i+3] for i in range(0,len(geometry.verts),3)])
        faces.extend([[offset+v for v in geometry.faces[i:i+3]] for i in range(0,len(geometry.faces),3)])
    preview(verts,faces,tmp_path/'native-preview.png')
    expected={'schema':'IFC4','element_counts':{'IfcWall':1,'IfcDoor':1,'IfcOpeningElement':1},'void_count':[1,1],'fill_count':[1,1],
              'element_volume_m3':{wall['id']:[2.621999,2.622001]}}
    c=contract(tmp_path,'building_architecture','building_architecture.details','ifc',path,expected)
    write(tmp_path/'contract.json',c)
    result=review(c,tmp_path);assert result['accepted_for_delivery'],result['findings']
    write(tmp_path/'measured-result.json',result)
    wrong=copy.deepcopy(expected);wrong['void_count']=[2,2]
    rejected=review(wrong_target(tmp_path,c,wrong),tmp_path)
    assert not rejected['accepted_for_delivery']
    assert any(r['code']=='ARTIFACT_READBACK_FAILED' for r in rejected['findings'])
