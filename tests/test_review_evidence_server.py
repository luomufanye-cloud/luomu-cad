"""Read-only boundaries and real stdio MCP protocol, without model/API/CAD calls."""
import hashlib
import json
from pathlib import Path
import sys
from datetime import timedelta

import ezdxf
import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,ArrayObject,FloatObject,DecodedStreamObject
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

from luomu_cad.storage import ROOT
from luomu_cad.review_runner import _prepare,_previews,_evidence_lock,_mcp_evidence
from luomu_cad.review_evidence_server import Evidence,facts


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def sample(tmp_path):
    brief=tmp_path/'customer.json'
    brief.write_text(json.dumps({'scope':'reference_redraw','requirements':[{'id':'R1','description':'Original1000mm line','artifact_ids':['native','paper']}],
        'required_sheets':[{'sheet_id':'P01','formats':['dxf','pdf']}]}),encoding='utf8')
    dxf=tmp_path/'P01.dxf';doc=ezdxf.new();doc.units=4;doc.modelspace().add_line((0,0),(1000,0));doc.modelspace().add_lwpolyline([(0,0),(1000,0),(1000,500),(0,500)],close=True)
    doc.modelspace().add_linear_dim(base=(0,-100),p1=(0,0),p2=(1000,0)).render();doc.saveas(dxf)
    pdf=tmp_path/'P01.pdf';writer=PdfWriter();writer.add_blank_page(width=297*72/25.4,height=210*72/25.4)
    with pdf.open('wb') as stream:writer.write(stream)
    source=tmp_path/'original.png';Image.new('RGB',(30,20),'white').save(source)
    standard=tmp_path/'customer-standard.txt';standard.write_text('Original customer-supplied drawing convention: units mm.',encoding='utf8')
    record=lambda p:{'path':p.name,'sha256':sha(p)}
    packet=tmp_path/'packet.json';packet.write_text(json.dumps({'schema_version':1,'contract_id':'original',
        'customer_brief':record(brief),'artifacts':[dict(record(dxf),id='native'),dict(record(pdf),id='paper')],
        'raw_sources':[record(source)],'standard_sources':[record(standard)]}),encoding='utf8')
    output=tmp_path/'review';output.mkdir()
    _,_,_,_,paths,_=_prepare(packet)
    lock_path,lock=_evidence_lock(packet,_previews(paths,output),output,'fixture-evidence')
    return packet,output,lock_path,lock


def test_native_fact_reader_returns_actual_geometry_pdf_and_original_content(tmp_path):
    packet,output,lock_path,lock=sample(tmp_path)
    evidence=Evidence(packet,lock_path,output)
    value=evidence.read('artifact:native')
    assert value['facts']['units']==4 and value['source_sha256']==sha(tmp_path/'P01.dxf')
    assert value['facts']['entities'][0]['dxf']['end']==[1000,0,0]
    assert len(value['facts']['entities'][1]['vertices_xyseb'])==4
    assert value['facts']['entities'][2]['native_measurement']==1000
    assert value['facts']['entities'][2]['dimension_style']['name']
    paper=evidence.read('artifact:paper')['facts']['pages'][0]['size_mm']
    assert paper==pytest.approx([297,210],abs=0.0001)
    assert evidence.read('brief')['facts']['content']['requirements'][0]['id']=='R1'
    assert evidence.read('standard:0')['facts']['text'].startswith('Original customer-supplied')
    assert 'accepted_for_delivery' not in value


@pytest.mark.parametrize('format',['asc','bin'])
def test_snapshot_dxf_keeps_real_units_and_native_values_in_ascii_and_binary(tmp_path,format):
    path=tmp_path/'original.dxf';doc=ezdxf.new();doc.units=4
    doc.modelspace().add_line((0,0),(1234,0));doc.saveas(path,fmt=format)
    raw=path.read_bytes()
    other=ezdxf.new();other.units=6;other.modelspace().add_line((0,0),(9999,0));other.saveas(path)
    value=facts(path,raw)
    assert value['units']==4 and value['entities'][0]['dxf']['end']==[1234,0,0]


