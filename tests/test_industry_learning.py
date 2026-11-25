"""Industry learning notes stay linked to source-checked catalogue records."""
import re
from pathlib import Path

import pytest

from luomu_cad.standards import catalogue, route

ROOT = Path(__file__).resolve().parents[1]
NOTE_ROUTES = {'mechanical', 'product', 'interior', 'environment_design', 'landscape', 'food_processing'}
STANDARD_ID = re.compile(r'`([a-z0-9]+(?:-[a-z0-9]+)+)`')


def _routes():
    return {r['id']: r for r in catalogue()['routes']}


def test_learning_routes_point_to_existing_notes():
    routes = _routes()
    assert NOTE_ROUTES <= set(routes)
    for route_id in NOTE_ROUTES:
        note = routes[route_id].get('learning_note')
        assert note and note.startswith('references/industry-learning/') and '..' not in note
        assert (ROOT / note).is_file()
    index = (ROOT / 'references/industry-learning/index.md').read_text(encoding='utf-8')
    for route_id in NOTE_ROUTES:
        assert Path(routes[route_id]['learning_note']).name in index


@pytest.mark.parametrize('route_id', sorted(NOTE_ROUTES))
def test_notes_only_cite_registered_standards(route_id):
    known = {s['id'] for s in catalogue()['standards']}
    text = (ROOT / _routes()[route_id]['learning_note']).read_text(encoding='utf-8')
    cited = set(STANDARD_ID.findall(text))
    assert cited, 'a learning note must point at catalogue records'
    assert cited <= known, sorted(cited - known)


def test_new_routes_return_core_records_without_automatic_adoption():
    food = route('food_processing')
    assert {'food-hygiene', 'food-machinery-safety', 'food-cleanroom-building'} <= {s['id'] for s in food['standards']}
    assert not food['auto_apply'] and not food['engineering_approval']
    assert food['route']['learning_note'] == 'references/industry-learning/food-processing.md'
    environment = route('environment_design')
    assert {'wayfinding-setting', 'public-symbols', 'accessibility'} <= {s['id'] for s in environment['standards']}


@pytest.mark.parametrize('route_id', sorted(NOTE_ROUTES))
def test_routes_return_their_teaching_sample_drawing(route_id):
    samples = route(route_id)['learning_samples']
    assert len(samples) == 1
    sample = samples[0]
    assert (ROOT / sample['file']).is_file() and sample['file'].endswith('.dxf')
    assert sample['self_checks_passed'] and sample['teaching_sample_only'] and not sample['engineering_approval']
    assert route('structure')['learning_samples'] == []


def test_food_processing_is_a_registered_industry_with_its_own_standards():
    from luomu_cad import industry
    result = industry.route(['food_processing'])
    assert {d['id'] for d in result['drawing_types']} == {
        'food_processing.site', 'food_processing.process_layout', 'food_processing.utilities'}
    ids = {s['id'] for s in result['standards']}
    assert {'food-hygiene', 'food-machinery-safety', 'pipe-symbols'} <= ids
    assert 'interior-drawing' not in ids and not result['auto_apply']
    mechanics = {s['id'] for s in industry.route(['mechanical'])['standards']}
    assert {'mechanical-views', 'surface-texture', 'iso-fits'} <= mechanics


def test_citation_only_records_are_not_presented_as_read_or_current():
    rows = [r for r in catalogue()['standards'] if r['evidence_level'] == 'government_citation']
    assert rows
    for row in rows:
        assert row['text_read'] == 'metadata_only'
        assert row['status_observed'] == 'cited_in_government_documents'
        assert '发布机关' in row['note']


def test_read_clauses_record_their_source_file_and_locators():
    row = next(r for r in catalogue()['standards'] if r['id'] == 'food-hygiene')
    assert row['text_read'] == 'selected_clauses' and row['read_locators']
    assert re.fullmatch('[0-9a-f]{64}', row['source_file_sha256'])
