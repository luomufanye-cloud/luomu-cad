"""Exercise documented user tasks through real MCP; never connects to AutoCAD."""
import asyncio
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from luomu_cad import __version__
from luomu_cad.cli import execute
from luomu_cad.storage import ROOT, atomic_json
from verify_install import validate_generated_result


async def verify():
    spec = json.loads((ROOT/'examples/two-room.json').read_text(encoding='utf-8'))
    prefix = 'skill-tasks-'+__version__.replace('.','-')
    original = await execute('workbench_generate', {'job_id':prefix,'spec':spec})
    first = validate_generated_result(original, ROOT, spec)
    patched = await execute('workbench_patch_opening', {'job_id':prefix+'-patch',
        'source_job':prefix, 'expected_revision':original['revision'],
        'opening_id':'M2','changes':{'width':1000}})
    changed = copy.deepcopy(spec)
    next(o for o in changed['openings'] if o['id']=='M2')['width'] = 1000
    second = validate_generated_result(patched, ROOT, changed)
    assert patched['unrelated_entities_unchanged'] is True
    invalid = copy.deepcopy(spec)
    invalid['walls'][0]['thickness'] = -1
    rejected = await execute('workbench_generate', {'job_id':prefix+'-invalid','spec':invalid})
    assert rejected.get('ok') is False and not list((ROOT/'outputs'/(prefix+'-invalid')).glob('*.dxf'))
    card = await execute('workbench_technical', {'operation':'get','card_id':'pipe-root-interface-training'})
    assert card.get('ok') and card['card']['auto_apply'] is False
    steps = [s['id'] for s in card['card']['procedure']]
    wrong = await execute('workbench_technical', {'operation':'check_sequence',
        'card_id':card['card']['id'],'sequence':[s for s in steps if s!='seal']})
    assert wrong['ok'] is False and wrong['engineering_approval'] is False
    research = await execute('workbench_research', {'operation':'status'})
    assert research.get('ok') is True
    return {'ok':True,'version':__version__,'checks':{
        'example_generation':first,'door_patch':second,'unrelated_entities_unchanged':True,
        'invalid_input_rejected':True,'technical_card_read':True,
        'missing_seal_detected':True,'research_status_read':True},
        'cad_contacted':False,'external_collection_run':False,
        'agent_host_evaluated':False,'marketplace_review_passed':False}


def main():
    try:
        result = asyncio.run(verify())
    except Exception as exc:
        result = {'ok':False,'error':str(exc),'cad_contacted':False}
    atomic_json(ROOT/'runtime/verification/tasks.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['ok'] else 1


if __name__=='__main__':
    sys.exit(main())
