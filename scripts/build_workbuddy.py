"""Build a rooted WorkBuddy marketplace ZIP from the same reviewed Skill sources."""
import hashlib
import json
import tomllib
import zipfile
from pathlib import Path, PurePosixPath
from build_release import ROOT, files, validate

FIELDS = ['name', 'display_name', 'display_name_en', 'description', 'description_zh',
          'description_en', 'version', 'author']


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
                         'src/luomu_cad/server.py','examples/two-room.json','uv.lock']:
            if 'luomu-cad/'+required not in names:
                raise ValueError('Incomplete runtime: '+required)
        return {'ok': True, 'version':meta['version'], 'root':'luomu-cad', 'files':len(names)}


def main():
    paths = files()
    validate(paths)
    skill,meta = marketplace_skill(ROOT)
    target = ROOT/'dist'/f"luomu-cad-workbuddy-{meta['version']}.zip"
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            relative = path.relative_to(ROOT)
            if relative.parts[0] in {'tests','.github'}:
                continue
            if relative.as_posix() == 'SKILL.md':
                archive.writestr('luomu-cad/SKILL.md',skill)
            else:
                archive.write(path,'luomu-cad/'+relative.as_posix())
    result = {**validate_archive(target), 'path':str(target),
              'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
              'marketplace_sandbox_verified':False}
    (ROOT/'dist/workbuddy.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
