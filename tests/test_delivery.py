"""Actual DXF/PDF customer-contract gates; fixtures are not recognition benchmarks."""
import copy
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys

import ezdxf
import pytest
from pypdf import PdfReader, PdfWriter

from luomu_cad.delivery import review, template
from luomu_cad.pdf_export import render_pdf
from luomu_cad.qa import file_hash
from luomu_cad.storage import ROOT


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    return {'path':path.name,'sha256':file_hash(path)}


def exercise(base,scope='reference_redraw'):
    """Original independent brief: a 1000x600 rectangle and its native width."""
    base.mkdir(parents=True,exist_ok=True)
    doc=ezdxf.new('R2018',setup=True);doc.units=4
    doc.layers.get('0').dxf.lineweight=13
    doc.layers.new('OUTLINE',dxfattribs={'lineweight':25})
    line=doc.modelspace().add_lwpolyline([(0,0),(1000,0),(1000,600),(0,600)],close=True,dxfattribs={'layer':'OUTLINE'})
    dim=doc.modelspace().add_linear_dim(base=(0,-100),p1=(0,0),p2=(1000,0),
        override={'dimtxt':25,'dimasz':20,'dimlfac':1,'dimdec':2,'dimzin':8,'dimlwd':13,'dimlwe':13})
    dim.render()
    drawing=base/'P01.dxf';doc.saveas(drawing)
    paper=base/'P01.pdf'
    pdf,_=render_pdf(drawing,[297,210],[-300,-300,1600,900],10)
    paper.write_bytes(pdf)
    import pypdfium2 as pdfium
    rendered=pdfium.PdfDocument(paper);page=rendered[0];bitmap=page.render(scale=.8)
    preview=base/'P01.png';bitmap.to_pil().save(preview)
    bitmap.close();page.close();rendered.close()
    geometry_checks=[{'id':'outline','kind':'dxf_measure','artifact_id':'native','source_locator':'Original customer brief rectangle coordinates',
        'measurement':{'kind':'contour','handles':[line.dxf.handle],
            'expected_points':[[0,0],[1000,0],[1000,600],[0,600],[0,0]],'tolerance':.001}},
       {'id':'width','kind':'dxf_measure','artifact_id':'native','source_locator':'Original customer brief width1000',
        'measurement':{'kind':'dimension','handles':[dim.dimension.dxf.handle],'range':[999.999,1000.001]}},
       {'id':'style','kind':'dxf_style','artifact_id':'native','source_locator':'Original customer brief layer widths',
        'style':{'basis':'Original test brief .25 outline and .13 dimension', 'layers':{
            'OUTLINE':{'lineweight_mm':[.25,.25],'linetypes':['CONTINUOUS'],'polyline_width':[0,0]},
            '0':{'lineweight_mm':[.13,.13],'linetypes':['CONTINUOUS'],'polyline_width':[0,0]}}}}]
    requirements=[{'id':'R-GEOMETRY','description':'Original rectangle1000x600 with measured native width1000 and agreed layer presentation',
        'industry_id':'interior','source_locator':'Customer brief geometry and native dimension specification',
        'checks':geometry_checks},
       {'id':'R-PAPER','description':'Deliver one nonblank A4 landscape PDF with agreed paper lineweights',
        'industry_id':'interior','source_locator':'Customer brief delivery-format paragraph',
        'checks':[{'id':'paper','kind':'pdf_delivery','artifact_id':'paper','source_locator':'Customer brief A4 landscape requirement'},
                  {'id':'paper_matches_native','kind':'pdf_dxf_correspondence','artifact_id':'paper','source_artifact_id':'native',
                   'window_mm':[-300,-300,1600,900],'scale':10,'margin_mm':10,'source_locator':'Customer brief same-sheet export at 1:10'}]}]
    sheet={'sheet_id':'P01','industry_id':'interior','drawing_type':'interior.layout','formats':['dxf','pdf'],
        'expected':{'dxf':{'units':4},'pdf':{'page_count':1,'paper_mm':[297,210],'lineweights_mm':[.13,.25]}}}
    brief={'schema_version':1,'scope':scope,'jurisdiction':'CN','industries':['interior'],
        'purpose':'Original narrow drawing exercise; no engineering or recognition accuracy claim',
        'requirements':copy.deepcopy(requirements),'required_sheets':[sheet]}
    contract={'schema_version':1,'contract_id':'ORIGINAL-BRIEF-001','scope':scope,'jurisdiction':'CN',
        'industries':['interior'],'producer_id':'producer-fixture',
        'customer_brief':save(base/'customer-brief.json',brief),
        'standard_assignments':[{'industry_id':'interior','standard_id':'interior-drawing',
            'review_scope':'reference_only','applicability_basis':'Explicit source-only rectangle reproduction, not a construction compliance claim',
            'evidence':save(base/'standards-review.json',{'scope':'Source-only reference reproduction; not adopted engineering clauses','basis':'Original exercise'})}],
        'artifacts':[
          {'id':'native','path':drawing.name,'sha256':file_hash(drawing),'format':'dxf',
           'industry_id':'interior','drawing_type':'interior.layout','sheet_id':'P01','expected':sheet['expected']['dxf']},
          {'id':'paper','path':paper.name,'sha256':file_hash(paper),'format':'pdf',
           'industry_id':'interior','drawing_type':'interior.layout','sheet_id':'P01','expected':sheet['expected']['pdf']}],
        'requirements':[{**r,'artifact_ids':['native'] if r['id']=='R-GEOMETRY' else ['paper','native']} for r in requirements]}
    independent={'schema_version':1,'contract_id':contract['contract_id'],'scope':scope,
        'reviewer_id':'independent-fixture-review','customer_brief_sha256':contract['customer_brief']['sha256'],
        'artifact_sha256':{a['id']:a['sha256'] for a in contract['artifacts']},'unresolved':[],
        'requirement_inventory_checked':True,'inventory_observation':'Both original brief requirements and its DXF/PDF sheet inventory are present',
        'requirements':[]}
    for r in contract['requirements']:
        independent['requirements'].append({'requirement_id':r['id'],'verdict':'accepted',
            'finding':'Original fixed fixture agrees with independently specified dimensions and requested paper output',
            'observations':[{'artifact_id':aid,'artifact_sha256':next(a['sha256'] for a in contract['artifacts'] if a['id']==aid),
                'locator':'P01 geometry/native-width and PDF page1, as applicable',
                'source_locator':r['source_locator'],'finding':'Checked the fixture against the fixed original brief, not a model recognition test',
                'preview':{'path':preview.name,'sha256':file_hash(preview)}} for aid in r['artifact_ids']]})
    contract['independent_review']=save(base/'independent-review.json',independent)
    return contract


