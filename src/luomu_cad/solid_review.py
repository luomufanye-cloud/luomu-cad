"""Isolated solid-engine CLI adapter used by the workbench_solid MCP tool."""
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from .storage import ROOT

VERSION = '0.7.2'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def runtime_python(explicit=None):
    selected = explicit or os.environ.get('LUOMU_CAD_SOLID_PYTHON')
    registration = ROOT / 'runtime/solid-runtime.json'
    if not selected and registration.is_file():
        selected = json.loads(registration.read_text(encoding='utf8'))['python']
    if not selected or not Path(selected).is_file():
        raise ValueError('SOLID_RUNTIME_REQUIRED: run scripts/prepare_solid_runtime.py')
    return str(Path(selected).resolve())


def decode_response(stdout, stderr, returncode):
    text = stdout.decode('utf8')
    try:
        data = json.loads(text)
    except ValueError:
        # Some native graphics drivers print diagnostics on fd 1. Keep them
        # visible; accept only one complete final JSON object, never a fragment.
        lines = text.splitlines()
        candidates = []
        for index, line in enumerate(lines):
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                candidates.append((index, value))
        if len(candidates) != 1 or candidates[0][0] != len(lines) - 1:
            return {'status': 'error', 'error': 'SOLID_INVALID_JSON_RESPONSE',
                    'diagnostic': (text + stderr.decode('utf8', errors='replace'))[-4000:]}
        index, data = candidates[0]
        data['native_stdout_diagnostics'] = '\n'.join(lines[:index])[-4000:]
    if not isinstance(data, dict):
        raise ValueError('SOLID_RESPONSE_NOT_OBJECT')
    if returncode:
        data = {**data, 'status': 'error'}
    if stderr:
        data['stderr_diagnostics'] = stderr.decode('utf8', errors='replace')[-4000:]
    return data


async def invoke(python, project, arguments):
    try:
        result = await asyncio.to_thread(subprocess.run, [python, '-m', 'agentcad', *arguments],
            cwd=project, stdin=subprocess.DEVNULL, capture_output=True, timeout=180,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            env=dict(os.environ, PYTHONUTF8='1', AGENTCAD_NO_LOG='1'))
    except subprocess.TimeoutExpired:
        return {'status': 'error', 'error': 'SOLID_COMMAND_TIMEOUT',
                'execution_uncertain': True, 'next_action': 'Query run_status with the original key; do not repeat the build.'}
    return decode_response(result.stdout, result.stderr, result.returncode)


async def verify_runtime(python):
    try:
        result = await asyncio.to_thread(subprocess.run, [python, '-c',
            'from importlib.metadata import version; print(version("agentcad"))'],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    except subprocess.TimeoutExpired:
        raise ValueError('SOLID_RUNTIME_VERSION_QUERY_TIMEOUT') from None
    actual = result.stdout.decode('utf8').strip()
    if result.returncode or actual != VERSION:
        raise ValueError('SOLID_RUNTIME_VERSION_MISMATCH: expected ' + VERSION + ', got ' + actual)


def evaluate_review(results, contract, render_files, reference_requested=False):
    """Command success, geometry, feature verdict and edit limits are distinct."""
    failures = []
    for name in ('measure', 'inspect', 'check_spec', 'render'):
        if results.get(name, {}).get('status') != 'success':
            failures.append(name + '_FAILED')
    measured = results.get('measure', {})
    metrics = measured.get('metrics', {})
    comparison = results.get('diff', {}).get('comparison_3d', {})
    if metrics.get('is_valid') is not True:
        failures.append('GEOMETRY_NOT_VALID')
    if results.get('check_spec', {}).get('passed') is not True:
        failures.append('FEATURE_REQUIREMENTS_NOT_PASSED')
    for name, limits in contract.items():
        if name not in ('volume_mm3', 'bbox_mm', 'removed_volume_mm3', 'added_volume_mm3'):
            raise ValueError('Unsupported metric contract: ' + name)
        if name in ('removed_volume_mm3', 'added_volume_mm3'):
            if not reference_requested:
                raise ValueError('Directional volume contract requires a reference file')
            key = 'reference_only' if name == 'removed_volume_mm3' else 'candidate_only'
            values = [comparison.get('volumes', {}).get(key)]
        else:
            values = [metrics.get('volume')] if name == 'volume_mm3' else [metrics.get('dimensions', {}).get(axis) for axis in ('x', 'y', 'z')]
        bounds = limits if name == 'bbox_mm' else [limits]
        if len(bounds) != len(values):
            raise ValueError('Contract shape mismatch')
        for index, (value, interval) in enumerate(zip(values, bounds)):
            if not isinstance(interval, (list, tuple)) or len(interval) != 2 or any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in interval) or interval[0] > interval[1]:
                raise ValueError('Finite ordered measurement interval required')
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not interval[0] <= value <= interval[1]:
                failures.append(f'{name}[{index}]_OUT_OF_RANGE')
    if set(render_files) != {'front', 'right', 'top', 'iso'}:
        failures.append('FOUR_VIEWS_MISSING')
    if reference_requested:
        if (results.get('diff', {}).get('status') != 'success' or comparison.get('status') != 'success'
                or comparison.get('method') != 'source_frame_boolean_volume'
                or comparison.get('alignment', {}).get('mode') != 'source_frame'
                or comparison.get('alignment', {}).get('transform_applied') is not False):
            failures.append('EXACT_COMPARISON_UNAVAILABLE')
    return {'checks_passed': not failures, 'failures': failures,
            'visual_review_passed': False, 'source_fidelity_verified': False,
            'engineering_approval': False}


