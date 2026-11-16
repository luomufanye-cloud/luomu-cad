"""Optional headless LibreCAD bridge for offline DWG/DXF exchange.

LibreCAD (GPL-2.0) is never bundled, imported or linked here. The user installs
it separately and this module invokes it as an external command. Nothing about
the conversion is inferred from a process exit code: on Windows LibreCAD.exe is
a GUI-subsystem program that returns before the conversion finishes and sets no
exit code. Every result is established by reading the produced file back.

Converted files are exchange artifacts, not accepted deliverables. Geometry
fidelity, standards compliance and engineering approval stay unverified.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .storage import ROOT, inside

PROVIDER = 'librecad-cli'
COMMANDS = {
    'dxf2dwg': {'.dxf': '.dwg'},
    'dwg2dxf': {'.dwg': '.dxf'},
}
DWG_VERSIONS = {'r2000': b'AC1015', 'r2004': b'AC1018', 'r2007': b'AC1021',
                'r2010': b'AC1024', 'r2013': b'AC1027', 'r2018': b'AC1032'}
DXF_VERSIONS = {'r12', 'r14', 'r2000', 'r2004', 'r2007', 'r2010', 'r2013', 'r2018'}
OUTPUT_ROOT = ROOT / 'outputs' / 'dwg-bridge'
MAX_INPUT_BYTES = 200 * 1024 * 1024
MIN_DWG_BYTES = 512
PROCESS_TIMEOUT = 120
OUTPUT_WAIT_SECONDS = 15.0
PROBE_DXF = """0
SECTION
2
HEADER
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
8
0
10
0.0
20
0.0
30
0.0
11
1.0
21
0.0
31
0.0
0
ENDSEC
0
EOF
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _review_flags() -> dict:
    return {'round_trip_verified': False, 'source_fidelity_verified': False,
            'engineering_approval': False, 'accepted_for_delivery': False,
            'delivery_review_required': True,
            'delivery_review_tool': 'workbench_delivery'}


def locate() -> dict:
    """Resolve an operator-supplied executable; never guess an install folder."""
    configured = os.environ.get('LUOMU_CAD_LIBRECAD', '').strip()
    if configured:
        candidate = Path(configured).expanduser().resolve()
        if candidate.is_file():
            return {'found': True, 'executable': str(candidate), 'source': 'LUOMU_CAD_LIBRECAD'}
        return {'found': False, 'executable': str(candidate),
                'source': 'LUOMU_CAD_LIBRECAD',
                'reason': 'LUOMU_CAD_LIBRECAD does not point to an existing file'}
    for name in ('librecad', 'LibreCAD', 'LibreCAD.exe', 'librecad.exe'):
        found = shutil.which(name)
        if found:
            return {'found': True, 'executable': str(Path(found).resolve()), 'source': 'PATH'}
    return {'found': False, 'executable': None, 'source': None,
            'reason': 'LibreCAD not found on PATH; set LUOMU_CAD_LIBRECAD to its executable'}


def _environment() -> dict:
    env = dict(os.environ)
    # Headless hosts have no display. DWG/DXF conversion does not need a window,
    # but Qt still probes the platform plugin at startup on some builds.
    env.setdefault('QT_QPA_PLATFORM', 'offscreen')
    return env


def _run(executable: str, arguments: list[str], timeout: int = PROCESS_TIMEOUT) -> dict:
    started = time.monotonic()
    try:
        result = subprocess.run([executable, *arguments], capture_output=True,
                                text=True, errors='replace', timeout=timeout,
                                env=_environment(), check=False)
        return {'returncode': result.returncode,
                'stdout_tail': result.stdout[-1200:], 'stderr_tail': result.stderr[-1200:],
                'timed_out': False, 'elapsed_seconds': round(time.monotonic() - started, 2)}
    except subprocess.TimeoutExpired as error:
        return {'returncode': None, 'stdout_tail': '', 'stderr_tail': str(error)[:600],
                'timed_out': True, 'elapsed_seconds': round(time.monotonic() - started, 2)}
    except OSError as error:
        return {'returncode': None, 'stdout_tail': '', 'stderr_tail': str(error)[:600],
                'timed_out': False, 'elapsed_seconds': round(time.monotonic() - started, 2)}


def _minimum_bytes(direction: str) -> int:
    # A minimal R12 DXF is far smaller than any real DWG; using one shared
    # threshold would make every dwg2dxf result wait for a timeout.
    return MIN_DWG_BYTES if direction == 'dxf2dwg' else 32


def _await_output(output: Path, direction: str) -> bool:
    """Windows GUI LibreCAD returns before writing; poll for a stable file."""
    minimum = _minimum_bytes(direction)
    deadline = time.monotonic() + OUTPUT_WAIT_SECONDS
    last = -1
    while time.monotonic() < deadline:
        if output.is_file():
            size = output.stat().st_size
            if size >= minimum and size == last:
                return True
            last = size
        time.sleep(0.25)
    return output.is_file() and output.stat().st_size >= minimum