def update_receipt(base,contract):
    path=base/contract['independent_review']['path'];receipt=json.loads(path.read_text(encoding='utf8'))
    receipt['artifact_sha256']={a['id']:a['sha256'] for a in contract['artifacts']}
    for row in receipt.get('requirements',[]):
        for observation in row.get('observations',[]):
            observation['artifact_sha256']=receipt['artifact_sha256'][observation['artifact_id']]
    contract['independent_review']=save(path,receipt)


def test_real_dxf_pdf_closed_customer_contract(tmp_path):
    contract=exercise(tmp_path)
    result=review(contract,tmp_path)
    assert result['accepted_for_delivery'],result['findings']
    assert all(row['passed'] for row in result['per_requirement'])
    assert result['artifacts'][0]['actual']['dimension_readback'][0]['measured']==1000
    assert result['artifacts'][1]['actual']['pages'][0]['rendered_ink_pixels']>25
    assert not result['engineering_approval'] and not result['recognition_accuracy_proven']
    assert not result['reviewer_identity_authenticated']


@pytest.mark.parametrize('fault',['omitted_requirement','weakened_target','wrong_industry','wrong_standard','missing_pdf',
    'stale_file','same_reviewer','fake_pass','stale_receipt','weakened_paper','out_of_scope_path','extra_sheet',
    'missing_preview','unresolved','scope_change','jurisdiction_change'])
