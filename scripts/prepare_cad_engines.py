"""Install optional upstream kernels into an explicitly selected separate runtime."""
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
    parser.add_argument('--index-url', help='Optional Python package index for this installation')
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    uv, npm = shutil.which('uv'), shutil.which('npm')
    if not uv or not npm:
        raise RuntimeError('uv and npm must be installed and available on PATH')
    runtime.mkdir(parents=True, exist_ok=True)
    venv = runtime / '.venv'
    python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        subprocess.run([uv, 'venv', str(venv), '--python', '3.11'], check=True)
    lock = json.loads((ROOT / 'references/cad-engines-python.json').read_text(encoding='utf-8'))
    command = [uv, 'pip', 'install', '--python', str(python), *lock['requirements']]
    if args.index_url:
        command.extend(['--index-url', args.index_url])
    subprocess.run(command, check=True)
    sewing = runtime / 'sewing'
    sewing.mkdir(exist_ok=True)
    for filename in ('package.json', 'package-lock.json'):
        source = ROOT / 'references' / ('freesewing-' + filename)
        target = sewing / filename
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise ValueError('Runtime npm configuration differs; use a fresh dedicated directory')
        target.write_bytes(source.read_bytes())
    subprocess.run([npm, 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], cwd=sewing, check=True)
    print(json.dumps({'python': str(python), 'sewing': str(sewing)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
