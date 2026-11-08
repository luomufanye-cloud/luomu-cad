"""Industry routes and hostile cross-industry standard/claim scenarios."""
import copy

import pytest

from luomu_cad import industry


BASE = {'space', 'interior', 'commercial', 'exterior', 'landscape', 'building_architecture',
        'structure', 'water_supply', 'building_electrical', 'electronics', 'garment', 'product', 'mechanical'}


def assignment(industry_id='interior', standard_id='interior-drawing', **extra):
    return {'industry_id': industry_id, 'standard_id': standard_id, **extra}


def test_preserved_industries_and_explicit_industry_qualified_drawing_contracts():
    data=industry.catalogue()
    assert BASE <= {r['id'] for r in data['industries']}
    assert len(data['industries']) >= 25
    standard_map={r['id']:r for r in data['standards']}
    for row in data['industries']:
        assert row['scope_limit'] and row['professional_checks']
        assert row['automatic_lineweight_defaults'] is False
        assert row['automatic_dimension_defaults'] is False
        for drawing in row['drawing_types']:
            assert drawing['id'].startswith(row['id']+'.')
            assert 'native_geometry' in drawing['required_checks']
            assert 'source_coverage' in drawing['required_checks']
        for standard_id in row['standard_ids']:
            assert row['id'] in standard_map[standard_id]['industry_ids']
    assert not data['engineering_approval'] and not data['auto_apply']


@pytest.mark.parametrize('industry_id', [r['id'] for r in industry.catalogue()['industries']])
def test_every_registered_industry_routes_its_actual_drawing_contract(industry_id):
    row=industry.get_profile(industry_id)
    drawing=row['drawing_types'][0]
    result=industry.route([industry_id],[drawing['id']],'CN')
    assert result['drawing_types'][0]['id']==drawing['id']
    assert not result['cross_industry_defaults_inherited']
    for standard in result['standards']:
        assert industry_id in standard['industry_ids']
        assert standard['project_clause_review_required']
    record=assignment(industry_id,row['standard_ids'][0])
    checked=industry.validate_assignments([industry_id],[record])
    assert checked['ok'],checked
    assert not checked['standards_compliance_certified']


def test_all_19_interior_drawing_types_are_distinct_and_retained():
    rows=industry.get_profile('interior')['drawing_types']
    assert len(rows)==19
    assert len({r['id'] for r in rows})==19
    expected={'interior.'+key for key in ['original_frame','layout','furniture_dimensions','floor_finish','ceiling',
        'lighting','ceiling_dimensions','switching','sockets','plumbing','elevation_index','living_dining_elevation',
        'master_bedroom_elevation','guzheng_elevation','secondary_bedroom_elevation','study_elevation',
        'kitchen_elevation','master_bathroom_elevation','public_bathroom_elevation']}
    assert {r['id'] for r in rows}==expected


def test_unknown_industry_and_cross_industry_drawing_have_no_generic_fallback():
    with pytest.raises(ValueError,match='Unknown industry'):
        industry.get_profile('invented_specialty')
    with pytest.raises(ValueError,match='Unknown industry'):
        industry.route(['invented_specialty'])
    with pytest.raises(ValueError,match='unselected or unknown'):
        industry.route(['interior'],['mechanical.part'])
    with pytest.raises(ValueError):
        industry.route(['interior'],['layout'])
    result=industry.validate_assignments(['invented_specialty'],[assignment('invented_specialty','interior-drawing')])
    assert not result['ok']


@pytest.mark.parametrize('record', [
    assignment('interior','mechanical-dimensions'),
    assignment('garment','building-general'),
    assignment('electronics','water-drawing'),
    assignment('shipbuilding','interior-drawing'),
    assignment('footwear','garment-cad'),
    assignment('furniture','building-general'),
])
def test_specialist_standards_cannot_be_reassigned_to_other_industries(record):
    result=industry.validate_assignments([record['industry_id']],[record])
    assert not result['ok']
    assert any(r['kind']=='cross_industry_standard' for r in result['findings'])


def test_composite_project_keeps_each_profession_isolated_and_requires_all_assignments():
    selected=['interior','building_electrical']
    correct=[assignment(),assignment('building_electrical','electrical-cad')]
    assert industry.validate_assignments(selected,correct)['ok']
    assert not industry.validate_assignments(selected,[assignment()])['ok']
    wrong=[assignment('interior','electrical-cad'),assignment('building_electrical','electrical-cad')]
    result=industry.validate_assignments(selected,wrong)
    assert not result['ok']
    assert any(r['kind']=='cross_industry_standard' for r in result['findings'])
    shared=[assignment('interior','building-general'),assignment('building_electrical','building-general')]
    assert industry.validate_assignments(selected,shared)['ok']


