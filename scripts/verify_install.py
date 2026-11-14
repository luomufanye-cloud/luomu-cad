"""Verify a complete Skill installation through real stdio MCP, without AutoCAD."""
import asyncio
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PIL import Image
from luomu_cad import __version__
from luomu_cad.cli import execute
from luomu_cad.plan import measured_check,validate_spec
from luomu_cad.qa import audit_dxf,file_hash
from luomu_cad.storage import ROOT,atomic_json


def validate_generated_result(result,root,spec):
    """Check actual saved files, not only the server's success flag."""
    if result.get('ok') is not True or result.get('target')!='offline':
        raise ValueError('Offline MCP generation failed: '+str(result.get('error',result.get('ok'))))
    directory=(Path(root)/'outputs'/result['job_id']).resolve()
    paths={}
    for key,name in [('dxf','plan.dxf'),('preview','preview.png'),('qa','qa.json'),('spec','spec.json')]:
        artifact=result.get('artifacts',{}).get(key,{})
        path=Path(artifact.get('path','')).resolve()
        if path!=directory/name or not path.is_file():raise ValueError(f'{key} must be inside this installation output job')
        if file_hash(path)!=artifact.get('sha256'):raise ValueError(f'{key} artifact hash mismatch')
        paths[key]=path
    expected_spec=json.loads(json.dumps(validate_spec(spec),ensure_ascii=False))
    if json.loads(paths['spec'].read_text(encoding='utf-8'))!=expected_spec:raise ValueError('Saved input differs from the installation example')
    geometry=audit_dxf(paths['dxf'])
    measured=measured_check(paths['dxf'],validate_spec(spec),result['owners'])
    if not geometry['ok'] or not measured['ok']:raise ValueError('Saved DXF geometry failed independent readback')
    try:
        with Image.open(paths['preview']) as preview:
            if preview.format!='PNG' or min(preview.size)<=0:raise ValueError('Expected a nonempty PNG preview')
            preview.verify()
    except Exception as exc:raise ValueError('Preview is not a valid PNG') from exc
    return {'artifact_hashes':'PASS','dxf_readback':'PASS','preview_file':'PASS',
            'visual_acceptance':'pending','professional_design':'not_reviewed',
            'artifacts':{k:str(v) for k,v in paths.items()}}


async def verify_installation(reviewer_project_root=None,reviewer_host='auto',reviewer_codex_home=None):
    if ROOT.resolve()!=Path(__file__).resolve().parents[1]:
        raise ValueError('LUOMU_CAD_ROOT points to another Skill folder; run this installation scripts/run.ps1')
    required=['SKILL.md','scripts/entry.py','src/luomu_cad/server.py','examples/two-room.json','references/usage.md','pyproject.toml','uv.lock',
              'agents/luomu-cad-reviewer.md','scripts/install_review_agent.py','src/luomu_cad/reviewer_install.py',
              'src/luomu_cad/delivery.py','src/luomu_cad/industry.py','references/industry-delivery.json',
              'scripts/run_review_agent.py','scripts/review_evidence_server.py','scripts/review_job_worker.py',
              'src/luomu_cad/review_runner.py','src/luomu_cad/review_codebuddy.py','src/luomu_cad/cad_access.py','src/luomu_cad/review_evidence_server.py',
              'src/luomu_cad/review_jobs.py','src/luomu_cad/native_delivery.py',
              'src/luomu_cad/native_correspondence.py','src/luomu_cad/pdf_strokes.py']
    missing=[p for p in required if not (ROOT/p).is_file()]
    if missing:raise ValueError('Incomplete Skill folder: '+', '.join(missing))
    from luomu_cad.reviewer_install import install,verify,install_codex_home,verify_codex_home
    if reviewer_codex_home is not None:
        if reviewer_project_root is not None:raise ValueError('Choose project or explicit CODEX_HOME reviewer scope')
        if reviewer_host not in {'auto','codex','t3'}:raise ValueError('CODEX_HOME scope requires a Codex host')
        reviewer_install=install_codex_home(ROOT,reviewer_codex_home)
        reviewer_check=verify_codex_home(reviewer_codex_home)
    else:
        reviewer_project_root=Path(reviewer_project_root or ROOT).resolve()
        reviewer_install=install(ROOT,reviewer_project_root,reviewer_host)
        reviewer_check=verify(reviewer_project_root,reviewer_host)
    if not reviewer_check['ok']:raise ValueError('Independent reviewer registration files failed verification')
    health=await execute('workbench_status',{})
    if health.get('ok') is not True or health.get('transport')!='stdio-mcp':raise ValueError('MCP health failed')
    if health.get('version')!=__version__:raise ValueError('MCP server version differs from this installation')
    if health.get('live_writes_enabled') is not False:raise ValueError('Installation verification requires live writes disabled')
    if Path(health.get('output_root','')).resolve()!=(ROOT/'outputs').resolve():raise ValueError('MCP server is using another installation output root')
    spec=json.loads((ROOT/'examples/two-room.json').read_text(encoding='utf-8'))
    fingerprint=hashlib.sha256(json.dumps(spec,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:12]
    job='install-check-'+__version__.replace('.','-')+'-'+fingerprint
    generated=await execute('workbench_generate',{'job_id':job,'spec':spec})
    checks=validate_generated_result(generated,ROOT,spec)
    config_path=ROOT/'runtime/mcp-config.json'
    atomic_json(config_path,{'mcpServers':{'luomu-cad':{
        'command':str(Path(sys.executable).resolve()),'args':['-u',str(ROOT/'scripts/entry.py'),'serve'],
        'env':{'LUOMU_CAD_ROOT':str(ROOT),'LUOMU_CAD_LIVE_WRITES':'0','PYTHONUTF8':'1'}}}})
    return {'ok':True,'version':__version__,'health':health,'checks':checks,'job_id':job,
            'default_reviewer':{'installation':reviewer_install,'verification':reviewer_check},
            'mcp_config_path':str(config_path),'mcp_config_format':'mcpServers JSON; adapt to the host format when necessary',
            'cad_contacted':False,'host_registration_verified':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    scope=parser.add_mutually_exclusive_group()
    scope.add_argument('--reviewer-project-root',type=Path,help='Project to receive native reviewer definitions; default is this installed repository')
    scope.add_argument('--reviewer-codex-home',type=Path,help='Explicit opt-in: install the reviewer for all projects using this CODEX_HOME')
    parser.add_argument('--reviewer-host',choices=['auto','codex','claude','codebuddy','t3'],default='auto')
    args=parser.parse_args()
    try:result=asyncio.run(verify_installation(args.reviewer_project_root,args.reviewer_host,args.reviewer_codex_home))
    except Exception as exc:result={'ok':False,'phase':'installation_verification','error':str(exc),'cad_contacted':False}
    try:atomic_json(ROOT/'runtime/verification/installation.json',result)
    except OSError as exc:result={'ok':False,'phase':'write_verification_report','error':str(exc),'cad_contacted':False}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['ok'] else 1


if __name__=='__main__':sys.exit(main())
