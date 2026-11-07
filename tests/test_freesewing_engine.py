"""Opt-in execution of the actual installed upstream design; no copied patterns."""
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/draft_freesewing.mjs'
MODULE = os.environ.get('LUOMU_CAD_FREESEWING_MODULE')
pytestmark = pytest.mark.skipif(not MODULE, reason='Explicit installed upstream module required')


@pytest.mark.parametrize('neck', [360, 400, 450])
def test_original_freesewing_draft_and_repeat(tmp_path, neck):
    settings = tmp_path / 'settings.json'
    settings.write_text(json.dumps({'measurements': {'neck': neck}, 'sa': 10, 'paperless': True}))
    output = tmp_path / 'pattern.svg'
    command = ['node', str(SCRIPT), MODULE, 'Benjamin', str(settings), str(output)]
    first = subprocess.run(command, capture_output=True, text=True, check=True)
    report = json.loads(first.stdout)
    assert report['draft_errors'] == []
    assert report['warnings'] == []
    assert report['version'] == '4.10.2'
    root = ET.fromstring(output.read_text(encoding='utf-8'))
    paths = root.findall('.//{http://www.w3.org/2000/svg}path')
    assert any('C' in p.get('d', '') or 'c' in p.get('d', '') for p in paths)
    assert len(paths) > 5
    repeated = subprocess.run(command, capture_output=True, text=True, check=True)
    assert json.loads(repeated.stdout) == report


def test_invalid_measurement_fails_without_output(tmp_path):
    settings = tmp_path / 'invalid.json'
    settings.write_text(json.dumps({'measurements': {'neck': -3}}))
    output = tmp_path / 'pattern.svg'
    result = subprocess.run(['node', str(SCRIPT), MODULE, 'Benjamin', str(settings), str(output)], capture_output=True)
    assert result.returncode != 0
    assert not output.exists()