def _read_back(output: Path, direction: str, version: str | None) -> dict:
    """Independently inspect the artifact; never trust the converter's claim."""
    if not output.is_file():
        return {'ok': False, 'method': 'file', 'detail': 'output file was not created'}
    size = output.stat().st_size
    if size == 0:
        return {'ok': False, 'method': 'file', 'detail': 'output file is empty'}
    if direction == 'dxf2dwg':
        if size < MIN_DWG_BYTES:
            return {'ok': False, 'method': 'dwg-magic',
                    'detail': f'DWG is only {size} bytes, suspiciously small'}
        with output.open('rb') as stream:
            magic = stream.read(6)
        if not magic.startswith(b'AC10'):
            return {'ok': False, 'method': 'dwg-magic',
                    'detail': 'DWG header signature AC10xx not found'}
        if version and magic != DWG_VERSIONS[version]:
            return {'ok': False, 'method': 'dwg-magic',
                    'detail': f'expected {DWG_VERSIONS[version].decode()} header, got {magic!r}'}
        return {'ok': True, 'method': 'dwg-magic', 'detail': magic.decode('ascii', 'replace'),
                'bytes': size}
    # Structure is judged by the parser, not by scanning a text prefix. A
    # construction DXF may carry a very large HEADER/TABLES section or leading
    # comments, so any fixed-size sniff risks rejecting a valid drawing.
    try:
        import ezdxf

        document = ezdxf.readfile(str(output))
        entities = len(document.modelspace())
    except Exception as error:
        return {'ok': False, 'method': 'ezdxf-readback',
                'detail': f'{type(error).__name__}: {error}'[:400]}
    return {'ok': True, 'method': 'ezdxf-readback', 'detail': 'DXF parsed',
            'bytes': size, 'modelspace_entities': entities}


def _execute_one(executable: str, direction: str, source: Path, output: Path,
                 version: str | None, timeout: int = PROCESS_TIMEOUT) -> dict:
    arguments = [direction]
    if version:
        arguments += ['-V', version]
    arguments += ['-o', str(output), str(source)]
    process = _run(executable, arguments, timeout)
    # The Windows GUI executable provides no meaningful return code. Artifact
    # readback is the only acceptance signal; a nonzero code on other platforms
    # is recorded but does not replace it either.
    ready = _await_output(output, direction)
    readback = _read_back(output, direction, version) if ready else {
        'ok': False, 'method': 'file', 'detail': 'no stable output appeared before timeout'}
    return {'ok': bool(readback['ok']), 'direction': direction,
            'command': [direction, *(['-V', version] if version else []), '-o', '<output>', '<input>'],
            'process': process, 'readback': readback,
            'status': 'converted' if readback['ok'] else 'not_verified'}


def inspect_backend(probe: bool = False) -> dict:
    """Report what is actually available; probe performs a real minimal round trip."""
    located = locate()
    report = {'ok': located['found'], 'provider': PROVIDER,
              'status': 'available' if located['found'] else 'missing',
              'executable': located['executable'], 'executable_source': located.get('source'),
              'reason': located.get('reason'),
              'dwg_support_note': 'DWG conversion requires a LibreCAD build with DWGSUPPORT enabled',
              'commands': sorted(COMMANDS), 'probe_performed': False,
              **_review_flags()}
    if not located['found']:
        return report
    help_result = _run(located['executable'], ['-h'], timeout=30)
    help_text = (help_result['stdout_tail'] + help_result['stderr_tail']).lower()
    listed = {name: name in help_text for name in COMMANDS}
    report['help_available'] = bool(help_text.strip())
    if not help_text.strip():
        # Windows GUI builds often print nothing for -h. Unknown is not false:
        # only a real round trip can settle whether DWGSUPPORT is present.
        report['commands_listed_in_help'] = 'unknown'
        report['help_note'] = 'GUI build produced no help text; use probe=True for a real round trip'
    else:
        report['commands_listed_in_help'] = listed
        if not all(listed.values()):
            report['status'] = 'unsupported'
            report['ok'] = False
            report['reason'] = 'This LibreCAD build does not list dxf2dwg/dwg2dxf in its help output'
    if not probe:
        return report
    report['probe_performed'] = True
    report['probe'] = probe_round_trip(located['executable'])
    if not report['probe']['ok']:
        report['status'] = 'unsupported'
        report['ok'] = False
        report['reason'] = 'Minimal DXF -> DWG -> DXF round trip failed; see probe details'
    return report


