"""Install the optional solid-model runtime into a dedicated environment."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--index-url')
    args = parser.parse_args()
    uv = shutil.which('uv')
    if not uv:
        raise RuntimeError('uv must be available on PATH')
    runtime = args.runtime.resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    marker = runtime / 'luomu-solid-runtime.json'
    venv = runtime / '.venv'
    if venv.exists() and not marker.exists():
        raise ValueError('Select a new dedicated runtime directory')
    if marker.exists() and json.loads(marker.read_text(encoding='utf8')).get('provider') != 'agentcad':
        raise ValueError('Runtime belongs to another provider')
    python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        subprocess.run([uv, 'venv', str(venv), '--python', '3.11'], check=True)
    marker.write_text(json.dumps({'provider': 'agentcad', 'version': '0.7.2'}), encoding='utf8')
    lock = ROOT / 'references/solid-runtime-lock.json'
    locked = json.loads(lock.read_text(encoding='utf8')) if lock.exists() else {'requirements': ['agentcad[mcp]==0.7.2']}
    requirements = locked['requirements']
    command = [uv, 'pip', 'install', '--python', str(python), *requirements]
    if args.index_url:
        command.extend(['--index-url', args.index_url])
    subprocess.run(command, check=True)
    subprocess.run([str(python), '-c', 'import agentcad, build123d, mcp'], check=True)
    if locked.get('provider_files_sha256'):
        verify = ('import hashlib,json,sys,agentcad; from pathlib import Path; '
                  'root=Path(agentcad.__file__).parent; '
                  'expected=json.loads(sys.argv[1]); '
                  'assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in expected.items()), '
                  '"Installed solid runtime code differs from reviewed files"')
        subprocess.run([str(python), '-c', verify, json.dumps(locked['provider_files_sha256'])], check=True)
    registration = ROOT / 'runtime/solid-runtime.json'
    registration.parent.mkdir(exist_ok=True)
    registration.write_text(json.dumps({'python': str(python), 'provider': 'agentcad', 'version': '0.7.2'}, indent=2), encoding='utf8')
    print(json.dumps({'ok': True, 'python': str(python), 'registration': str(registration)}))


if __name__ == '__main__':
    main()
