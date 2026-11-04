"""Extract the actual allowlisted source ZIP and verify it in an independent venv."""
import json
import os
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    release=json.loads((ROOT/"dist/release.json").read_text(encoding="utf-8"))
    destination=ROOT/"runtime/verification"/release["sha256"][:12]
    if destination.exists():raise ValueError("Verification directory already exists; preserve evidence and use a new release")
    destination.mkdir(parents=True)
    with zipfile.ZipFile(release["path"]) as archive:
        for name in archive.namelist():
            if not (destination/name).resolve().is_relative_to(destination):raise ValueError("Unsafe ZIP member")
        archive.extractall(destination)
    env=dict(os.environ,LUOMU_CAD_ROOT=str(destination),UV_PROJECT_ENVIRONMENT=str(destination/".venv"),PYTHONPATH=str(destination/"src"),PYTHONUTF8="1")
    logs=ROOT/"runtime/verification"
    def run(name,command):
        result=subprocess.run(command,cwd=destination,env=env,capture_output=True,encoding="utf-8",errors="replace",timeout=300)
        (logs/f"{name}.stdout.log").write_text(result.stdout,encoding="utf-8")
        (logs/f"{name}.stderr.log").write_text(result.stderr,encoding="utf-8")
        if result.returncode:raise RuntimeError(f"{name} failed: {result.stdout[-1000:]} {result.stderr[-1000:]}")
        return result.stdout
    run("install",["uv","sync","--python","3.11","--managed-python","--locked","--extra","dev","--no-editable","--link-mode","copy"])
    python=destination/".venv"/("Scripts/python.exe" if os.name=="nt" else "bin/python")
    tests=run("tests",[str(python),"-X","utf8","-m","pytest","-q","--junitxml=runtime/clean-tests.xml"])
    health=json.loads(run("health",[str(python),"-X","utf8","scripts/entry.py","health"]))
    if Path(health["output_root"])!=destination/"outputs":raise RuntimeError("Original project was reused")
    result={"ok":True,"package_sha256":release["sha256"],"clean_venv":True,"original_project_reused":False,
        "health":health,"tests":tests.strip(),"cad_modified":False,"live_write_verified":False}
    (logs/"release-smoke.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"ok":True,"package_sha256":release["sha256"],"tests":tests.strip()},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