@pytest.mark.parametrize('records', [None, [], [None], [{}], [assignment(),assignment()],
    [assignment('interior','does_not_exist')], [assignment(number='JGJ/T 244-1999')],
    [assignment(source_url='https://example.invalid/fake-standard')]])
def test_missing_duplicate_or_edited_standard_identity_is_not_accepted(records):
    assert not industry.validate_assignments(['interior'],records)['ok']


@pytest.mark.parametrize('extra', [{'claims_compliance':True}, {'clauses':['5.4']},
    {'clauses':['5.4'],'clause_evidence':{'level':'official_metadata'}},
    {'clauses':['5.4'],'clause_evidence':{'level':'project_clause_review','source_locator':'page 1',
      'source_sha256':'not-a-hash','review_sha256':'a'*64}}])
def test_catalogue_metadata_does_not_substantiate_project_clause_claims(extra):
    result=industry.validate_assignments(['interior'],[assignment(**extra)])
    assert not result['ok']
    assert any(r['kind']=='unevidenced_clause_claim' for r in result['findings'])


def test_well_formed_clause_evidence_is_still_not_a_compliance_certificate():
    result=industry.validate_assignments(['interior'],[assignment(clauses=['project-adopted clause'],
        clause_evidence={'level':'project_clause_review','source_locator':'licensed source p.12',
                         'source_sha256':'a'*64,'review_sha256':'b'*64})])
    assert result['ok']
    assert not result['standards_compliance_certified']
    result=industry.validate_assignments(['interior'],[assignment(engineering_approved=True)])
    assert not result['ok']


def test_local_and_contract_standards_are_discovered_without_automatic_adoption():
    cn=industry.route(['landscape'],jurisdiction='CN')
    beijing=industry.route(['landscape'],jurisdiction='CN-BJ')
    assert 'beijing-landscape-depth' not in {r['id'] for r in cn['standards']}
    assert 'beijing-landscape-depth' in {r['id'] for r in beijing['standards']}
    mechanics=industry.route(['mechanical'])
    assert not mechanics['auto_apply']
    assert all(not r['automatic_application'] for r in mechanics['standards'])
    local=assignment('landscape','beijing-landscape-depth')
    wrong=industry.validate_assignments(['landscape'],[local],jurisdiction='CN-Hunan')
    assert not wrong['ok']
    assert any(r['kind']=='cross_jurisdiction_standard' for r in wrong['findings'])
    assert industry.validate_assignments(['landscape'],[local],jurisdiction='CN-BJ')['ok']


def test_corrupt_permission_cannot_silently_expand_a_profile(monkeypatch):
    original=industry._resource
    data=original('industry-delivery.json')
    data['industries'][0]['standard_ids'].append('mechanical-dimensions')
    def resource(name):
        return copy.deepcopy(data) if name=='industry-delivery.json' else original(name)
    monkeypatch.setattr(industry,'_resource',resource)
    with pytest.raises(ValueError,match='outside its explicit allowlist'):
        industry.catalogue()


def test_current_replacement_entries_preserve_their_real_evidence_limits():
    data=industry.catalogue();standards={r['id']:r for r in data['standards']}
    assert standards['municipal-delivery-depth']['number']=='建质〔2025〕38号'
    assert standards['municipal-delivery-depth']['effective_on']=='2025-10-01'
    assert standards['water-resources-1']['number']=='SL/T 73.1-2026'
    assert standards['ship-arrangement']['text_read']=='metadata_only'
    assert standards['furniture-drawing']['number']=='QB/T 1338-2012'


def test_dimensioning_systems_must_be_split_instead_of_silently_mixed():
    cn=[assignment('mechanical','mechanical-dimensions'),assignment('mechanical','gps-tolerances')]
    assert industry.validate_assignments(['mechanical'],cn)['ok']
    asme=[assignment('mechanical','asme-dimensioning')]
    assert industry.validate_assignments(['mechanical'],asme)['ok']
    mixed=industry.validate_assignments(['mechanical'],cn+asme)
    assert not mixed['ok']
    assert any(row['kind']=='standard_system_conflict' for row in mixed['findings'])
