import importlib.util
from pathlib import Path
import ezdxf
import pytest
from luomu_cad.annotations import short_extensions,configure_cjk_style,text_style_findings
from luomu_cad.qa import prepare_chinese_font


@pytest.mark.parametrize('pen',[9,13,18,35,50])
def test_selected_dimension_pen_reaches_native_cache_and_actual_pdf(tmp_path,pen):
    from io import BytesIO
    from pypdf import PdfReader
    from luomu_cad.annotations import render_dimension,dimension_stroke_findings
    from luomu_cad.pdf_export import render_pdf
    from luomu_cad.delivery import _painted_widths
    doc=ezdxf.new('R2018',setup=True);doc.units=4
    doc.layers.get('0').dxf.lineweight=25
    doc.layers.new('SELECTED-DIM',dxfattribs={'lineweight':pen})
    dim=doc.modelspace().add_linear_dim(base=(0,-100),p1=(0,0),p2=(1000,0),
        dxfattribs={'layer':'SELECTED-DIM'},override={'dimtxt':20,'dimasz':15})
    assert render_dimension(dim)=={'dimlwd':pen,'dimlwe':pen}
    source=tmp_path/'profile.dxf';doc.saveas(source);saved=ezdxf.readfile(source)
    e=next(iter(saved.modelspace().query('DIMENSION')))
    assert e.override().get('dimlwd')==pen and e.override().get('dimlwe')==pen
    lines=list(saved.blocks.get(e.dxf.geometry).query('LINE'))
    assert len(lines)==3 and all(line.dxf.lineweight==pen for line in lines)
    spec={'layers':{'SELECTED-DIM':{'lineweight_mm':[pen/100,pen/100]}}}
    assert not dimension_stroke_findings(saved,spec)['errors']
    data,_=render_pdf(source,[297,210],[-100,-250,1100,250],5)
    reader=PdfReader(BytesIO(data));widths=_painted_widths(reader.pages[0],reader,1)
    assert len(widths)==3 and all(abs(width-pen/100)<1e-6 for width in widths)
    assert saved.layers.get('0').dxf.lineweight==25


def test_legacy_pdf_stroke_leak_is_rejected_after_correct_instance_adapter(tmp_path,monkeypatch):
    from io import BytesIO
    from pypdf import PdfReader
    from luomu_cad.annotations import dimension_stroke_findings
    from luomu_cad.delivery import _painted_widths
    from luomu_cad.pdf_export import render_pdf
    doc=ezdxf.new('R2018',setup=True);doc.units=4;doc.layers.get('0').dxf.lineweight=25
    doc.layers.new('DIM',dxfattribs={'lineweight':13})
    dim=doc.modelspace().add_linear_dim(base=(0,-100),p1=(0,0),p2=(1000,0),
        dxfattribs={'layer':'DIM'},override={'dimtxt':20,'dimasz':15});dim.render()
    source=tmp_path/'r1-leak.dxf';doc.saveas(source)
    spec={'layers':{'DIM':{'lineweight_mm':[.13,.13]}}}
    findings=dimension_stroke_findings(ezdxf.readfile(source),spec)
    assert not findings['errors']  # legal inheritance; the old PDF adapter was wrong
    import luomu_cad.pdf_export as export
    from ezdxf.addons.drawing import Frontend
    with monkeypatch.context() as legacy:
        legacy.setattr(export,'_dimension_frontend',lambda context,backend,config:Frontend(context,backend,config=config))
        data,_=render_pdf(source,[297,210],[-100,-250,1100,250],5)
    reader=PdfReader(BytesIO(data));widths=_painted_widths(reader.pages[0],reader,1)
    assert len(widths)==3 and all(abs(width-.25)<1e-6 for width in widths)
    old=tmp_path/'legacy.pdf';old.write_bytes(data)
    from luomu_cad.delivery import _pdf_correspondence
    result=_pdf_correspondence(old,source,{'window_mm':[-100,-250,1100,250],'scale':5,'margin_mm':10},
        {'page_count':1,'paper_mm':[297,210]})
    assert not result['passed'] and result['painted_stroke_correspondence']['different_segments']==3


