"""Offline DWG bridge regression; simulates the external CLI, never needs LibreCAD.

The real external program is exercised separately with operation='probe' on a
machine that has a DWGSUPPORT build installed.
"""
from pathlib import Path

import pytest

from luomu_cad import dwg_bridge


class FakeCLI:
    def __init__(self, mode='ok', help_text='dxf2dwg dwg2dxf dxf2pdf'):
        self.mode = mode
        self.help_text = help_text
        self.calls = []

    def __call__(self, executable, arguments, timeout=120):
        direction = arguments[0] if arguments else ''
        self.calls.append(direction)
        output = Path(arguments[arguments.index('-o') + 1]) if '-o' in arguments else None
        if output is not None and self.mode != 'no_output':
            if direction == 'dxf2dwg':
                payload = b'AC1015' + b'\x00' * 700 if self.mode == 'ok' else b'NOT_A_DWG' * 100
                output.write_bytes(payload)
            elif direction == 'dwg2dxf':
                import ezdxf

                document = ezdxf.new('R2010')
                document.modelspace().add_line((0, 0), (1, 0))
                document.saveas(output)
        return {'returncode': 0, 'stdout_tail': self.help_text if direction == '-h' else '',
                'stderr_tail': '', 'timed_out': False, 'elapsed_seconds': 0.01}


@pytest.fixture
def harness(monkeypatch, tmp_path):
    root = tmp_path / 'outputs'
    fake = FakeCLI()
    monkeypatch.setattr(dwg_bridge, 'OUTPUT_ROOT', root)
    monkeypatch.setattr(dwg_bridge, 'OUTPUT_WAIT_SECONDS', 1.0)
    monkeypatch.setattr(dwg_bridge, 'locate',
                        lambda: {'found': True, 'executable': 'fake-librecad', 'source': 'test'})
    monkeypatch.setattr(dwg_bridge, '_run', fake)
    return fake, root, tmp_path


def _source(folder, name, payload=b'0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n'):
    path = folder / name
    path.write_bytes(payload)
    return str(path)


def test_locate_prefers_explicit_environment_variable(monkeypatch, tmp_path):
    executable = tmp_path / 'librecad'
    executable.write_text('#!/bin/sh\n', encoding='utf-8')
    monkeypatch.setenv('LUOMU_CAD_LIBRECAD', str(executable))
    found = dwg_bridge.locate()
    assert found['found'] and found['source'] == 'LUOMU_CAD_LIBRECAD'
    monkeypatch.setenv('LUOMU_CAD_LIBRECAD', str(tmp_path / 'missing'))
    assert not dwg_bridge.locate()['found']


def test_status_missing_is_explicit(monkeypatch):
    monkeypatch.setattr(dwg_bridge, 'locate',
                        lambda: {'found': False, 'executable': None, 'source': None,
                                 'reason': 'not installed'})
    report = dwg_bridge.inspect_backend()
    assert report['ok'] is False and report['status'] == 'missing'
    assert report['accepted_for_delivery'] is False


def test_empty_help_is_unknown_not_unsupported(monkeypatch, harness):
    fake, _, _ = harness
    fake.help_text = ''
    report = dwg_bridge.inspect_backend()
    assert report['commands_listed_in_help'] == 'unknown'
    assert report['ok'] is True and report['status'] == 'available'


def test_help_without_dwg_commands_is_rejected(monkeypatch, harness):
    fake, _, _ = harness
    fake.help_text = 'dxf2pdf dxf2png dxf2svg only'
    report = dwg_bridge.inspect_backend()
    assert report['ok'] is False and report['status'] == 'unsupported'


def test_probe_round_trip_uses_real_artifact_readback(harness):
    fake, _, _ = harness
    report = dwg_bridge.probe_round_trip('fake-librecad')
    assert report['ok'] is True and report['status'] == 'round_trip_ok'
    assert report['round_trip_verified'] is True
    assert report['forward']['readback']['method'] == 'dwg-magic'
    assert report['reverse']['readback']['method'] == 'ezdxf-readback'
    assert report['accepted_for_delivery'] is False


