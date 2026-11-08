"""Actual optional native-kernel checks, enabled with LUOMU_CAD_SOLID_PYTHON."""
import json
import math
import os
from pathlib import Path

import pytest
from luomu_cad.solid_review import execute

ROOT = Path(__file__).resolve().parents[1]
PYTHON = os.environ.get('LUOMU_CAD_SOLID_PYTHON')
pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(not PYTHON, reason='Dedicated solid runtime not selected')]


async def test_native_plate_features_exact_diff_and_retry_identity(tmp_path):
    project = tmp_path / 'plate'; project.mkdir()
    assert (await execute('initialize', project, runtime=PYTHON))['ok']
    script = project / 'plate.py'
    original = (ROOT / 'examples/solid-mounting-plate.py').read_text(encoding='utf8')
    script.write_text(original, encoding='utf8')
    spec = project / 'features.json'
    spec.write_bytes((ROOT / 'examples/solid-plate-requirements.json').read_bytes())
    contract = json.loads((ROOT / 'examples/solid-plate-contract.json').read_text())
    built = await execute('run', project, runtime=PYTHON, source=script, label='base', idempotency_key='plate-base')
    assert built['ok'], built
    assert built['provider']=='luomu-cad'
    assert (project/'.luomu-solid/project.json').is_file()
    base = project / built['results']['run']['outputs']['step']
    replay = await execute('run', project, runtime=PYTHON, source=script, label='base', idempotency_key='plate-base')
    assert replay['ok'] and replay['results']['run']['version'] == built['results']['run']['version']
    checked = await execute('review', project, runtime=PYTHON, source=base, spec=spec, contract=contract)
    assert checked['ok'] and len(checked['render_files']) == 4, checked['failures']
    from luomu_cad.solid_render import image_has_content
    assert all(image_has_content(item['path']) for item in checked['render_files'].values())
    assert not checked['source_fidelity_verified']
    script.write_text(original.replace('Cylinder(3, 8)', 'Cylinder(4, 8)'), encoding='utf8')
    conflict = await execute('run', project, runtime=PYTHON, source=script, label='base', idempotency_key='plate-base')
    assert not conflict['ok']
    edited = await execute('run', project, runtime=PYTHON, source=script, label='wide', idempotency_key='plate-wide')
    assert edited['ok'], edited
    wide = project / edited['results']['run']['outputs']['step']
    wrong = await execute('review', project, runtime=PYTHON, source=wide, spec=spec, reference=base)
    assert not wrong['ok'] and 'FEATURE_REQUIREMENTS_NOT_PASSED' in wrong['failures']
    removed = wrong['results']['diff']['comparison_3d']['volumes']['reference_only']
    assert removed == pytest.approx(4 * math.pi * (4**2 - 3**2) * 8, abs=.001)
    new_spec = json.loads(spec.read_text()); new_spec['features'][0]['diameter_mm'] = 8
    spec.write_text(json.dumps(new_spec))
    intended = await execute('review', project, runtime=PYTHON, source=wide, spec=spec, reference=base,
        contract={'removed_volume_mm3':[removed-.001,removed+.001], 'added_volume_mm3':[0,.001]})
    assert intended['ok'], intended['failures']
    script.write_text(original.replace('show_object(plate)', 'show_object(Pos(10, 0, 0) * plate)'), encoding='utf8')
    moved = await execute('run', project, runtime=PYTHON, source=script, label='moved', idempotency_key='plate-moved')
    assert moved['ok'], moved
    spec.write_bytes((ROOT / 'examples/solid-plate-requirements.json').read_bytes())
    rejected = await execute('review', project, runtime=PYTHON, source=project/moved['results']['run']['outputs']['step'],
        spec=spec, reference=base, contract={**contract,'removed_volume_mm3':[0,.001], 'added_volume_mm3':[0,.001]})
    assert not rejected['ok']
    assert any('volume_mm3[0]_OUT_OF_RANGE' in s for s in rejected['failures'])
    assert rejected['results']['check_spec']['passed'] is True


async def test_native_stepped_shaft_independent_geometry(tmp_path):
    project = tmp_path / 'shaft'; project.mkdir()
    assert (await execute('initialize',project,runtime=PYTHON))['ok']
    script=project/'shaft.py'
    script.write_text('show_object(Cylinder(10,20) + Pos(0,0,15) * Cylinder(5,10))\n')
    spec=project/'requirements.json'
    spec.write_text(json.dumps({'expect_solids':1,'features':[
        {'name':'body','type':'cylinder','diameter_mm':20,'count':1},
        {'name':'tip','type':'cylinder','diameter_mm':10,'count':1}]}))
    result=await execute('run',project,runtime=PYTHON,source=script,label='shaft',idempotency_key='shaft-v1')
    assert result['ok'],result
    checked=await execute('review',project,runtime=PYTHON,source=project/result['results']['run']['outputs']['step'],
        spec=spec,contract={'bbox_mm':[[19.99,20.01],[19.99,20.01],[29.99,30.01]],
                            'volume_mm3':[2250*math.pi-.001,2250*math.pi+.001]})
    assert checked['ok'],checked['failures']


async def test_actual_stdio_mcp_can_launch_isolated_windows_runtime(tmp_path):
    from luomu_cad.cli import execute as mcp_call
    project=tmp_path/'mcp-project';project.mkdir()
    base={'project':str(project),'runtime':PYTHON}
    initialized=await mcp_call('workbench_solid',{**base,'operation':'initialize'})
    assert initialized['ok'],initialized
    (project/'model.py').write_text('show_object(Box(10,20,5))\n')
    (project/'features.json').write_text('{"expect_solids":1}')
    built=await mcp_call('workbench_solid',{**base,'operation':'run','source':'model.py',
        'label':'box','idempotency_key':'mcp-box'})
    assert built['ok'],built
    reviewed=await mcp_call('workbench_solid',{**base,'operation':'review',
        'source':built['results']['run']['outputs']['step'],'spec':'features.json',
        'contract':{'volume_mm3':[999.99,1000.01]}})
    assert reviewed['ok'],reviewed
    report_dir=Path(reviewed['report']['path']).parent
    assert all(Path(item['path']).parent==report_dir for item in reviewed['render_files'].values())
    from luomu_cad.solid_render import image_has_content
    assert all(image_has_content(item['path']) for item in reviewed['render_files'].values())
