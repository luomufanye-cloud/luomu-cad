"""Committed learning sample drawings stay reproducible, auditable and linked."""
import json
import sys
from pathlib import Path

import ezdxf
import pytest

from luomu_cad.learning_samples import SAMPLES, build, canonical
from luomu_cad.qa import audit_dxf
from luomu_cad.standards import catalogue

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'examples'
INDEX = json.loads((EXAMPLES / 'learning-samples.json').read_text(encoding='utf-8'))


def test_committed_samples_match_the_generator(tmp_path):
    build(tmp_path)
    for name, _ in SAMPLES:
        assert canonical(EXAMPLES / name) == canonical(tmp_path / name), name
    fresh = (tmp_path / 'learning-samples.json').read_text(encoding='utf-8')
    assert fresh == (EXAMPLES / 'learning-samples.json').read_text(encoding='utf-8').replace('\r\n', '\n')


@pytest.mark.parametrize('name', [name for name, _ in SAMPLES])
def test_samples_pass_saved_geometry_audit(name):
    result = audit_dxf(EXAMPLES / name)
    assert result['ok'], result['findings']


def test_index_links_routes_notes_and_standards():
    value = catalogue()
    known = {s['id'] for s in value['standards']}
    routes = {r['id'] for r in value['routes']}
    assert [s['file'] for s in INDEX['samples']] == [name for name, _ in SAMPLES]
    for sample in INDEX['samples']:
        assert sample['route'] in routes
        assert set(sample['standard_ids']) <= known, sample['id']
        note = ROOT / sample['learning_note']
        assert sample['file'] in note.read_text(encoding='utf-8'), 'learning note must link its sample'
        assert sample['self_checks'] and all(c['result'] == 'pass' for c in sample['self_checks'])
    assert '不是工程' in INDEX['notice']


def test_mechanical_sample_shows_true_measurements_at_enlarged_scale():
    doc = ezdxf.readfile(EXAMPLES / 'learning-mechanical-shaft.dxf')
    measured = sorted(round(float(d.get_measurement()), 3) for d in doc.modelspace().query('DIMENSION'))
    assert measured == sorted([30, 36, 24, 20, 12, 25, 20, 40, 20, 25, 120, 8, 26])
    assert int(doc.header['$INSUNITS']) == 4
    texts = {t.dxf.text for t in doc.modelspace().query('TEXT')}
    assert {'A-A', '2:1'} <= texts


def test_release_allowlists_only_the_generated_sample_dxf():
    sys.path.insert(0, str(ROOT / 'scripts'))
    import build_release
    names = {p.relative_to(ROOT).as_posix() for p in build_release.files()}
    assert {f'examples/{name}' for name, _ in SAMPLES} <= names
    assert build_release.GENERATED_DXF.fullmatch('examples/learning-food-bakery.dxf')
    for private in ('examples/client-plan.dxf', 'references/learning-plan.dxf', 'examples/learning-../x.dxf'):
        assert not build_release.GENERATED_DXF.fullmatch(private)


def test_text_styles_declare_long_fangsong_and_gb_number_fonts():
    for name, _ in SAMPLES:
        doc = ezdxf.readfile(EXAMPLES / name)
        fs = doc.styles.get('LM-FS')
        assert fs.dxf.font == 'simfang.ttf' and fs.get_extended_font_data()[0] == 'FangSong'
        assert doc.styles.get('LM-NUM').dxf.font == 'gbenor.shx'
        assert all(abs(t.dxf.width - 0.7) < 1e-9 for t in doc.modelspace().query('TEXT'))