def test_probe_fails_when_dwg_writer_is_absent(harness):
    fake, _, _ = harness
    fake.mode = 'no_output'
    report = dwg_bridge.probe_round_trip('fake-librecad')
    assert report['ok'] is False and report['status'] == 'dxf2dwg_failed'


def test_dxf2dwg_publishes_only_after_readback(harness):
    fake, root, folder = harness
    result = dwg_bridge.convert('dxf2dwg', _source(folder, 'in.dxf'), 'out.dwg', version='r2000')
    assert result['ok'] is True and result['status'] == 'converted'
    assert result['readback']['method'] == 'dwg-magic'
    produced = root / 'out.dwg'
    assert produced.is_file() and produced.read_bytes()[:6] == b'AC1015'
    assert result['output']['sha256'] == dwg_bridge.sha256(produced)
    assert result['source_fidelity_verified'] is False
    assert result['accepted_for_delivery'] is False
    assert result['delivery_review_required'] is True


def test_dxf2dwg_discards_unverifiable_artifact(harness):
    fake, root, folder = harness
    fake.mode = 'garbage'
    result = dwg_bridge.convert('dxf2dwg', _source(folder, 'in.dxf'), 'out.dwg')
    assert result['ok'] is False and result['status'] == 'not_verified'
    assert not (root / 'out.dwg').exists()
    assert result['output']['sha256'] is None


def test_dwg2dxf_parses_result_with_ezdxf(harness):
    fake, root, folder = harness
    result = dwg_bridge.convert('dwg2dxf', _source(folder, 'in.dwg', b'AC1015' + b'\x00' * 700),
                                'received.dxf', version='r2007')
    assert result['ok'] is True
    assert result['readback']['method'] == 'ezdxf-readback'
    assert result['readback']['modelspace_entities'] == 1
    assert (root / 'received.dxf').is_file()


def test_dxf_readback_handles_large_drawing_without_prefix_sniffing(harness):
    """A construction DXF is far larger than any fixed text slice."""
    import ezdxf

    fake, root, folder = harness
    large = folder / 'large.dxf'
    document = ezdxf.new('R2010')
    for index in range(6000):
        document.modelspace().add_line((index, 0), (index, 1))
    document.saveas(large)
    assert large.stat().st_size > 200000
    result = dwg_bridge._read_back(large, 'dwg2dxf', None)
    assert result['ok'] is True
    assert result['modelspace_entities'] == 6000


def test_output_path_escape_and_overwrite_are_refused(harness):
    fake, root, folder = harness
    source = _source(folder, 'in.dxf')
    escaped = dwg_bridge.convert('dxf2dwg', source, '../escape.dwg')
    assert escaped['ok'] is False and escaped['status'] == 'unsafe_output_path'
    root.mkdir(parents=True, exist_ok=True)
    (root / 'taken.dwg').write_bytes(b'existing')
    existing = dwg_bridge.convert('dxf2dwg', source, 'taken.dwg')
    assert existing['ok'] is False and existing['status'] == 'output_exists'
    assert (root / 'taken.dwg').read_bytes() == b'existing'


def test_wrong_formats_and_versions_are_refused(harness):
    fake, root, folder = harness
    wrong_input = dwg_bridge.convert('dxf2dwg', _source(folder, 'in.dwg', b'x'), 'out.dwg')
    assert wrong_input['ok'] is False and wrong_input['status'] == 'wrong_input_format'
    wrong_output = dwg_bridge.convert('dxf2dwg', _source(folder, 'in.dxf'), 'out.dxf')
    assert wrong_output['ok'] is False and wrong_output['status'] == 'wrong_output_suffix'
    with pytest.raises(ValueError):
        dwg_bridge.convert('dxf2dwg', _source(folder, 'in.dxf'), 'out.dwg', version='r1999')
    with pytest.raises(ValueError):
        dwg_bridge.convert('dxf2pdf', _source(folder, 'in.dxf'), 'out.pdf')