async def execute(operation, project, *, runtime=None, source=None, label=None,
                  idempotency_key=None, spec=None, reference=None, contract=None):
    if operation not in {'initialize', 'run', 'run_status', 'review', 'context'}:
        raise ValueError('Unknown solid workflow operation')
    python = runtime_python(runtime)
    await verify_runtime(python)
    project = Path(project).resolve()
    if not project.is_dir():
        raise ValueError('Existing project directory required')
    if operation == 'initialize':
        if any(project.iterdir()):
            raise ValueError('Initialize requires an empty project directory; preserves existing work')
        data = await invoke(python, project, ['init', '--name', project.name, '--runtime', 'build123d', '--no-agent-setup'])
        return {'ok': data.get('status') == 'success', 'result': data}
    files = {}
    for name, value, suffixes in [('source', source, ('.py',) if operation == 'run' else ('.step', '.stp', '.brep')),
                                  ('spec', spec, ('.json',)), ('reference', reference, ('.step', '.stp', '.brep'))]:
        if value:
            path = Path(value)
            if not path.is_absolute():
                path = project / path
            path = path.resolve()
            if not path.is_file() or path.suffix.lower() not in suffixes:
                raise ValueError('Missing or incompatible ' + name)
            files[name] = {'path': str(path), 'sha256': sha256(path)}
    if operation == 'run' and (not source or not label or not idempotency_key):
        raise ValueError('run requires reviewed source, label and caller-saved idempotency_key')
    if operation == 'run_status' and not idempotency_key:
        raise ValueError('run_status requires original idempotency_key')
    if operation == 'review' and (not source or not spec):
        raise ValueError('review requires saved geometry and independent feature requirements')
    results = {}
    async def call(name, *arguments):
        result = await invoke(python, project, list(arguments))
        results[name] = result
        return result
    if operation == 'run':
        await call('run', 'run', files['source']['path'], '--label', label, '--idempotency-key', idempotency_key,
                   '--no-preview', '--no-diff', '--no-view', '--no-daemon')
    elif operation == 'run_status':
        await call('run_status', 'run', '--idempotency-key', idempotency_key, '--status')
    elif operation == 'context':
        await call('context', 'context')
    else:
        await call('measure', 'measure', files['source']['path'], '--features', '--limit', '30', '--no-daemon')
        await call('inspect', 'inspect', files['source']['path'], '--summary', '--limit', '20', '--no-daemon')
        await call('check_spec', 'check-spec', files['source']['path'], files['spec']['path'], '--no-daemon')
        await call('render', 'render', files['source']['path'], '--view', 'all', '--no-daemon')
        if reference:
            await call('diff', 'diff', files['reference']['path'], files['source']['path'], '--no-daemon')
    changed = [name for name, item in files.items() if sha256(item['path']) != item['sha256']]
    if changed:
        raise ValueError('SOLID_INPUT_CHANGED: ' + ','.join(changed))
    report = {'operation': operation, 'provider': 'agentcad', 'provider_version': VERSION,
              'engine_transport': 'isolated-cli', 'inputs': files, 'results': results,
              'ok': all(r.get('status') == 'success' for r in results.values())}
    if operation == 'review':
        images = {}
        for name, value in results.get('render', {}).get('renders', {}).items():
            path = Path(value)
            if not path.is_absolute():
                path = project / path
            if path.is_file() and path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
                images[name] = {'path': str(path.resolve()), 'sha256': sha256(path)}
        report.update(evaluate_review(results, contract or {}, images, bool(reference)))
        report['render_files'] = images
        report['contract'] = contract or {}
        report['ok'] = report['ok'] and report['checks_passed']
        review_dir = project / 'luomu-reviews' / uuid.uuid4().hex
        review_dir.mkdir(parents=True)
        for name, item in images.items():
            target = review_dir / (name + '.png')
            shutil.copy2(item['path'], target)
            if sha256(target) != item['sha256']:
                raise ValueError('SOLID_RENDER_CHANGED_DURING_ARCHIVE')
            item['path'] = str(target)
        destination = review_dir / 'report.json'
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
        report['report'] = {'path': str(destination), 'sha256': sha256(destination)}
    return report
