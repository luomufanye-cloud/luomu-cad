"""Independently install and test a trusted downloaded Skill ZIP (executes its code)."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import zipfile


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path)
    p.add_argument('--destination',required=True,type=Path)
    p.add_argument('--kind',choices=['github','workbuddy'],required=True)
    args=p.parse_args()
    if args.kind=='workbuddy':
        from build_workbuddy import validate_archive
        validate_archive(args.archive)
    destination=args.destination.resolve()
    if destination.exists():raise ValueError('Use a new directory; retain previous evidence')
    with zipfile.ZipFile(args.archive) as z:
        roots=set()
        for name in z.namelist():
            part=PurePosixPath(name)
            if part.is_absolute() or '..' in part.parts or '\\' in name:raise ValueError('Unsafe ZIP entry')
            if ((z.getinfo(name).external_attr>>16)&0o170000)==0o120000:raise ValueError('ZIP symlink rejected')
            roots.add(part.parts[0])
        if len(roots)!=1:raise ValueError('Expected one Skill directory')
        destination.mkdir(parents=True)
        z.extractall(destination)
    root=destination/next(iter(roots))
    env=dict(os.environ,LUOMU_CAD_ROOT=str(root),UV_PROJECT_ENVIRONMENT=str(root/'.venv'),PYTHONPATH=str(root/'src'),PYTHONUTF8='1',LUOMU_CAD_LIVE_WRITES='0')
    stages={}
    def run(label,command):
        r=subprocess.run(command,cwd=root,env=env,capture_output=True,encoding='utf-8',errors='replace',timeout=600)
        (destination/(label+'.log')).write_text(r.stdout+'\n'+r.stderr,encoding='utf-8')
        stages[label]={'exit_code':r.returncode}
        if r.returncode:raise RuntimeError(label+': '+r.stdout[-800:]+r.stderr[-800:])
        return r.stdout
    sync=['uv','sync','--python','3.11','--managed-python','--locked','--no-editable','--link-mode','copy']
    if args.kind=='github':sync+=['--extra','dev']
    run('install',sync)
    python=root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    preflight=json.loads(run('preflight',[str(python),'scripts/preflight.py','--mode','offline']))
    if args.kind=='github':
        stages_text=run('tests',[str(python),'-m','pytest','-q'])
        stages['tests']['summary']=stages_text.strip()
    install=json.loads(run('installation',[str(python),'scripts/verify_install.py']))
    tasks=json.loads(run('tasks',[str(python),'scripts/verify_tasks.py']))
    assert preflight['ok'] and install['ok'] and tasks['ok']
    assert Path(install['health']['output_root'])==root/'outputs'
    result={'ok':True,'kind':args.kind,'version':install['version'],
        'archive_sha256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        'isolated_root':str(root),'stages':stages,'installation':install,'tasks':tasks,
        'cad_contacted':False,'marketplace_sandbox_verified':False}
    (destination/'acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'ok':True,'version':install['version'],'report':str(destination/'acceptance.json')},ensure_ascii=False))


if __name__=='__main__':main()