def test_contract_cannot_hide_missing_or_stale_work(tmp_path,fault):
    contract=exercise(tmp_path)
    receipt_path=tmp_path/'independent-review.json';receipt=json.loads(receipt_path.read_text(encoding='utf8'))
    if fault=='omitted_requirement':contract['requirements'].pop()
    elif fault=='weakened_target':contract['requirements'][0]['checks'][1]['measurement']['range']=[0,999999]
    elif fault=='wrong_industry':contract['artifacts'][0]['industry_id']='mechanical'
    elif fault=='wrong_standard':contract['standard_assignments'][0]['standard_id']='mechanical-cad'
    elif fault=='missing_pdf':contract['artifacts'].pop()
    elif fault=='stale_file':(tmp_path/'P01.dxf').write_bytes(b'changed')
    elif fault=='same_reviewer':receipt['reviewer_id']=contract['producer_id']
    elif fault=='fake_pass':receipt={'status':'pass','ok':True}
    elif fault=='stale_receipt':receipt['artifact_sha256']['native']='f'*64
    elif fault=='weakened_paper':contract['artifacts'][1]['expected']['paper_mm']=[100,100]
    elif fault=='out_of_scope_path':contract['artifacts'][0]['path']='../escape.dxf'
    elif fault=='extra_sheet':contract['artifacts'][0]['sheet_id']='P99'
    elif fault=='missing_preview':receipt['requirements'][0]['observations'][0].pop('preview')
    elif fault=='unresolved':receipt['unresolved']=['Missing customer title']
    elif fault=='scope_change':contract['scope']='drawing_delivery'
    else:contract['jurisdiction']='CN-Beijing'
    contract['independent_review']=save(receipt_path,receipt)
    result=review(contract,tmp_path)
    assert not result['accepted_for_delivery'],fault
    assert result['findings']


@pytest.mark.parametrize('fault',['geometry','dimension_override','dimension_display','blank_pdf','wrong_paper','fake_dxf','fake_pdf'])
def test_actual_files_reopened_even_when_report_hashes_are_updated(tmp_path,fault):
    contract=exercise(tmp_path)
    if fault in {'geometry','dimension_override','dimension_display'}:
        path=tmp_path/'P01.dxf';doc=ezdxf.readfile(path)
        if fault=='geometry':next(iter(doc.modelspace().query('LWPOLYLINE'))).set_points([(0,0),(900,0),(900,600),(0,600)])
        else:
            dim=next(iter(doc.modelspace().query('DIMENSION')))
            if fault=='dimension_override':dim.dxf.text='1000'
            else:next(e for e in doc.blocks[dim.dxf.geometry] if e.dxftype() in {'TEXT','MTEXT'}).dxf.text='900'
        doc.saveas(path);contract['artifacts'][0]['sha256']=file_hash(path)
    else:
        if fault=='fake_dxf':
            path=tmp_path/'P01.dxf';path.write_text('This is not DXF',encoding='utf8');index=0
        elif fault=='fake_pdf':
            path=tmp_path/'P01.pdf';path.write_bytes(b'%PDF-FAKE');index=1
        else:
            path=tmp_path/'P01.pdf';writer=PdfWriter();writer.add_blank_page(width=(297 if fault=='blank_pdf' else 210)*72/25.4,height=210*72/25.4)
            with path.open('wb') as stream:writer.write(stream)
            index=1
        contract['artifacts'][index]['sha256']=file_hash(path)
    update_receipt(tmp_path,contract)
    result=review(contract,tmp_path)
    assert not result['accepted_for_delivery'],fault
    assert result['findings']


def test_template_is_not_a_completed_delivery(tmp_path):
    value=template(['interior'])
    assert not value['accepted_for_delivery']
    result=review(value,tmp_path)
    assert not result['accepted_for_delivery']


