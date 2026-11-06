"""Exercise documented user tasks through real MCP; never connects to AutoCAD."""
import asyncio
import copy
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from luomu_cad import __version__
from luomu_cad.cli import execute
from luomu_cad.storage import ROOT, atomic_json
from verify_install import validate_generated_result
from verify_redraw import audit as audit_redraw, compare_patch


def verify_redraw_sequence():
    """Reproducible native dimensions and two successive scoped edits."""
    import ezdxf
    folder = ROOT/'runtime/verification/redraw'
    folder.mkdir(parents=True, exist_ok=True)
    doc = ezdxf.new('R2018', setup=True)
    doc.units = 4
    model = doc.modelspace()
    model.add_line((0, 0), (3000, 0))
    dimension = model.add_linear_dim(base=(0, 500), p1=(0, 0), p2=(3000, 0),
                                     override={'dimlfac': 1})
    dimension.render()
    title = model.add_text('Original plan', dxfattribs={'height': 100, 'insert': (0, 1000)})
    note = model.add_text('Retained note', dxfattribs={'height': 100, 'insert': (0, 1200)})
    initial = folder/'initial.dxf'
    doc.saveas(initial)
    contract = {'source': 'Original synthetic 3000 mm segment and two annotations', 'units': 4,
        'dimensions': [{'handle':dimension.dimension.dxf.handle, 'start':[0,0,0], 'end':[3000,0,0],
                        'measurement':3000, 'tolerance':0.01, 'dimlfac':1}],
        'texts':['Original plan', 'Retained note'],
        'expected_handles':[e.dxf.handle for e in model]}
    assert audit_redraw(initial, contract)['checks_passed']
    def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    # First accepted change; second edit must retain this new title.
    title.dxf.text = 'Revised title'
    first = folder/'first.dxf'; doc.saveas(first)
    assert compare_patch(initial, first, sha(initial), [title.dxf.handle])['checks_passed']
    note.dxf.insert = (100, 1200, 0)
    second = folder/'second.dxf'; doc.saveas(second)
    assert compare_patch(first, second, sha(first), [note.dxf.handle])['checks_passed']
    contract['texts'][0] = 'Revised title'
    assert audit_redraw(second, contract)['checks_passed']
    title.dxf.text = 'Original plan'
    regression = folder/'regression.dxf'; doc.saveas(regression)
    assert not compare_patch(first, regression, sha(first), [note.dxf.handle])['checks_passed']
    title.dxf.text = 'Revised title'
    model.add_line((0, 50), (3000, 50))
    extra = folder/'unexpected-wall.dxf'; doc.saveas(extra)
    assert not audit_redraw(extra, contract)['checks_passed']
    assert not compare_patch(first, extra, sha(first), [note.dxf.handle])['checks_passed']
    result = {'native_dimension_verified':True, 'two_successive_edits_verified':True,
              'prior_correction_rollback_rejected':True, 'unexpected_geometry_rejected':True,
              'reference':'original synthetic fixture; not a customer drawing or host model run',
              'files':{p.name:sha(p) for p in (initial,first,second,regression,extra)}}
    atomic_json(folder/'result.json',result)
    return result


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
        'missing_seal_detected':True,'research_status_read':True,
        'redraw_and_edit_sequence':verify_redraw_sequence()},
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
