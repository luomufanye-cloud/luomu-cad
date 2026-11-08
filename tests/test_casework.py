"""Multiview size contracts, source checks and native drawing mutation tests."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import ezdxf
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from luomu_cad.casework import build, draw, normalize, review
from luomu_cad.cli import unpack
from luomu_cad.qa import file_hash
from luomu_cad.storage import ROOT


def example():
    return json.loads((ROOT/'examples/casework.json').read_text(encoding='utf8'))


def load_manifest(result):
    return json.loads(Path(result['artifacts']['manifest']['path']).read_text(encoding='utf8'))


def test_three_views_read_native_dimensions_and_share_their_sizes(tmp_path):
    result = build(example(), tmp_path/'bundle')
    assert result['ok'], result['review']
    dims = result['review']['dimensions_mm']
    assert dims['front.width'] == dims['plan.width'] == 2400
    assert dims['front.body_height'] == pytest.approx(2300)
    assert dims['section.body_height'] == pytest.approx(2300)
    assert dims['front.overall_height'] == pytest.approx(2400)
    assert dims['section.overall_height'] == pytest.approx(2400)
    assert dims['plan.depth'] == dims['section.depth'] == 600
    assert dims['front.closure'] == 100 and dims['front.plinth'] == 80
    doc = ezdxf.readfile(result['artifacts']['dxf']['path'])
    assert len(list(doc.modelspace().query('DIMENSION'))) == 14
    assert not list(doc.modelspace().query('LWPOLYLINE'))
    assert result['review']['cross_view_pairs_checked'] == 4


def test_height_change_updates_both_elevation_and_section_but_not_plan(tmp_path):
    spec = example()
    a = build(spec, tmp_path/'a')
    spec['height_mm'] = 2700
    b = build(spec, tmp_path/'b')
    ma, mb = load_manifest(a), load_manifest(b)
    def relative_rows(manifest, view):
        origin = manifest['views'][view]['origin']
        return [[r['key'], [v-origin[i] for i,v in enumerate(r['start'])],
                 [v-origin[i] for i,v in enumerate(r['end'])]]
                for r in manifest['geometry'] if r['kind']=='LINE' and r.get('view')==view]
    assert relative_rows(ma, 'plan') == relative_rows(mb, 'plan')
    for view in ('front', 'section'):
        assert relative_rows(ma, view) != relative_rows(mb, view)
    assert b['review']['dimensions_mm']['front.body_height'] == pytest.approx(2600)
    assert b['review']['dimensions_mm']['section.overall_height'] == pytest.approx(2700)


def test_body_height_and_overall_height_are_not_confused(tmp_path):
    spec = example();spec['height_basis'] = 'body'
    result = build(spec, tmp_path/'body')
    assert result['ok']
    dims = result['review']['dimensions_mm']
    assert dims['front.body_height'] == pytest.approx(2400)
    assert dims['section.overall_height'] == pytest.approx(2500)


@pytest.mark.parametrize('change', [
    {'height_basis': 'guessed'}, {'width_mm': True}, {'depth_mm': float('nan')},
    {'front_widths_mm': [600, 600]}, {'opening_mm': 2400}, {'section_bay': 0},
    {'panel_mm': 400}, {'back_mm': 650}, {'top_closure_mm': 2500},
    {'interiors': [{'bay': 1, 'shelves_mm': [500, 505]}]},
    {'interiors': [{'bay': 1, 'shelves_mm': [20]}]},
    {'interiors': [{'bay': 1}, {'bay': 1}]},
    {'sheet': {'scale': 10, 'paper_mm': [210,297]}},
    {'sheet': {'scale': 30, 'lineweights_mm': {'outline': .251, 'hidden': .13, 'cut': .35, 'annotation': .13}}},
])
def test_impossible_or_ambiguous_models_fail_before_output(tmp_path, change):
    spec=example();spec.update(change)
    with pytest.raises(ValueError):
        build(spec,tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_outline_mode_does_not_invent_board_thickness(tmp_path):
    spec=example();spec['detail_level']='reference_outline'
    spec.pop('panel_mm');spec.pop('back_mm')
    result=build(spec,tmp_path/'outline')
    assert result['ok']
    manifest=load_manifest(result)
    assert not any(r.get('role')=='cut' for r in manifest['geometry'])
    assert not result['review']['manufacturing_approved']


@pytest.mark.parametrize('mutation', ['line', 'dimension', 'cached_text', 'cached_line', 'dimension_weight',
                                     'lineweight', 'linetype', 'line_scale', 'global_scale', 'extra', 'delete'])
def test_saved_geometry_dimensions_and_styles_are_actually_read(tmp_path,mutation):
    result=build(example(),tmp_path/'bundle');manifest=load_manifest(result)
    path=Path(result['artifacts']['dxf']['path']);doc=ezdxf.readfile(path)
    if mutation=='line':
        row=next(r for r in manifest['geometry'] if r.get('view')=='section' and r.get('key')=='envelope:1')
        doc.entitydb[row['handle']].dxf.end += (0, 50, 0)
    elif mutation=='dimension':
        e=doc.entitydb[manifest['dimensions']['front.width']['handle']]
        e.dxf.defpoint3 += (100,0,0)
    elif mutation=='cached_text':
        e=doc.entitydb[manifest['dimensions']['front.width']['handle']]
        text=next(v for v in doc.blocks[e.dxf.geometry] if v.dxftype() in ('TEXT','MTEXT'))
        text.dxf.text='9999'
    elif mutation=='cached_line':
        e=doc.entitydb[manifest['dimensions']['front.width']['handle']]
        line=next(v for v in doc.blocks[e.dxf.geometry] if v.dxftype()=='LINE')
        line.dxf.lineweight=90
    elif mutation=='dimension_weight':
        e=doc.entitydb[manifest['dimensions']['front.width']['handle']]
        overrides=e.override();overrides['dimlwd']=90;overrides.commit()
    elif mutation=='lineweight':
        doc.layers.get('CW-OUTLINE').dxf.lineweight=70
    elif mutation=='linetype':
        doc.layers.get('CW-HIDDEN').dxf.linetype='CONTINUOUS'
    elif mutation=='line_scale':
        next(e for e in doc.modelspace().query('LINE') if e.dxf.layer=='CW-HIDDEN').dxf.ltscale=1
    elif mutation=='global_scale':
        doc.header['$LTSCALE']=100
    elif mutation=='extra':
        doc.modelspace().add_line((0,0),(10,10))
    else:
        doc.modelspace().delete_entity(doc.entitydb[manifest['dimensions']['section.depth']['handle']])
    doc.saveas(path)
    manifest.pop('drawing_sha256')  # Exercise geometric checks independently of the file hash.
    check=review(path,manifest)
    assert not check['ok'],mutation
    assert check['findings']


def test_independent_source_requirements_are_bound_and_wrong_dimensions_fail(tmp_path):
    source=tmp_path/'source.txt';source.write_text('Original design brief: W2400 D600 H2400 overall, closure100.',encoding='utf8')
    requirements={'source':{'sha256':file_hash(source),'locator':'Independent design brief, first line'},
                  'dimensions_mm':{'front.width':2400,'front.body_height':2300,'front.overall_height':2400,
                                   'plan.depth':600,'section.depth':600},'tolerance_mm':.001}
    result=build(example(),tmp_path/'bundle',requirements,source)
    assert result['ok'] and result['review']['independent_source_check']['passed']
    bad=copy.deepcopy(requirements);bad['dimensions_mm']['front.body_height']=2400
    check=review(result['artifacts']['dxf']['path'],load_manifest(result),bad,source)
    assert not check['ok']
    source.write_text('changed source',encoding='utf8')
    check=review(result['artifacts']['dxf']['path'],load_manifest(result),requirements,source)
    assert any(f['kind']=='independent_source_hash_mismatch' for f in check['findings'])
    with pytest.raises(ValueError,match='original source'):
        review(result['artifacts']['dxf']['path'],load_manifest(result),requirements)


def test_repeated_output_refused_and_source_files_preserved(tmp_path):
    result=build(example(),tmp_path/'bundle')
    old=file_hash(result['artifacts']['dxf']['path'])
    with pytest.raises(ValueError,match='empty'):
        build(example(),tmp_path/'bundle')
    assert file_hash(result['artifacts']['dxf']['path'])==old


def test_actual_casework_pdf_has_the_requested_page_and_paper_lineweights(tmp_path):
    from io import BytesIO
    from pypdf import PdfReader
    from pypdf.generic import ContentStream
    from luomu_cad.pdf_export import render_pdf
    result=build(example(),tmp_path/'paper')
    data,settings=render_pdf(result['artifacts']['dxf']['path'],[420,297],[0,0,12600,8910],30,0)
    reader=PdfReader(BytesIO(data));page=reader.pages[0]
    assert float(page.mediabox.width)==pytest.approx(420*72/25.4)
    assert float(page.mediabox.height)==pytest.approx(297*72/25.4)
    assert settings['scale']==30
    widths=[float(args[0]) for args,op in ContentStream(page.get_contents(),reader).operations if op==b'w']
    for mm in [.13,.25,.35]:
        assert any(abs(v-mm*72/25.4)<.001 for v in widths)
    (tmp_path/'casework.pdf').write_bytes(data)


def test_cli_build_and_review(tmp_path):
    env=dict(os.environ,PYTHONUTF8='1')
    output=tmp_path/'cli'
    args=[sys.executable,str(ROOT/'scripts/build_casework.py')]
    result=subprocess.run([*args,'build','--spec',str(ROOT/'examples/casework.json'),'--output',str(output)],env=env,capture_output=True,text=True,encoding='utf8')
    assert result.returncode==0,result.stderr
    result=subprocess.run([*args,'review','--drawing',str(output/'casework.dxf'),'--manifest',str(output/'casework-manifest.json')],env=env,capture_output=True,text=True,encoding='utf8')
    assert result.returncode==0,result.stderr


@pytest.mark.asyncio
async def test_actual_stdio_mcp_build_and_review(tmp_path):
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),LUOMU_CAD_ROOT=str(tmp_path),LUOMU_CAD_LIVE_WRITES='0',PYTHONUTF8='1')
    parameters=StdioServerParameters(command=sys.executable,args=['-m','luomu_cad.server'],env=env,cwd=str(ROOT))
    async with stdio_client(parameters) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            result=unpack(await session.call_tool('workbench_casework',{'spec':example(),'output':str(tmp_path/'mcp')}))
            assert result['ok'],result
            again=unpack(await session.call_tool('workbench_casework',{'operation':'review','drawing':result['artifacts']['dxf']['path'],'manifest':load_manifest(result)}))
            assert again['ok'] and again['dimensions_mm']['front.width']==2400
            outside=await session.call_tool('workbench_casework',{'spec':example(),'output':str(tmp_path.parent/'escape')})
            assert outside.isError