def test_nonblank_correct_paper_pdf_of_a_different_drawing_is_rejected(tmp_path):
    contract=exercise(tmp_path)
    wrong=ezdxf.readfile(tmp_path/'P01.dxf')
    next(iter(wrong.modelspace().query('LWPOLYLINE'))).set_points([(0,0),(1300,0),(1300,600),(0,600)])
    other=tmp_path/'other.dxf';wrong.saveas(other)
    data,_=render_pdf(other,[297,210],[-300,-300,1600,900],10)
    (tmp_path/'P01.pdf').write_bytes(data)
    contract['artifacts'][1]['sha256']=file_hash(tmp_path/'P01.pdf')
    update_receipt(tmp_path,contract)
    result=review(contract,tmp_path)
    assert not result['accepted_for_delivery']
    paper=next(row for row in result['per_requirement'] if row['id']=='R-PAPER')
    comparison=next(row for row in paper['checks'] if row['id']=='paper_matches_native')
    assert not comparison['passed'] and comparison['actual']['changed_pixels']>10


def test_unused_pdf_width_declarations_do_not_prove_painted_lineweights(tmp_path):
    import re
    from pypdf.generic import DecodedStreamObject,NameObject
    contract=exercise(tmp_path)
    path=tmp_path/'P01.pdf';reader=PdfReader(path);page=reader.pages[0]
    data=re.sub(rb'[-+0-9.eE]+\s+w\b',b'0.1 w',page.get_contents().get_data())
    data+=b'\n'+str(.13*72/25.4).encode()+b' w\n'+str(.25*72/25.4).encode()+b' w\n'
    stream=DecodedStreamObject();stream.set_data(data);page[NameObject('/Contents')]=stream
    writer=PdfWriter();writer.add_page(page)
    with path.open('wb') as output:writer.write(output)
    contract['artifacts'][1]['sha256']=file_hash(path);update_receipt(tmp_path,contract)
    result=review(contract,tmp_path)
    assert not result['accepted_for_delivery']
    assert any('physical lineweight absent' in row.get('error','') for row in result['findings'])


@pytest.mark.parametrize('mutation',['stale_display','nonuniform','scaled_dimension','cycle','xref'])
def test_reachable_insert_dimensions_and_unsupported_transforms_fail_closed(tmp_path,mutation):
    contract=exercise(tmp_path);path=tmp_path/'P01.dxf';doc=ezdxf.readfile(path)
    block=doc.blocks.new('SECONDARY_NATIVE_DIMENSION')
    dimension=block.add_linear_dim(base=(0,100),p1=(0,0),p2=(600,0),
        override={'dimtxt':25,'dimasz':20,'dimlfac':1,'dimdec':2,'dimzin':8,'dimlwd':13,'dimlwe':13})
    dimension.render()
    if mutation=='stale_display':
        next(e for e in doc.blocks[dimension.dimension.dxf.geometry] if e.dxftype() in {'TEXT','MTEXT'}).dxf.text='999'
    if mutation=='cycle':block.add_blockref(block.name,(0,0))
    if mutation=='xref':block.block.dxf.flags=4
    attributes={'xscale':2,'yscale':1} if mutation=='nonuniform' else {'xscale':2,'yscale':2,'zscale':2} if mutation=='scaled_dimension' else {}
    doc.modelspace().add_blockref(block.name,(0,400),dxfattribs=attributes)
    doc.saveas(path);contract['artifacts'][0]['sha256']=file_hash(path)
    # The native readback must independently reject this; unchanged PDF cannot hide it.
    update_receipt(tmp_path,contract)
    result=review(contract,tmp_path)
    assert not result['accepted_for_delivery']
    native=next(row for row in result['artifacts'] if row['id']=='native')
    assert not native['passed'],result


def test_every_declared_industry_needs_customer_requirements_and_sheets(tmp_path):
    contract=exercise(tmp_path);path=tmp_path/'customer-brief.json';brief=json.loads(path.read_text(encoding='utf8'))
    brief['industries'].append('mechanical');contract['industries']=brief['industries']
    contract['customer_brief']=save(path,brief)
    result=review(contract,tmp_path)
    assert not result['accepted_for_delivery']
    assert any('Every declared industry' in row.get('error','') for row in result['findings'])