def test_snapshot_preserves_legacy_chinese_dxf_encoding(tmp_path):
    path=tmp_path/'legacy.dxf';doc=ezdxf.new('R2000');doc.units=4;doc.encoding='gbk'
    doc.modelspace().add_text('客户中文标注');doc.saveas(path)
    value=facts(path)
    assert value['units']==4 and value['entities'][0]['dxf']['text']=='客户中文标注'


def test_effective_dimension_override_and_real_cached_display_are_not_confused_with_base_style(tmp_path):
    path=tmp_path/'dimension.dxf';doc=ezdxf.new();doc.units=4
    doc.dimstyles.new('BASE100',dxfattribs={'dimlfac':100})
    dim=doc.modelspace().add_linear_dim(base=(0,-100),p1=(0,0),p2=(1000,0),dimstyle='BASE100',override={'dimlfac':1})
    dim.render();doc.saveas(path)
    row=facts(path)['entities'][0]
    assert row['native_measurement']==1000
    assert row['dimension_style']['dimlfac']==100
    assert row['entity_dimstyle_overrides']['dimlfac']==1
    assert row['effective_dimension_style']['dimlfac']==1
    assert row['cached_display']['block_exists']
    assert row['cached_display']['texts'][0]['plain_text']=='1000'


def test_pdf_painted_widths_follow_form_ctm_extgstate_and_ignore_idle_w(tmp_path):
    path=tmp_path/'actual.pdf';writer=PdfWriter();page=writer.add_blank_page(width=300,height=200)
    gs=DictionaryObject({NameObject('/LW'):FloatObject(.25*72/25.4/6),NameObject('/CA'):FloatObject(1)})
    form=DecodedStreamObject();form.set_data(b'/GS gs 0 0 m 10 0 l S 99 w')
    form.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Form'),
        NameObject('/BBox'):ArrayObject([FloatObject(v) for v in [0,0,100,100]]),
        NameObject('/Matrix'):ArrayObject([FloatObject(v) for v in [3,0,0,3,0,0]]),
        NameObject('/Resources'):DictionaryObject({NameObject('/ExtGState'):DictionaryObject({NameObject('/GS'):gs})})})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/XObject'):DictionaryObject({NameObject('/Fm'):writer._add_object(form)})})
    stream=DecodedStreamObject();stream.set_data(b'q 2 0 0 2 10 20 cm /Fm Do Q 88 w')
    page[NameObject('/Contents')]=writer._add_object(stream)
    with path.open('wb') as target:writer.write(target)
    row=facts(path)['pages'][0]
    assert len(row['painted_strokes'])==1
    assert row['painted_strokes'][0]['physical_width_mm']==pytest.approx(.25,abs=1e-6)
    native=row['vector_paths'][0]
    assert native['object_path']=='0.0' and native['stroke_enabled']
    points=native['paths'][0]
    assert points['start_mm']==pytest.approx([10*25.4/72,20*25.4/72],abs=1e-6)
    assert points['segments'][0]['points_mm'][0]==pytest.approx([70*25.4/72,20*25.4/72],abs=1e-5)


def test_offline_preview_does_not_follow_external_image_dependencies(tmp_path,monkeypatch):
    path=tmp_path/'image-reference.dxf';doc=ezdxf.new()
    image=doc.add_image_def(filename=str(tmp_path/'not-an-authorized-source.png'),size_in_pixel=(30,20))
    doc.modelspace().add_image(image,insert=(0,0),size_in_units=(100,100));doc.saveas(path)
    output=tmp_path/'review';output.mkdir()
    from ezdxf.addons.drawing import matplotlib
    monkeypatch.setattr(matplotlib,'qsave',lambda *_args,**_kwargs:pytest.fail('Renderer must not follow the external image path'))
    with pytest.raises(ValueError,match='DXF_EXTERNAL_DEPENDENCY'):_previews({'native':path},output)