@pytest.mark.parametrize('raw',[-1,-2,-3])
def test_document_selected_legal_inherited_pens_are_measured(tmp_path,raw):
    from io import BytesIO
    from pypdf import PdfReader
    from luomu_cad.annotations import dimension_stroke_findings
    from luomu_cad.delivery import _painted_widths
    from luomu_cad.pdf_export import render_pdf
    doc=ezdxf.new('R2018',setup=True);doc.units=4
    doc.layers.get('0').dxf.lineweight=25;doc.layers.new('DIM',dxfattribs={'lineweight':35})
    dim=doc.modelspace().add_linear_dim(base=(0,-100),p1=(0,0),p2=(1000,0),
        dxfattribs={'layer':'DIM'},override={'dimtxt':20,'dimasz':15,'dimlwd':raw,'dimlwe':raw});dim.render()
    source=tmp_path/'legal.dxf';doc.saveas(source)
    expected=.25 if raw==-3 else .35
    result=dimension_stroke_findings(doc,{'layers':{'DIM':{'lineweight_mm':[expected,expected]}}})
    assert not result['errors']
    data,_=render_pdf(source,[297,210],[-100,-250,1100,250],5)
    reader=PdfReader(BytesIO(data));widths=_painted_widths(reader.pages[0],reader,1)
    assert len(widths)==3 and all(abs(value-expected)<1e-6 for value in widths)

def checker():
    spec=importlib.util.spec_from_file_location('annotation_check',Path(__file__).parents[1]/'scripts/check_annotations.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod.check

def test_real_unicode_missing_metadata_is_not_display_proof(tmp_path):
    doc=ezdxf.new();s=doc.styles.new('CJK',dxfattribs={'font':'simsun.ttc'})
    doc.modelspace().add_text('客厅 6.06×4.16 25.2㎡',dxfattribs={'style':'CJK'})
    assert text_style_findings(doc)[0]['kind']=='cjk_typeface_missing'
    s.set_extended_font_data('SimSun');assert not text_style_findings(doc)
    doc.modelspace().add_text('?? \ufffd');assert text_style_findings(doc)[0]['kind']=='suspect_text_loss'

def test_short_lines_preserve_measurement_and_saved_block(tmp_path):
    doc=ezdxf.new('R2018');m=doc.modelspace()
    d=m.add_aligned_dim((0,0),(10500,0),distance=-4050,override=short_extensions(100));d.render()
    p=tmp_path/'short.dxf';doc.saveas(p);saved=ezdxf.readfile(p);e=next(iter(saved.modelspace().query('DIMENSION')))
    assert e.get_measurement()==10500
    assert tuple(e.dxf.defpoint2)==(0,0,0) and tuple(e.dxf.defpoint3)==(10500,0,0)
    vertical=[x for x in saved.blocks[e.dxf.geometry].query('LINE') if abs(x.dxf.start.x-x.dxf.end.x)<1e-6]
    assert len(vertical)==2
    assert all(abs(x.dxf.start.y-x.dxf.end.y)==pytest.approx(400) for x in vertical)
    assert checker()(p,300,150)['ok']
    o=e.override();o['dimfxlon']=0;o.commit();saved.saveas(p)
    assert not checker()(p,300,150)['ok']

@pytest.mark.parametrize('value',[0,-1,True,float('nan'),float('inf')])
def test_invalid_scale(value):
    with pytest.raises(ValueError):short_extensions(value)

def test_configure_only_target_style_and_preserve_units(tmp_path):
    doc=ezdxf.new();doc.units=6;doc.styles.new('OTHER',dxfattribs={'font':'txt.shx'})
    doc.styles.new('LUOMU',dxfattribs={'font':'msyh.ttc'})
    p=tmp_path/'styles.dxf';doc.saveas(p);result=prepare_chinese_font(p);d=ezdxf.readfile(p)
    assert d.units==6 and d.styles.get('OTHER').dxf.font=='txt.shx'
    if result['available']:
        assert d.styles.get('LUOMU').get_extended_font_data()[0]
        assert '/' not in d.styles.get('LUOMU').dxf.font
    assert not result['native_display_verified']

def test_missing_font_does_not_claim_success(tmp_path):
    doc=ezdxf.new();assert not configure_cjk_style(doc,'CJK',tmp_path/'absent.ttf')['available']
    assert 'CJK' not in doc.styles

def test_numeric_override_cannot_hide_scaled_measurement(tmp_path):
    from luomu_cad.qa import audit_dxf
    doc=ezdxf.new();doc.units=4
    d=doc.modelspace().add_aligned_dim((0,0),(3840,0),-700,override={'dimlfac':100})
    d.dimension.dxf.text='3840';d.render();p=tmp_path/'false-label.dxf';doc.saveas(p)
    assert any(f['kind']=='dimension_override_mismatch' for f in audit_dxf(p)['findings'])
