"""Prepare Luomu CAD's isolated geometry-kernel environment."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--index-url')
    args=parser.parse_args()
    uv=shutil.which('uv')
    if not uv:raise RuntimeError('uv is required')
    runtime=args.runtime.resolve();runtime.mkdir(parents=True,exist_ok=True)
    marker=runtime/'luomu-solid-runtime.json';venv=runtime/'.venv'
    if venv.exists() and (not marker.is_file() or json.loads(marker.read_text()).get('provider')!='luomu-cad'):
        raise ValueError('Use a new dedicated Luomu CAD runtime directory')
    python=venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.exists():subprocess.run([uv,'venv',str(venv),'--python','3.11'],check=True)
    marker.write_text(json.dumps({'provider':'luomu-cad','version':'1.0'}),encoding='utf8')
    lock=json.loads((ROOT/'references/solid-runtime-lock.json').read_text(encoding='utf8'))
    command=[uv,'pip','install','--python',str(python),*lock['requirements']]
    if args.index_url:command+=['--index-url',args.index_url]
    subprocess.run(command,check=True)
    subprocess.run([str(python),'-c','import build123d,matplotlib,PIL'],check=True)
    registration=ROOT/'runtime/solid-runtime.json';registration.parent.mkdir(exist_ok=True)
    registration.write_text(json.dumps({'python':str(python),'provider':'luomu-cad','version':'1.0'},indent=2),encoding='utf8')
    print(json.dumps({'ok':True,'python':str(python),'registration':str(registration)}))

if __name__=='__main__':main()
