"""Verify a complete Skill installation through real stdio MCP, without AutoCAD."""
import asyncio
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


async def verify_installation():
    if ROOT.resolve()!=Path(__file__).resolve().parents[1]:
        raise ValueError('LUOMU_CAD_ROOT points to another Skill folder; run this installation scripts/run.ps1')
    required=['SKILL.md','scripts/entry.py','src/luomu_cad/server.py','examples/two-room.json','references/usage.md','pyproject.toml','uv.lock']
    missing=[p for p in required if not (ROOT/p).is_file()]
    if missing:raise ValueError('Incomplete Skill folder: '+', '.join(missing))
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
            'mcp_config_path':str(config_path),'mcp_config_format':'mcpServers JSON; adapt to the host format when necessary',
            'cad_contacted':False,'host_registration_verified':False}


def main():
    try:result=asyncio.run(verify_installation())
    except Exception as exc:result={'ok':False,'phase':'installation_verification','error':str(exc),'cad_contacted':False}
    try:atomic_json(ROOT/'runtime/verification/installation.json',result)
    except OSError as exc:result={'ok':False,'phase':'write_verification_report','error':str(exc),'cad_contacted':False}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['ok'] else 1


if __name__=='__main__':sys.exit(main())
