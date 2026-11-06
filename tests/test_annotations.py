import importlib.util
from pathlib import Path
import ezdxf
import pytest
from luomu_cad.annotations import short_extensions,configure_cjk_style,text_style_findings
from luomu_cad.qa import prepare_chinese_font

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