def test_unknown_artifact_expectations_cannot_be_silently_ignored(tmp_path):
    contract=exercise(tmp_path);path=tmp_path/'customer-brief.json';brief=json.loads(path.read_text(encoding='utf8'))
    brief['required_sheets'][0]['expected']['pdf']['unimplemented_requirement']='must be verified'
    contract['customer_brief']=save(path,brief)
    contract['artifacts'][1]['expected']=brief['required_sheets'][0]['expected']['pdf']
    result=review(contract,tmp_path)
    assert not result['accepted_for_delivery']
    assert any('Unsupported artifact expectations' in row.get('error','') for row in result['findings'])


def test_painted_pdf_widths_use_q_restore_and_ctm_at_stroking_time():
    from pypdf.generic import DecodedStreamObject,NameObject
    from luomu_cad.delivery import _painted_widths
    writer=PdfWriter();page=writer.add_blank_page(width=100,height=100)
    stream=DecodedStreamObject();stream.set_data(b'.25 w q 2 0 0 2 0 0 cm 0 0 m 10 10 l S Q 0 20 m 10 20 l S .13 w')
    page[NameObject('/Contents')]=stream
    data=BytesIO();writer.write(data);reader=PdfReader(data)
    widths=_painted_widths(reader.pages[0],reader,1)
    assert widths==pytest.approx([.5*25.4/72,.25*25.4/72])
    assert not any(abs(value-.13*25.4/72)<1e-9 for value in widths)


def native_dimension_fixture(base,kind,decimal_separator=46):
    doc=ezdxf.new('R2018',setup=True);doc.units=4;layout=doc.modelspace()
    options={'dimlfac':1,'dimdec':2,'dimadec':2,'dimzin':8,'dimazin':2,
        'dimdsep':decimal_separator,'dimtxt':2.5,'dimasz':2,'dimlwd':13,'dimlwe':13}
    if kind=='linear':
        dimension=layout.add_linear_dim(base=(0,20),p1=(0,0),p2=(100,0),override=options);value=100
    elif kind=='aligned':
        dimension=layout.add_aligned_dim(p1=(0,0),p2=(60,80),distance=10,override=options);value=100
        # Exercise a native type1 as well as ezdxf's type0 rotated factory representation.
        dimension.dimension.dxf.dimtype=(dimension.dimension.dxf.dimtype&~7)|1
    elif kind=='radius':
        dimension=layout.add_radius_dim(center=(0,0),radius=50.25,angle=45,override=options);value=50.25
    elif kind=='diameter':
        dimension=layout.add_diameter_dim(center=(0,0),radius=50.25,angle=45,override=options);value=100.5
    elif kind=='angular_3p':
        dimension=layout.add_angular_dim_3p(base=(30,20),center=(0,0),p1=(100,0),p2=(50,86.6025403784),override=options);value=60
    else:
        dimension=layout.add_angular_dim_2l(base=(30,20),line1=((0,0),(100,0)),line2=((0,0),(50,86.6025403784)),override=options);value=60
    dimension.render();path=base/(kind+'.dxf');doc.saveas(path)
    return path,dimension.dimension.dxf.handle,value


@pytest.mark.parametrize('kind',['linear','aligned','radius','diameter','angular_3p'])
def test_supported_automatic_native_mechanical_dimensions_reopen_and_measure(tmp_path,kind):
    from luomu_cad.delivery import _dxf
    path,handle,value=native_dimension_fixture(tmp_path,kind)
    actual,_=_dxf(path,{'units':4})
    row=next(d for d in actual['dimension_readback'] if d['handle']==handle)
    assert row['measured']==pytest.approx(value)
    assert row['display']==pytest.approx([value])
    assert row['unit']==('degrees' if kind.startswith('angular') else 'drawing_units')
    if kind=='radius':assert row['display_text'].startswith('R')
    if kind=='diameter':assert row['display_text'].startswith('Ø')
    if kind=='angular_3p':assert row['display_text'].endswith('°')


