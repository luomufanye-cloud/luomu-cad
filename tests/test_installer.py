"""Behaviour of the one-line installer (install.mjs) inside an isolated home directory."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / 'install.mjs'
REPO = 'https://github.com/luomufanye-cloud/luomu-cad.git'

pytestmark = pytest.mark.skipif(shutil.which('node') is None or shutil.which('git') is None,
                                reason='installer tests need node and git')


def _env(home, extra=None):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('GIT_')}
    env.update({'HOME': str(home), 'USERPROFILE': str(home), 'GIT_CONFIG_NOSYSTEM': '1',
                'GIT_TERMINAL_PROMPT': '0',
                'GIT_AUTHOR_NAME': 'test', 'GIT_AUTHOR_EMAIL': 'test@example.invalid',
                'GIT_COMMITTER_NAME': 'test', 'GIT_COMMITTER_EMAIL': 'test@example.invalid'})
    env.update(extra or {})
    return env


def _git(env, *args, cwd=None):
    subprocess.run(['git', *args], cwd=cwd, env=env, check=True, capture_output=True)


def _install(home, *args, extra_env=None):
    return subprocess.run(['node', str(INSTALLER), *args], env=_env(home, extra_env),
                          capture_output=True, text=True, encoding='utf-8', errors='replace',
                          timeout=120)


def _repository(path, content, env, origin=None):
    path.mkdir(parents=True)
    (path / 'SKILL.md').write_text(content, encoding='utf-8')
    _git(env, 'init', '-q', cwd=path)
    if origin:
        _git(env, 'remote', 'add', 'origin', origin, cwd=path)
    _git(env, 'add', 'SKILL.md', cwd=path)
    _git(env, 'commit', '-q', '-m', content, cwd=path)


@pytest.fixture
def home(tmp_path):
    home = tmp_path / 'home'
    (home / '.claude' / 'skills').mkdir(parents=True)
    return home


@pytest.fixture
def dest(home):
    return home / '.claude' / 'skills' / 'luomu-cad'


def test_equals_form_selects_the_target(home):
    # codex has no skills directory here, so auto-detection alone would skip it.
    result = _install(home, '--target=codex', '--dry-run')
    assert result.returncode == 0, result.stdout + result.stderr
    assert '[codex]' in result.stdout
    assert '[claude]' not in result.stdout


@pytest.mark.parametrize('args', [('--dry-run', '--target'), ('--target=', '--dry-run'),
                                  ('--target', '--dry-run')])
def test_target_without_a_value_is_an_error(home, args):
    result = _install(home, *args)
    assert result.returncode == 1
    assert 'needs a value' in result.stderr


@pytest.mark.parametrize('origin', [REPO, 'git@github.com:luomufanye-cloud/luomu-cad.git',
                                    'https://user:token@github.com/LuomuFanye-Cloud/luomu-cad/'])
def test_own_checkout_is_recognised_in_any_spelling(home, dest, origin):
    _repository(dest, 'local', _env(home), origin)
    result = _install(home, '--target', 'claude', '--dry-run')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'existing checkout found' in result.stdout


@pytest.mark.parametrize('origin', ['https://github.com/someone/luomu-cad.git',
                                    'https://github.com/luomufanye-cloud/luomu-cad-fork.git'])
def test_similarly_named_repository_is_refused_and_left_untouched(home, dest, origin):
    _repository(dest, 'local', _env(home), origin)
    result = _install(home, '--target', 'claude')
    assert result.returncode == 1
    assert 'not a checkout of this repository' in result.stdout
    assert (dest / 'SKILL.md').read_text(encoding='utf-8') == 'local'


def test_force_reinstall_recovers_a_checkout_that_cannot_fast_forward(home, dest, tmp_path):
    env = _env(home)
    _repository(tmp_path / 'upstream-work', 'upstream', env)
    bare = tmp_path / 'upstream.git'
    _git(env, 'clone', '-q', '--bare', str(tmp_path / 'upstream-work'), str(bare))
    # Point the public URL at the local bare repository; no network is used.
    redirect = {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': f'url.{bare.as_uri()}.insteadOf',
                'GIT_CONFIG_VALUE_0': REPO}
    # The local branch has no upstream, so `git pull --ff-only` fails.
    _repository(dest, 'local', env, REPO)

    failed = _install(home, '--target', 'claude', extra_env=redirect)
    assert failed.returncode == 1
    assert 'fast-forward failed' in failed.stdout
    assert (dest / 'SKILL.md').read_text(encoding='utf-8') == 'local'

    recovered = _install(home, '--target', 'claude', '--force-reinstall', extra_env=redirect)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert (dest / 'SKILL.md').read_text(encoding='utf-8') == 'upstream'
    backups = list(dest.parent.glob('luomu-cad.bak-*'))
    assert len(backups) == 1
    assert (backups[0] / 'SKILL.md').read_text(encoding='utf-8') == 'local'
