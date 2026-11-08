"""Build a rooted WorkBuddy marketplace ZIP from the same reviewed Skill sources."""
import hashlib
import json
import posixpath
import re
import tomllib
import zipfile
from pathlib import Path, PurePosixPath
from build_release import ROOT, files, validate

FIELDS = ['name', 'display_name', 'display_name_en', 'description', 'description_zh',
          'description_en', 'version', 'author']
DEVELOPMENT_SCRIPTS={'build_release.py','build_workbuddy.py','release_smoke.py','verify_download.py'}


def market_path(name):
    for old,new in [('src/luomu_cad/','luomu_cad/'),('references/technical/','technical/'),('references/learned/','learned/')]:
        if name.startswith(old):return new+name[len(old):]
    return name


def market_files(root, paths):
    selected={p.relative_to(root).as_posix():p for p in paths
              if p.relative_to(root).parts[0] not in {'tests','.github','.codex','.claude'}
              and not (p.relative_to(root).parts[0]=='scripts' and p.name in DEVELOPMENT_SCRIPTS)}
    mapping={name:market_path(name) for name in selected}
    if len(set(mapping.values()))!=len(mapping):raise ValueError('Market path collision')
    skill,_=marketplace_skill(root)
    output={}
    for name,path in selected.items():
        text=skill if name=='SKILL.md' else path.read_text(encoding='utf-8')
        if path.suffix=='.md':
            def link(match):
                target=match.group(1)
                if '://' in target or target.startswith('#'):return match.group(0)
                file,sep,anchor=target.partition('#')
                old=posixpath.normpath(posixpath.join(posixpath.dirname(name),file))
                if old not in mapping:return match.group(0)
                relative=posixpath.relpath(mapping[old],posixpath.dirname(mapping[name]) or '.')
                return ']('+relative+(sep+anchor if sep else '')+')'
            text=re.sub(r'\]\(([^)]+)\)',link,text)
        # Relocate only project-relative resource/import paths; business logic is shared.
        text=text.replace('src/luomu_cad','luomu_cad')
        text=re.sub(r"references/(technical|learned)(?=/|['\"]|$)",r'\1',text)
        if path.suffix in {'.py','.ps1','.toml'}:
            text=re.sub(r'(/)(\s*)([\'\"])src\3',r'\1\2\3.\3',text)
            text=text.replace("Join-Path $projectRoot 'src'", "Join-Path $projectRoot '.'")
        if name=='src/luomu_cad/storage.py':
            text=text.replace('Path(__file__).resolve().parents[2]','Path(__file__).resolve().parents[1]')
        if len(PurePosixPath(mapping[name]).parts)>2:
            raise ValueError('Market directory depth exceeded: '+name)
        output[mapping[name]]=text.encode('utf-8')
    for name,data in output.items():
        if name.endswith('.py'):
            compile(data,name,'exec')
        if name.endswith('.md'):
            for target in re.findall(r'\]\(([^)]+)\)',data.decode('utf-8')):
                if '://' in target or target.startswith('#'):continue
                resolved=posixpath.normpath(posixpath.join(posixpath.dirname(name),target.split('#')[0]))
                if resolved not in output:raise ValueError('Broken market link: '+name+': '+target)
    return output


def marketplace_skill(root):
    meta = json.loads((root/'references/workbuddy-market.json').read_text(encoding='utf-8'))
    meta['version'] = tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    for key in FIELDS:
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            raise ValueError('Missing WorkBuddy metadata: '+key)
    if meta['name'] != 'luomu-cad':
        raise ValueError('Unexpected Skill identity')
    text = (root/'SKILL.md').read_text(encoding='utf-8')
    parts = text.split('---', 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError('Invalid source frontmatter')
    header = '\n'.join(k+': '+json.dumps(v, ensure_ascii=False) for k,v in meta.items())
    return '---\n'+header+'\n---'+parts[2], meta


def validate_archive(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip():
            raise ValueError('Duplicate or corrupted ZIP entries')
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or p.parts[0] != 'luomu-cad':
                raise ValueError('Unsafe or incorrectly rooted Skill entry')
            if len(p.parts)>(2 if name.endswith('/') else 3):
                raise ValueError('WorkBuddy directory depth exceeded: '+name)
        text = archive.read('luomu-cad/SKILL.md').decode('utf-8')
        header = text.split('---',2)[1]
        meta = {line.split(':',1)[0]:json.loads(line.split(':',1)[1]) for line in header.strip().splitlines()}
        if any(not isinstance(meta.get(key),str) or not meta[key].strip() for key in FIELDS):
            raise ValueError('Missing required marketplace field')
        try:
            project=tomllib.loads(archive.read('luomu-cad/pyproject.toml').decode('utf-8'))
        except KeyError as exc:
            raise ValueError('Incomplete runtime: pyproject.toml') from exc
        if meta['name']!='luomu-cad' or meta['version']!=project['project']['version']:
            raise ValueError('Marketplace identity/version mismatch')
        for required in ['scripts/preflight.py','scripts/entry.py','scripts/verify_tasks.py',
                         'agents/luomu-cad-reviewer.md','scripts/install_review_agent.py','scripts/verify_delivery.py',
                         'scripts/run_review_agent.py','scripts/review_evidence_server.py','scripts/review_job_worker.py',
                         'luomu_cad/review_runner.py','luomu_cad/review_evidence_server.py','luomu_cad/review_jobs.py',
                         'luomu_cad/native_delivery.py','luomu_cad/native_correspondence.py','luomu_cad/pdf_strokes.py',
                         'luomu_cad/server.py','technical/pipe-root-interface-training.json',
                         'learned/index.md','examples/two-room.json','uv.lock']:
            if 'luomu-cad/'+required not in names:
                raise ValueError('Incomplete runtime: '+required)
        return {'ok': True, 'version':meta['version'], 'root':'luomu-cad', 'files':len(names),
                'max_directory_depth':2}


def main():
    paths = files()
    validate(paths)
    _,meta = marketplace_skill(ROOT)
    content=market_files(ROOT,paths)
    target = ROOT/'dist'/f"luomu-cad-workbuddy-{meta['version']}.zip"
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in content.items():
            archive.writestr('luomu-cad/'+name,data)
    result = {**validate_archive(target), 'path':str(target),
              'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
              'marketplace_sandbox_verified':False}
    (ROOT/'dist/workbuddy.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