@pytest.mark.parametrize('kind',['linear','aligned','radius','diameter','angular_3p'])
def test_supported_native_display_values_cannot_be_replaced_by_wrong_numbers(tmp_path,kind):
    import re
    from luomu_cad.delivery import _dxf
    path,handle,_=native_dimension_fixture(tmp_path,kind)
    doc=ezdxf.readfile(path);dimension=doc.entitydb[handle]
    display=next(e for e in doc.blocks[dimension.dxf.geometry] if e.dxftype() in {'TEXT','MTEXT'})
    display.dxf.text=re.sub(r'\d+(?:\.\d+)?','999',display.dxf.text,count=1)
    doc.saveas(path)
    with pytest.raises(ValueError,match='display does not match'):_dxf(path,{'units':4})


@pytest.mark.parametrize('style',['mtext_controls','diameter_unicode','degree_percent','decimal_comma'])
def test_verified_control_decoding_keeps_native_dimension_symbols(tmp_path,style):
    from luomu_cad.delivery import _dxf
    kind='angular_3p' if style=='degree_percent' else 'diameter' if style=='diameter_unicode' else 'radius'
    path,handle,value=native_dimension_fixture(tmp_path,kind,44 if style=='decimal_comma' else 46)
    doc=ezdxf.readfile(path);dimension=doc.entitydb[handle]
    display=next(e for e in doc.blocks[dimension.dxf.geometry] if e.dxftype() in {'TEXT','MTEXT'})
    if style=='mtext_controls':display.dxf.text='{\\C1;\\H1.0x;'+display.dxf.text+'}'
    elif style=='diameter_unicode':display.dxf.text=display.dxf.text.replace('%%c','⌀')
    elif style=='degree_percent':display.dxf.text=display.dxf.text.replace('°','%%d')
    doc.saveas(path)
    actual,_=_dxf(path,{'units':4})
    assert actual['dimension_readback'][0]['display']==pytest.approx([value])


@pytest.mark.parametrize('kind,replacement',[('radius','⌀50.25'),('diameter','R100.5'),('angular_3p','60')])
def test_dimension_symbol_must_agree_with_native_dimension_type(tmp_path,kind,replacement):
    from luomu_cad.delivery import _dxf
    path,handle,_=native_dimension_fixture(tmp_path,kind)
    doc=ezdxf.readfile(path);dimension=doc.entitydb[handle]
    next(e for e in doc.blocks[dimension.dxf.geometry] if e.dxftype() in {'TEXT','MTEXT'}).dxf.text=replacement
    doc.saveas(path)
    with pytest.raises(ValueError,match='symbol/unit/display format'):_dxf(path,{'units':4})


def test_installed_two_line_angular_renderer_disagreement_is_not_silently_repaired(tmp_path):
    from luomu_cad.delivery import _dxf
    path,handle,_=native_dimension_fixture(tmp_path,'angular_2l')
    doc=ezdxf.readfile(path);dimension=doc.entitydb[handle]
    value=float(dimension.get_measurement())
    display=next(e.plain_text() for e in doc.blocks[dimension.dxf.geometry] if e.dxftype() in {'TEXT','MTEXT'})
    # ezdxf1.4.5 renders the complementary sweep for this actual two-line case.
    assert value==pytest.approx(60) and display=='300°'
    with pytest.raises(ValueError,match='display does not match'):_dxf(path,{'units':4})


def test_ifc_measured_expectations_are_consumed():
    from luomu_cad.delivery import _ifc_expectations
    actual={'schema':'IFC4','elements':[{'id':'wall-id','class':'IfcWall','net_volume_m3':2.4}],
        'voids':[{'host':'wall-id','opening':'opening-id'}],'fills':[]}
    expected={'schema':'IFC4','element_counts':{'IfcWall':1},'void_count':[1,1],'fill_count':[0,0],
        'element_volume_m3':{'wall-id':[2.39,2.41]}}
    _ifc_expectations(actual,expected)
    for change in [{'schema':'IFC2X3'},{'element_counts':{'IfcWall':2}},{'void_count':[0,0]},
        {'fill_count':[1,1]},{'element_volume_m3':{'wall-id':[1,2]}}]:
        with pytest.raises(ValueError):_ifc_expectations(actual,{**expected,**change})


