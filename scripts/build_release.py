"""Allowlisted source release: no personal CAD files, caches or bundled libraries."""
import ast
import hashlib
import json
import re
import zipfile
import tomllib
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TOP={"README.md","THIRD_PARTY_NOTICES.md","SKILL.md","CHANGELOG.md","LICENSE","DEPENDENCIES.md","pyproject.toml","uv.lock",".gitignore"}
FOLDERS={"src","scripts","tests","examples","references","agents",".codex",".claude",".github"}
SUFFIXES={".py",".ps1",".mjs",".md",".json",".yaml",".yml",".toml"}
NATIVE_AGENTS={'.codex/agents/luomu-cad-reviewer.toml','.claude/agents/luomu-cad-reviewer.md'}


def files():
    result=[]
    candidates=[ROOT/name for name in TOP if (ROOT/name).is_file()]
    for folder in FOLDERS:
        candidates.extend((ROOT/folder).rglob('*'))
    for path in candidates:
        if not path.is_file():continue
        relative=path.relative_to(ROOT)
        if relative.parts[0] in {'.codex','.claude'} and relative.as_posix() not in NATIVE_AGENTS:
            continue
        if len(relative.parts)==1 and path.name in TOP:
            result.append(path)
        elif relative.parts[0] in FOLDERS and path.suffix in SUFFIXES and not {'__pycache__', 'node_modules'}.intersection(relative.parts):
            result.append(path)
    return sorted(result)


def validate(paths):
    blocked=[]
    for path in paths:
        text=path.read_text(encoding="utf-8-sig")
        if path.suffix==".py":ast.parse(text,filename=str(path))
        if path.suffix=='.toml':tomllib.loads(text)
        if re.search(r"(?:gh[pousr]_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9]{25,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"+"-----)",text):blocked.append(str(path))
        if re.search(r"(?:[A-Z]:[/\\](?:Users|ai工作台)|AppData[/\\]|codex"+"-clipboard)",text,re.I):blocked.append(str(path))
        if "vendor" in path.relative_to(ROOT).parts:blocked.append(str(path))
        if path.suffix==".md":
            for target in re.findall(r"\]\(([^)]+)\)",text):
                if "://" not in target and not target.startswith("#") and not (path.parent/target.split('#')[0]).exists():
                    raise ValueError(f"Broken local reference: {path.name}: {target}")
    if blocked:raise ValueError("Release scan failed: "+", ".join(blocked))
    return {"private_data_scan":"PASS","source_boundary":"no bundled CAD service sources","files":len(paths)}


def main():
    paths=files()
    checks=validate(paths)
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    version=tomllib.loads((ROOT/"pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    manifest={"project":"luomu-cad","version":version,"date":date.today().isoformat(),"checks":checks,"files":hashes}
    dist=ROOT/"dist"
    dist.mkdir(exist_ok=True)
    destination=dist/f"luomu-cad-{version}-source.zip"
    with zipfile.ZipFile(destination,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in paths:archive.write(path,path.relative_to(ROOT).as_posix())
        archive.writestr("release-manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip():raise RuntimeError("ZIP CRC check failed")
        for name,sha in hashes.items():
            if hashlib.sha256(archive.read(name)).hexdigest()!=sha:raise RuntimeError("ZIP hash mismatch")
    result={"ok":True,"path":str(destination),"bytes":destination.stat().st_size,"sha256":hashlib.sha256(destination.read_bytes()).hexdigest(),**checks}
    (dist/"release.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