@pytest.mark.parametrize('name',['../outside.txt','P01.dxf','Z:/outside/secret','artifact:missing','source:0/../../outside'])
def test_no_arbitrary_path_or_unknown_file_id(tmp_path,name):
    packet,output,lock_path,_=sample(tmp_path);evidence=Evidence(packet,lock_path,output)
    with pytest.raises(ValueError,match='Unknown authorized'):evidence.read(name)
    assert not evidence.audit.read_text(encoding='utf8')


@pytest.mark.parametrize('kind',['original','packet','lock','preview'])
def test_hashes_are_rechecked_on_every_operation(tmp_path,kind):
    packet,output,lock_path,lock=sample(tmp_path);evidence=Evidence(packet,lock_path,output)
    evidence.read('artifact:native')
    target={'original':tmp_path/'P01.dxf','packet':packet,'lock':lock_path,
            'preview':Path(lock['files'][1]['previews'][0]['path'])}[kind]
    target.write_bytes(target.read_bytes()+b'changed')
    with pytest.raises(ValueError):
        evidence.view('artifact:native',0) if kind=='preview' else evidence.read('artifact:native')


def test_lock_cannot_add_hidden_files_or_replace_original_source_identity(tmp_path):
    packet,output,lock_path,lock=sample(tmp_path)
    other=tmp_path/'producer-report.json';other.write_text('{"pass":true}',encoding='utf8')
    lock['files'][0].update(path=str(other),sha256=sha(other))
    lock_path.write_text(json.dumps(lock),encoding='utf8')
    with pytest.raises(ValueError,match='original source identity'):Evidence(packet,lock_path,output)
    assert not (output/'evidence-access.jsonl').exists()


def test_preview_cannot_read_a_file_outside_owned_source_or_output(tmp_path):
    packet,output,lock_path,lock=sample(tmp_path)
    outside=tmp_path/'outside.png';Image.new('RGB',(10,10)).save(outside)
    lock['files'][1]['previews'][0].update(path=str(outside),sha256=sha(outside))
    lock_path.write_text(json.dumps(lock),encoding='utf8')
    evidence=Evidence(packet,lock_path,output)
    with pytest.raises(ValueError,match='escaped'):evidence.view('artifact:native',0)


@pytest.mark.asyncio
async def test_actual_stdio_mcp_has_only_id_scoped_reads_and_real_images(tmp_path):
    packet,output,lock_path,lock=sample(tmp_path)
    before={p:sha(p) for p in tmp_path.iterdir() if p.is_file()}
    params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'scripts/review_evidence_server.py'),
        '--packet',str(packet),'--lock',str(lock_path),'--output',str(output)])
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=10)) as session:
            await session.initialize()
            tools=(await session.list_tools()).tools
            assert {t.name for t in tools}=={'review_inventory','review_read','review_view'}
            assert all(t.annotations.readOnlyHint and not t.annotations.destructiveHint for t in tools)
            assert all('path' not in t.inputSchema.get('properties',{}) for t in tools)
            inventory=await session.call_tool('review_inventory',{})
            assert not inventory.isError
            for row in lock['files']:
                response=await session.call_tool('review_read',{'file_id':row['file_id']})
                assert not response.isError
                value=json.loads(response.content[0].text)
                assert value['source_sha256']==row['sha256']
                for index,preview in enumerate(row['previews']):
                    response=await session.call_tool('review_view',{'file_id':row['file_id'],'preview_index':index})
                    assert not response.isError
                    assert response.content[1].type=='image'
                    assert json.loads(response.content[0].text)['preview']['sha256']==preview['sha256']
            for args in [{'path':str(tmp_path/'P01.dxf')},{'file_id':'../not-allowed'}]:
                response=await session.call_tool('review_read',args)
                assert response.isError
            response=await session.call_tool('execute_command',{'command':'echo forbidden'})
            assert response.isError
    assert all(sha(p)==value for p,value in before.items())
    events=[json.loads(line) for line in (output/'evidence-access.jsonl').read_text(encoding='utf8').splitlines()]
    assert len(events)==len(lock['files'])+sum(len(r['previews']) for r in lock['files'])