def test_cli_actual_contract_and_failed_exit(tmp_path):
    contract=exercise(tmp_path);path=tmp_path/'contract.json';save(path,contract)
    args=[sys.executable,str(ROOT/'scripts/verify_delivery.py'),'review','--contract',str(path),'--base',str(tmp_path)]
    result=subprocess.run(args,capture_output=True,text=True,encoding='utf8')
    assert result.returncode==0,result.stderr+result.stdout
    contract['requirements'].pop();save(path,contract)
    result=subprocess.run(args,capture_output=True,text=True,encoding='utf8')
    assert result.returncode==1


def test_engineering_delivery_does_not_fake_authority(tmp_path):
    contract=exercise(tmp_path,scope='engineering_delivery')
    assignment=contract['standard_assignments'][0]
    assignment.update(review_scope='reviewed_clauses',clauses=['Original explicit test clause'],
        clause_reviews=[{'locator':'Original explicit test clause','interpretation':'Fixture-only evidence of dimensions, not actual standard text or legal approval',
            'requirement_ids':['R-GEOMETRY','R-PAPER'],'check_ids':['outline','width','style','paper','paper_matches_native']}])
    from luomu_cad.industry import catalogue
    library=catalogue();standard=next(s for s in library['standards'] if s['id']=='interior-drawing')
    assignment['version_evidence']={'number':standard['number'],'source_url':standard['source_url'],
        'status':'current','checked_on':library['checked_on']}
    assignment['source_evidence']=save(tmp_path/'clause-source.json',{'scope':'Original fixture, not normative copied text'})
    assignment['clause_evidence']={'level':'project_clause_review','source_locator':'Original fixture paragraph',
        'source_sha256':assignment['source_evidence']['sha256'],'review_sha256':assignment['evidence']['sha256']}
    result=review(contract,tmp_path)
    assert not result['accepted_for_delivery'] and not result['engineering_approval']
    assert any(row['code']=='PROFESSIONAL_ENGINEERING_AUTHORITY_REQUIRED' for row in result['findings']),result


@pytest.mark.parametrize('fmt',['dwg','step','ifc'])
def test_opaque_logs_and_missing_native_parsers_never_accept_files(tmp_path,fmt):
    contract=exercise(tmp_path)
    brief_path=tmp_path/'customer-brief.json';brief=json.loads(brief_path.read_text(encoding='utf8'))
    # Original fixture is now an explicitly different requested file format.
    # A fabricated producer receipt must never be treated as native reopening.
    expected={'measurements':{'solid_count':[1,1]}} if fmt=='step' else {}
    brief['required_sheets'][0]['formats']=[fmt,'pdf']
    brief['required_sheets'][0]['expected']={fmt:expected,'pdf':brief['required_sheets'][0]['expected']['pdf']}
    contract['customer_brief']=save(brief_path,brief)
    file=tmp_path/('P01.'+fmt);file.write_bytes((b'AC1032' if fmt=='dwg' else b'FAKE EXCHANGE FILE')+b' '*1000)
    contract['artifacts'][0].update(path=file.name,sha256=file_hash(file),format=fmt,expected=expected)
    receipt_path=tmp_path/'independent-review.json';receipt=json.loads(receipt_path.read_text(encoding='utf8'))
    receipt['customer_brief_sha256']=contract['customer_brief']['sha256']
    contract['independent_review']=save(receipt_path,receipt)
    update_receipt(tmp_path,contract)
    result=review(contract,tmp_path)
    assert not result['accepted_for_delivery']
    assert any(row['code']=='ARTIFACT_READBACK_FAILED' for row in result['findings'])
    if fmt=='dwg':
        assert any('DWG_LIVE_MCP_REVALIDATION_REQUIRED' in row.get('error','') for row in result['findings'])
