"""Install project-local review agents without altering host settings or users' roles."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import tomllib

AGENT_NAME = 'luomu-cad-reviewer'
HOST_PATHS = {
    'codex': '.codex/agents/luomu-cad-reviewer.toml',
    'claude': '.claude/agents/luomu-cad-reviewer.md',
}
DESCRIPTION = '独立检查 CAD 客户需求、分行业标准、原生图纸与实际出图，交付前默认委派；缺项或失败不得放行。'


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _inside(root, relative):
    target = root.joinpath(relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError('Agent destination must remain inside the explicit project root')
    return target


def _atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def definitions(bundle_root, project_root):
    """Generate standalone native files from the same canonical review instructions."""
    bundle = Path(bundle_root).resolve(strict=True)
    project = Path(project_root).resolve(strict=True)
    source = bundle/'agents/luomu-cad-reviewer.md'
    if not source.is_file():
        raise ValueError('Complete Skill bundle with agents/luomu-cad-reviewer.md required')
    prompt = source.read_text(encoding='utf-8-sig').strip()
    if not prompt or '\x00' in prompt:
        raise ValueError('Invalid reviewer instructions')
    try:
        relative = os.path.relpath(bundle, project).replace('\\', '/')
    except ValueError:
        relative = bundle.as_posix()
    # Resource path is data in role instructions; it is never executed by installation.
    prompt += '\n\n本次安装的 Luomu CAD 完整资源目录：'+relative+'。相对路径以项目根目录为基准。\n'
    codex = '\n'.join([
        'name = '+json.dumps(AGENT_NAME),
        'description = '+json.dumps(DESCRIPTION, ensure_ascii=False),
        'developer_instructions = '+json.dumps(prompt, ensure_ascii=False),
        '',
    ])
    parsed = tomllib.loads(codex)
    if set(parsed) != {'name', 'description', 'developer_instructions'}:
        raise ValueError('Unexpected host settings in agent definition')
    claude = '\n'.join([
        '---', 'name: '+AGENT_NAME,
        'description: '+json.dumps(DESCRIPTION, ensure_ascii=False),
        'disallowedTools: Edit, Write, NotebookEdit',
        '---', '', prompt, '',
    ])
    return {'codex': codex.encode('utf8'), 'claude': claude.encode('utf8')}


def install(bundle_root, project_root, host='auto'):
    """Install both documented project scopes by default; never enable host capabilities."""
    project = Path(project_root).resolve(strict=True)
    if not project.is_dir():
        raise ValueError('An existing explicit project root is required')
    if host not in {'auto', 'codex', 'claude', 't3'}:
        raise ValueError('host must be auto/codex/claude/t3')
    # T3's Codex provider launches the Codex app server. There is no invented T3 role schema.
    hosts = ['codex', 'claude'] if host == 'auto' else ['codex' if host == 't3' else host]
    content = definitions(bundle_root, project)
    receipt_path = _inside(project, '.luomu-cad/reviewer-install.json')
    old = json.loads(receipt_path.read_text(encoding='utf8')) if receipt_path.is_file() else {}
    ownership = {entry['path']: entry['sha256'] for entry in old.get('files', [])}
    planned = []
    for kind in hosts:
        relative = HOST_PATHS[kind]
        target = _inside(project, relative)
        previous = target.read_bytes() if target.is_file() else None
        if target.exists() and not target.is_file():
            raise ValueError('Agent path is not a regular file: '+relative)
        data = content[kind]
        if previous is not None and previous != data and ownership.get(relative) != _hash(previous):
            raise ValueError('AGENT_CONFLICT: preserve existing user agent: '+relative)
        planned.append((relative, target, data, previous))
    # All collision checks finish before any existing file is changed.
    written = []
    try:
        for relative, target, data, previous in planned:
            if target.is_file() and target.read_bytes() != previous:
                raise ValueError('AGENT_CHANGED_DURING_INSTALL: '+relative)
            if not target.exists() and previous is not None:
                raise ValueError('AGENT_CHANGED_DURING_INSTALL: '+relative)
            if previous != data:
                _atomic(target, data)
                written.append((target, previous))
        merged = {entry['path']: entry for entry in old.get('files', [])}
        for relative, _, data, _ in planned:
            merged[relative] = {'path': relative, 'sha256': _hash(data)}
        receipt = {'schema_version': 1, 'agent_name': AGENT_NAME, 'files': list(merged.values()),
                   'instruction_sha256': _hash((Path(bundle_root)/'agents/luomu-cad-reviewer.md').read_bytes())}
        _atomic(receipt_path, json.dumps(receipt, ensure_ascii=False, indent=2).encode('utf8'))
    except Exception:
        for target, previous in reversed(written):
            if previous is None:
                target.unlink(missing_ok=True)
            else:
                _atomic(target, previous)
        raise
    return {'ok': True, 'agent_name': AGENT_NAME, 'host': host,
            'project_root': str(project), 'files_installed': [str(p[1]) for p in planned],
            'files_changed': len(written), 'runtime_discovery_verified': False,
            'cli_available': {kind: bool(shutil.which(kind)) for kind in hosts},
            'global_or_provider_config_changed': False,
            'permission_boundary': 'Inherits host settings; behavioral review-only instructions are not a sandbox',
            'activation': 'Open a trusted project in a compatible host; current Codex sessions may need a fresh session. Claude first agents directory needs restart.',
            't3_support': 'Codex-provider native project agent definition only; T3 UI delegation was not tested' if host == 't3' else None,
            'receipt': str(receipt_path)}


def verify(project_root, host='auto'):
    project = Path(project_root).resolve(strict=True)
    if host not in {'auto', 'codex', 'claude', 't3'}:
        raise ValueError('host must be auto/codex/claude/t3')
    hosts = ['codex', 'claude'] if host == 'auto' else ['codex' if host == 't3' else host]
    receipt_path = _inside(project, '.luomu-cad/reviewer-install.json')
    receipt = json.loads(receipt_path.read_text(encoding='utf8')) if receipt_path.is_file() else {}
    ownership = {entry['path']: entry['sha256'] for entry in receipt.get('files', [])}
    findings = []
    files = []
    for kind in hosts:
        relative = HOST_PATHS[kind]
        path = _inside(project, relative)
        if not path.is_file():
            findings.append({'kind': 'agent_missing', 'path': relative})
            continue
        data = path.read_bytes()
        if ownership.get(relative) != _hash(data):
            findings.append({'kind': 'agent_changed_or_unowned', 'path': relative})
        try:
            if kind == 'codex':
                value = tomllib.loads(data.decode('utf8'))
                if value.get('name') != AGENT_NAME or not value.get('description') or not value.get('developer_instructions'):
                    raise ValueError('Required Codex native fields missing')
                if set(value) != {'name', 'description', 'developer_instructions'}:
                    raise ValueError('Unowned settings in role definition')
            elif not data.decode('utf8').startswith('---\nname: '+AGENT_NAME+'\n'):
                raise ValueError('Claude native role header missing')
        except (ValueError, UnicodeError) as exc:
            findings.append({'kind': 'invalid_native_agent', 'path': relative, 'error': str(exc)})
        files.append({'path': relative, 'sha256': _hash(data)})
    return {'ok': not findings, 'agent_name': AGENT_NAME, 'files': files, 'findings': findings,
            'runtime_discovery_verified': False, 'model_weights_trained': False}
