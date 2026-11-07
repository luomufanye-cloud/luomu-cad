import copy
import hashlib
import json
from pathlib import Path

import pytest

from luomu_cad.standards import catalogue,route,review_basis,validate_catalogue


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reference_manifest(drawing):
    return {'schema_version':1,'drawing_sha256':sha(drawing),'reviewed_on':'2026-11-07',
        'reviewer':'Original synthetic record test; not a normative or customer acceptance',
        'project':{'jurisdiction':'CN','discipline':'general','stage':'training','delivery_scope':'Original source geometry exercise only'},
        'scope':'reference_only','compliance_claim':False,'unresolved':[],
        'layers':{name:{'status':'not_assessed','reason':'Reference-only exercise; no current engineering compliance claim'}
                  for name in ('drawing','design','construction_acceptance','data_delivery')},
        'standards':[{'standard_id':'cad-general','number':'GB/T 18229-2000','applicability':'adopted',
            'reason':'Identify the general CAD rule as a project lookup basis; no clause pass inferred',
            'read_level':'metadata','checks':[],
            'version_evidence':{'source_kind':'official_catalogue','url':'https://std.samr.gov.cn/gb/search/gbDetailed?id=71F772D78D39D3A7E05397BE0A0AB82A',
                'locator':'Official metadata, current status and effective date','checked_on':'2026-11-07',
                'status':'current','effective_on':'2001-05-01'}}]}


def exercise(tmp_path):
    drawing=tmp_path/'original-exercise.dxf';drawing.write_text('Original synthetic exercise drawing bytes')
    manifest=reference_manifest(drawing)
    library=catalogue()
    row=copy.deepcopy(library['standards'][0])
    row.update(id='exercise-rule',number='EXERCISE-1',title='Original contract exercise rule, not an engineering standard',
               source_url='https://example.org/original-exercise',text_read='selected_clauses')
    library['standards'].append(row)
    manifest.update(scope='drawing_review',compliance_claim=True)
    for name,layer in manifest['layers'].items():
        layer['status']='covered' if name=='drawing' else 'not_applicable'
        layer['reason']='Original record-check exercise, no construction or engineering approval'
    evidence=tmp_path/'measurement.json'
    evidence.write_text(json.dumps({'exercise':'Original mock readback evidence, not a field or engineering inspection'}))
    item=manifest['standards'][0]
    item.update(standard_id='exercise-rule',number='EXERCISE-1',read_level='clauses',
        checks=[{'clause':'original exercise section 1','requirement':'Check the explicitly given exercise condition',
            'result':'pass','evidence':{'path':evidence.name,'sha256':sha(evidence),'drawing_sha256':sha(drawing)}}])
    item['version_evidence']['url']='https://example.org/original-exercise'
    return drawing,manifest,library,evidence


def test_catalogue_routes_preserve_source_levels_and_no_automatic_adoption():
    value=validate_catalogue(catalogue())
    assert len(value['routes'])>=20
    assert any(s['text_read']=='metadata_only' for s in value['standards'])
    assert any(s['status_observed']=='replacement_reported' for s in value['standards'])
    result=route('mechanical')
    assert not result['auto_apply'] and not result['engineering_approval']
    assert {'cad-general','mechanical-cad'}<={s['id'] for s in result['standards']}
    with pytest.raises(ValueError,match='Unknown discipline'):route('invented-industry')


def test_reference_only_can_record_basis_without_claiming_normative_compliance(tmp_path):
    drawing=tmp_path/'reference.dxf';drawing.write_text('Original reference-only exercise')
    result=review_basis(reference_manifest(drawing),drawing,tmp_path)
    assert result['basis_record_accepted'] and result['supported_claim']=='reference_fidelity_only'
    assert not result['standards_compliance_certified'] and not result['engineering_approval']
    assert result['limitations']


def test_complete_bound_clause_record_is_not_engineering_certification(tmp_path):
    drawing,manifest,library,_=exercise(tmp_path)
    result=review_basis(manifest,drawing,tmp_path,library)
    assert result['basis_record_accepted'],result
    assert not result['standards_compliance_certified'] and not result['engineering_approval']