def probe_round_trip(executable: str | None = None) -> dict:
    """Real evidence: convert a minimal DXF to DWG and back, reading both back."""
    target = executable or locate().get('executable')
    if not target:
        return {'ok': False, 'status': 'missing', 'reason': 'no LibreCAD executable',
                **_review_flags()}
    with tempfile.TemporaryDirectory(prefix='luomu-dwg-probe-') as temporary:
        folder = Path(temporary)
        source = folder / 'probe.dxf'
        dwg = folder / 'probe.dwg'
        back = folder / 'probe-back.dxf'
        source.write_text(PROBE_DXF, encoding='ascii')
        forward = _execute_one(target, 'dxf2dwg', source, dwg, None, timeout=60)
        if not forward['ok']:
            return {'ok': False, 'status': 'dxf2dwg_failed', 'forward': forward,
                    'reason': 'dxf2dwg produced no verifiable DWG', **_review_flags()}
        reverse = _execute_one(target, 'dwg2dxf', dwg, back, None, timeout=60)
        return {'ok': bool(reverse['ok']), 'status': 'round_trip_ok' if reverse['ok'] else 'dwg2dxf_failed',
                'forward': forward, 'reverse': reverse,
                'round_trip_verified': bool(reverse['ok']),
                'source_fidelity_verified': False, 'engineering_approval': False,
                'accepted_for_delivery': False, 'delivery_review_required': True}


def convert(direction: str, source: str, target: str,
            version: str | None = None, timeout: int = PROCESS_TIMEOUT) -> dict:
    """Convert one file with an external LibreCAD CLI and read the result back.

    ``target`` is a name relative to outputs/dwg-bridge inside the installation
    root. Existing outputs are refused. Input files are read-only and can live
    anywhere the process can read.
    """
    if direction not in COMMANDS:
        raise ValueError('direction must be dxf2dwg or dwg2dxf')
    expected_input, expected_output = next(iter(COMMANDS[direction].items()))
    versions = DWG_VERSIONS if direction == 'dxf2dwg' else DXF_VERSIONS
    if version and version not in versions:
        raise ValueError('unsupported output version: ' + str(version))
    input_path = Path(source).expanduser().resolve()
    if not input_path.is_file():
        return {'ok': False, 'status': 'missing_input', 'provider': PROVIDER,
                'reason': 'input file does not exist', **_review_flags()}
    if input_path.suffix.lower() != expected_input:
        return {'ok': False, 'status': 'wrong_input_format', 'provider': PROVIDER,
                'reason': f'{direction} expects a {expected_input} input', **_review_flags()}
    size = input_path.stat().st_size
    if size > MAX_INPUT_BYTES:
        return {'ok': False, 'status': 'input_too_large', 'provider': PROVIDER,
                'reason': f'input exceeds {MAX_INPUT_BYTES} bytes', **_review_flags()}
    try:
        output_path = inside(target, OUTPUT_ROOT)
    except ValueError as error:
        return {'ok': False, 'status': 'unsafe_output_path', 'provider': PROVIDER,
                'reason': str(error), **_review_flags()}
    if output_path.suffix.lower() != expected_output:
        return {'ok': False, 'status': 'wrong_output_suffix', 'provider': PROVIDER,
                'reason': f'{direction} writes {expected_output} files', **_review_flags()}
    if output_path.exists():
        return {'ok': False, 'status': 'output_exists', 'provider': PROVIDER,
                'reason': 'output already exists; choose a fresh name, no overwrite',
                **_review_flags()}
    located = locate()
    if not located['found']:
        return {'ok': False, 'status': 'missing', 'provider': PROVIDER,
                'reason': located.get('reason'), **_review_flags()}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='luomu-dwg-stage-', dir=output_path.parent) as temporary:
        staged = Path(temporary) / output_path.name
        result = _execute_one(located['executable'], direction, input_path,
                              staged, version, timeout)
        if result['ok']:
            if output_path.exists():
                result['ok'] = False
                result['status'] = 'output_exists'
                result['reason'] = 'output appeared during conversion; no overwrite'
            else:
                # Atomic publish on the same volume, only after readback passed.
                os.replace(staged, output_path)
        # An unverified staged artifact is discarded with the temporary dir,
        # so the output root never contains a file claimed as converted.
        result.update({'provider': PROVIDER, 'version': version,
                       'source': {'path': str(input_path), 'bytes': size,
                                  'sha256': sha256(input_path)},
                       'output': {'path': str(output_path),
                                  'bytes': output_path.stat().st_size if output_path.exists() else 0,
                                  'sha256': sha256(output_path) if output_path.exists() else None},
                       **_review_flags()})
    if not result['ok'] and result.get('status') == 'not_verified':
        result['status'] = 'not_verified'
        result['reason'] = result['readback']['detail']
    return result