@pytest.mark.parametrize('fault,expected',[
    ('stale_drawing','STANDARDS_STALE_DRAWING'),
    ('metadata_pass','STANDARDS_METADATA_NOT_COMPLIANCE:exercise-rule'),
    ('old_edition','STANDARDS_EDITION_MISMATCH:exercise-rule'),
    ('replaced','STANDARDS_REPLACED:exercise-rule'),
    ('draft','STANDARDS_REPLACED:exercise-rule'),
    ('future_effective','STANDARDS_NOT_EFFECTIVE:exercise-rule'),
    ('future_check','STANDARDS_FUTURE_VERIFICATION:exercise-rule'),
    ('old_check','STANDARDS_VERSION_RECHECK:exercise-rule'),
    ('unverified_status','STANDARDS_STATUS_UNVERIFIED:exercise-rule'),
    ('wrong_country','STANDARDS_JURISDICTION:exercise-rule'),
    ('wrong_discipline','STANDARDS_DISCIPLINE:exercise-rule'),
    ('no_clause_check','STANDARDS_CLAUSE_REVIEW_REQUIRED:exercise-rule'),
    ('unassessed_layer','STANDARDS_LAYER_UNASSESSED:design'),
    ('fabricated_coverage','STANDARDS_LAYER_WITHOUT_BASIS:data_delivery'),
    ('unresolved','STANDARDS_UNRESOLVED'),
    ('textbook_as_version','STANDARDS_OFFICIAL_VERSION_EVIDENCE:exercise-rule'),
    ('tampered_evidence','STANDARDS_CHECK_EVIDENCE:exercise-rule'),
    ('wrong_evidence_drawing','STANDARDS_CHECK_EVIDENCE:exercise-rule'),
    ('failed_clause','STANDARDS_CHECK_FAIL:exercise-rule'),
])
def test_material_standard_delivery_failures_block_acceptance(tmp_path,fault,expected):
    drawing,manifest,library,evidence=exercise(tmp_path)
    item=manifest['standards'][0];version=item['version_evidence']
    if fault=='stale_drawing':drawing.write_text('Changed after review')
    if fault=='metadata_pass':item['read_level']='metadata'
    if fault=='old_edition':item['number']='EXERCISE-0'
    if fault=='replaced':library['standards'][-1]['superseded_by']='cad-general'
    if fault=='draft':library['standards'][-1]['status_observed']='draft'
    if fault=='future_effective':version['effective_on']='2027-01-01'
    if fault=='future_check':version['checked_on']='2027-01-01'
    if fault=='old_check':version['checked_on']='2020-01-01'
    if fault=='unverified_status':version['status']='pending'
    if fault=='wrong_country':manifest['project']['jurisdiction']='US'
    if fault=='wrong_discipline':library['standards'][-1]['disciplines']=['shipbuilding']
    if fault=='no_clause_check':item['checks']=[]
    if fault=='unassessed_layer':manifest['layers']['design']['status']='not_assessed'
    if fault=='fabricated_coverage':manifest['layers']['data_delivery']['status']='covered'
    if fault=='unresolved':manifest['unresolved']=['Unresolved version/source discrepancy']
    if fault=='textbook_as_version':version['source_kind']='textbook'
    if fault=='tampered_evidence':evidence.write_text('Replaced evidence')
    if fault=='wrong_evidence_drawing':item['checks'][0]['evidence']['drawing_sha256']='0'*64
    if fault=='failed_clause':item['checks'][0]['result']='fail'
    result=review_basis(manifest,drawing,tmp_path,library)
    assert not result['basis_record_accepted'] and expected in result['errors'],result


def test_contract_standard_needs_explicit_adoption(tmp_path):
    drawing,manifest,library,_=exercise(tmp_path)
    library['standards'][-1]['jurisdiction']='US_contract'
    assert 'STANDARDS_CONTRACT_ADOPTION:exercise-rule' in review_basis(manifest,drawing,tmp_path,library)['errors']
    manifest['standards'][0]['contract_adoption']='Original exercise contract explicitly adopts EXERCISE-1'
    assert review_basis(manifest,drawing,tmp_path,library)['basis_record_accepted']


def test_historical_standard_only_supports_reference_reproduction(tmp_path):
    drawing,manifest,library,_=exercise(tmp_path)
    manifest['standards'][0]['applicability']='historical_reference'
    assert 'STANDARDS_HISTORICAL_ADOPTION:exercise-rule' in review_basis(manifest,drawing,tmp_path,library)['errors']
    manifest.update(scope='reference_only',compliance_claim=False)
    manifest['layers']['drawing'].update(status='not_assessed',reason='Historical source reproduction only')
    assert review_basis(manifest,drawing,tmp_path,library)['basis_record_accepted']


def test_missing_basis_is_never_a_delivery_pass(tmp_path):
    result=review_basis(None,tmp_path/'not-read.dxf',tmp_path)
    assert result['errors']==['STANDARDS_BASIS_REQUIRED'] and not result['basis_record_accepted']


def test_unfilled_template_is_not_a_pass(tmp_path):
    from luomu_cad.storage import ROOT
    drawing=tmp_path/'exercise.dxf';drawing.write_text('Original exercise')
    value=json.loads((ROOT/'examples/standards-basis-template.json').read_text(encoding='utf-8'))
    with pytest.raises(ValueError,match='project|reviewer'):
        review_basis(value,drawing,tmp_path)


def test_project_catalogue_cli_does_not_need_to_modify_public_library(tmp_path):
    import subprocess
    import sys
    drawing,manifest,library,_=exercise(tmp_path)
    basis=tmp_path/'basis.json';basis.write_text(json.dumps(manifest),encoding='utf-8')
    custom=tmp_path/'catalogue.json';custom.write_text(json.dumps(library),encoding='utf-8')
    report=tmp_path/'report.json'
    script=Path(__file__).resolve().parents[1]/'scripts/verify_standards.py'
    result=subprocess.run([sys.executable,str(script),str(drawing),str(basis),'--catalogue',str(custom),'--report',str(report)],capture_output=True)
    assert result.returncode==0,result.stderr
    assert json.loads(report.read_text())['basis_record_accepted']
