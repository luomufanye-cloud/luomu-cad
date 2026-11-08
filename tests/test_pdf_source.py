"""Original PDF fixtures: measured extraction, not a copy of project drawings."""
import math
from pathlib import Path

import ezdxf
import pytest
from matplotlib.font_manager import FontProperties, findfont

from luomu_cad.pdf_source import extract_pdf, calibration_scale
from luomu_cad.reference_build import build
from luomu_cad.reference_presentation import font_ink_bounds


def write_pdf(path, content, extra_resources=b'', extra_objects=(), page_entries=b'', font_object=None):
    """Tiny original PDF writer for public tests, with one Helvetica font."""
    if isinstance(content, str):content=content.encode('ascii')
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',
             b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
             b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] '+page_entries+b' /Resources << /Font << /F1 4 0 R >> '+extra_resources+b' >> /Contents 5 0 R >>',
             font_object or b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
             b'<< /Length '+str(len(content)).encode()+b' >>\nstream\n'+content+b'\nendstream',*extra_objects]
    data=b'%PDF-1.7\n'; offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(data));data+=str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    start=len(data)
    data+=b'xref\n0 '+str(len(objects)+1).encode()+b'\n0000000000 65535 f \n'
    data+=b''.join(f'{offset:010} 00000 n \n'.encode() for offset in offsets[1:])
    data+=b'trailer\n<< /Size '+str(len(objects)+1).encode()+b' /Root 1 0 R >>\nstartxref\n'+str(start).encode()+b'\n%%EOF'
    Path(path).write_bytes(data)
    return Path(path)


def calibration():
    return {'source_points':[[20,20],[100,20]],'distance_mm':800,
            'check_points':[[20,20],[20,120]],'check_distance_mm':1000,'tolerance_mm':.01}


@pytest.fixture
def font():return Path(findfont(FontProperties(family='DejaVu Sans'),fallback_to_default=False))


def embedded_test_font():
    """Original glyph outlines with known ink bounds, independent of system fonts."""
    from io import BytesIO
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(['.notdef', 'A', 'b', 'g'])
    builder.setupCharacterMap({65: 'A', 98: 'b', 103: 'g'})
    glyphs = {}
    for name, bounds in [('.notdef', (0, 0, 500, 700)), ('A', (0, 0, 668, 716)),
                         ('b', (0, 0, 500, 700)), ('g', (0, -200, 500, 500))]:
        left, bottom, right, top = bounds
        pen = TTGlyphPen(None)
        pen.moveTo((left, bottom))
        pen.lineTo((right, bottom))
        pen.lineTo((right, top))
        pen.lineTo((left, top))
        pen.closePath()
        glyphs[name] = pen.glyph()
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({name: (700, 0) for name in glyphs})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({'familyName': 'LuomuPDFTest', 'styleName': 'Regular',
                            'psName': 'LuomuPDFTest', 'fullName': 'LuomuPDFTest'})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    buffer = BytesIO()
    builder.save(buffer)
    data = buffer.getvalue()
    font_object = (b'<< /Type /Font /Subtype /TrueType /BaseFont /LuomuPDFTest '
                   b'/FirstChar 65 /LastChar 103 /Widths [' + b'700 ' * 39 +
                   b'] /Encoding /WinAnsiEncoding /FontDescriptor 6 0 R >>')
    descriptor = (b'<< /Type /FontDescriptor /FontName /LuomuPDFTest /Flags 32 '
                  b'/FontBBox [0 -200 668 716] /ItalicAngle 0 /Ascent 800 /Descent -200 '
                  b'/CapHeight 716 /StemV 80 /FontFile2 7 0 R >>')
    stream = (b'<< /Length ' + str(len(data)).encode() + b' /Length1 ' +
              str(len(data)).encode() + b' >>\nstream\n' + data + b'\nendstream')
    return {'font_object': font_object, 'extra_objects': (descriptor, stream)}


def test_pdf_vectors_preserve_control_points_holes_and_paint_order(tmp_path):
    source=write_pdf(tmp_path/'original.pdf',
        '0.8 0.8 0.8 rg 20 20 100 100 re 40 40 60 60 re f*\n'
        '0.1 0.2 0.3 RG 0 w 20 150 m 50 190 80 110 110 150 c S\n'
        '0.25 w 20 10 m 100 10 l S')
    before=source.read_bytes(); result=extract_pdf(source,calibration=calibration())
    assert result['ok'] and result['inventory']['extraction_complete']
    assert source.read_bytes()==before
    doc,mapping=build(result['inventory']); path=tmp_path/'saved.dxf';doc.saveas(path)
    doc=ezdxf.readfile(path); model=doc.modelspace()
    assert [e.dxftype() for e in model]==['HATCH','SPLINE','LINE']
    hatch=model[0];assert len(hatch.paths)==2
    assert [bool(p.path_type_flags & 1) for p in hatch.paths]==[True,False]
    spline=model[1];assert spline.dxf.degree==3
    assert all(tuple(a)==pytest.approx(b) for a,b in zip(spline.control_points,[(200,1500,0),(500,1900,0),(800,1100,0),(1100,1500,0)]))
    assert list(spline.knots)==[0,0,0,0,1,1,1,1]
    assert spline.dxf.lineweight==0 and model[2].dxf.lineweight==9
    assert tuple(spline.rgb)==(26,51,77)
    assert len(mapping)==3 and not result['complete_redraw_accepted']


def test_text_rotation_tj_spacing_and_actual_ink_bounds(tmp_path,font):
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    from redraw_delivery import audit_reference
    embedded = embedded_test_font()
    source=write_pdf(tmp_path/'text.pdf',
        'BT /F1 12 Tf .8660254 .5 -.5 .8660254 100 100 Tm [(A) 200 (b) -300 (g)] TJ ET', **embedded)
    result=extract_pdf(source,calibration=calibration(),font_map={'LuomuPDFTest':str(font)})
    assert result['ok'];text=[o['expected'] for o in result['inventory']['objects']]
    doc,mapping=build(result['inventory']);target=tmp_path/'text.dxf';doc.saveas(target)
    assert audit_reference(target,result['inventory'],mapping,source)['checks_passed']
    assert ''.join(v['text'] for v in text)=='Abg'
    assert all(v['rotation']==pytest.approx(30,abs=.00001) for v in text)
    # Independently measured PDF glyph A ink is 8.016 x 8.592 pt at 12 pt em.
    box=font_ink_bounds('A',font);a=text[0]
    assert a['height']*(box[3]-box[1])==pytest.approx(85.92,abs=.001)
    assert a['height']*a['width']*(box[2]-box[0])==pytest.approx(80.16,abs=.001)
    assert a['height']!=pytest.approx(120) # em size is not glyph ink height
    # TJ spacing survives as separate native TEXT entities rather than global width stretching.
    normal=write_pdf(tmp_path/'normal.pdf','BT /F1 12 Tf .8660254 .5 -.5 .8660254 100 100 Tm (Abg) Tj ET', **embedded)
    reference=extract_pdf(normal,calibration=calibration(),font_map={'LuomuPDFTest':str(font)})
    base=[o['expected'] for o in reference['inventory']['objects']]
    assert math.dist(text[1]['at'],base[1]['at'])==pytest.approx(24,abs=.01)
    assert math.dist(text[2]['at'],base[2]['at'])==pytest.approx(12,abs=.01)


@pytest.mark.parametrize('change',[
    {'distance_mm':float('nan')},{'distance_mm':0},
    {'check_points':[[0,0],[100,0]]},{'check_distance_mm':1100},
    {'source_points':[[0,0],[0,0]]}, {'tolerance_mm':-1},
])
def test_calibration_rejects_guesses_and_conflicting_scale(change):
    value=calibration();value.update(change)
    with pytest.raises(ValueError):calibration_scale(value)
    with pytest.raises(ValueError):calibration_scale({'scale':50})


def test_font_omission_and_dash_are_explicit_failed_extraction(tmp_path):
    source=write_pdf(tmp_path/'blocked.pdf','[3 2] 0 d 20 20 m 100 20 l S BT /F1 12 Tf 1 0 0 1 10 50 Tm (A) Tj ET')
    result=extract_pdf(source,calibration=calibration())
    assert not result['ok'] and not result['inventory']['extraction_complete']
    assert {f['code'] for f in result['findings']}=={'PDF_DASH_PATTERN_REQUIRES_CONVERSION','PDF_FONT_MAPPING_REQUIRED'}
    assert not result['inventory']['objects']


def test_fill_rule_keeps_hole_and_nonzero_same_direction_solid(tmp_path):
    from shapely.geometry import Polygon
    areas=[]
    for op in ('f*','f'):
        p=write_pdf(tmp_path/(op.replace('*','alt')+'.pdf'),'20 20 100 100 re 40 40 60 60 re '+op)
        result=extract_pdf(p,calibration=calibration());assert result['ok']
        loops=result['inventory']['objects'][0]['expected']['loops']
        areas.append(Polygon([pt[:2] for pt in loops[0]['points']],[[pt[:2] for pt in l['points']] for l in loops[1:]]).area)
    assert areas==[640000,1000000]


def test_nested_form_transform_is_composed_once(tmp_path):
    content=b'0 w 0 0 m 20 0 l S'
    form=b'<< /Type /XObject /Subtype /Form /BBox [0 0 100 100] /Matrix [0 1 -1 0 100 20] /Resources << >> /Length '+str(len(content)).encode()+b' >>\nstream\n'+content+b'\nendstream'
    p=write_pdf(tmp_path/'form.pdf','q 2 0 0 2 10 10 cm /Fm Do Q',b'/XObject << /Fm 6 0 R >>',(form,))
    result=extract_pdf(p,calibration=calibration())
    assert result['ok'],result['findings']
    line=result['inventory']['objects'][0]['expected']
    assert line['start']==pytest.approx((2100,500,0)) and line['end']==pytest.approx((2100,900,0))


def test_clip_is_native_and_rendered_and_removal_fails_audit(tmp_path):
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    from redraw_delivery import audit_reference
    from ezdxf.xclip import XClip
    from ezdxf.addons.drawing import Frontend,RenderContext
    from ezdxf.addons.drawing.recorder import Recorder
    p=write_pdf(tmp_path/'clip.pdf','0 0 50 50 re W n 0 w 20 20 m 100 20 l S')
    result=extract_pdf(p,calibration=calibration())
    assert result['ok'] and result['inventory']['objects'][0]['kind']=='CLIPPED'
    doc,mapping=build(result['inventory']);path=tmp_path/'clipped.dxf';doc.saveas(path)
    assert audit_reference(path,result['inventory'],mapping,p)['checks_passed']
    # Inspect the actual rendering pipeline, not merely DXF dictionary presence.
    renderer=Recorder();Frontend(RenderContext(doc),renderer).draw_layout(doc.modelspace(),finalize=True)
    assert tuple(renderer.player().bbox().extmax)==pytest.approx((500,200))
    XClip(doc.modelspace()[0]).disable_clipping();doc.saveas(path)
    assert not audit_reference(path,result['inventory'],mapping,p)['checks_passed']
    p=write_pdf(tmp_path/'contained.pdf','0 0 150 150 re W n 0 w 20 20 m 100 20 l S')
    assert extract_pdf(p,calibration=calibration())['ok']


def test_crop_box_and_concave_clip_use_real_clipping(tmp_path):
    from ezdxf.addons.drawing import Frontend,RenderContext
    from ezdxf.addons.drawing.recorder import Recorder
    crop=write_pdf(tmp_path/'crop.pdf','0 w 0 80 m 290 80 l S',page_entries=b'/CropBox [50 50 150 150]')
    result=extract_pdf(crop,calibration=calibration());assert result['ok']
    doc,_=build(result['inventory']);renderer=Recorder()
    Frontend(RenderContext(doc),renderer).draw_layout(doc.modelspace(),finalize=True)
    assert tuple(renderer.player().bbox().extmin)==pytest.approx((0,300))
    assert tuple(renderer.player().bbox().extmax)==pytest.approx((1000,300))
    concave=write_pdf(tmp_path/'concave.pdf','0 0 m 120 0 l 120 120 l 80 120 l 80 50 l 40 50 l 40 120 l 0 120 l h W n 0 w 20 100 m 100 100 l S')
    result=extract_pdf(concave,calibration=calibration());assert result['ok']
    assert result['inventory']['objects'][0]['kind']=='CLIPPED'
    doc,_=build(result['inventory']);renderer=Recorder()
    Frontend(RenderContext(doc),renderer).draw_layout(doc.modelspace(),finalize=True)
    records=list(renderer.player().recordings())
    assert len(records)==2 # one source line renders as two visible intervals


def test_clipped_text_keeps_editable_glyph_and_rendered_crop(tmp_path,font):
    from ezdxf.addons.drawing import Frontend,RenderContext
    from ezdxf.addons.drawing.recorder import Recorder
    p=write_pdf(tmp_path/'text-clip.pdf','0 0 34 150 re W n BT /F1 12 Tf 1 0 0 1 30 100 Tm (A) Tj ET')
    result=extract_pdf(p,calibration=calibration(),font_map={'Helvetica':str(font)})
    assert result['ok'] and result['inventory']['objects'][0]['kind']=='CLIPPED'
    doc,_=build(result['inventory']);insert=doc.modelspace()[0]
    assert insert.dxftype()=='INSERT' and list(insert.block())[0].dxftype()=='TEXT'
    renderer=Recorder();Frontend(RenderContext(doc),renderer).draw_layout(doc.modelspace(),finalize=True)
    assert renderer.player().bbox().extmax.x <= 340.001


@pytest.mark.parametrize('state',[b'/BM /Multiply',b'/BM /Multiply /ca .5',b'/SMask << /S /Luminosity >>'])
def test_non_normal_compositing_is_not_reported_as_converted(tmp_path,state):
    p=write_pdf(tmp_path/'blend.pdf','0 0 1 rg 20 20 80 80 re f /GS gs 1 0 0 rg 60 60 80 80 re f',
                b'/ExtGState << /GS 6 0 R >>',(b'<< /Type /ExtGState '+state+b' >>',))
    result=extract_pdf(p,calibration=calibration())
    assert not result['ok'] and not result['inventory']['extraction_complete']
    assert any(f['code'] in ('PDF_BLEND_MODE_REQUIRES_CONVERSION','PDF_SOFT_MASK_REQUIRES_CONVERSION') for f in result['findings'])
    with pytest.raises(ValueError,match='PDF_EXTRACTION_INCOMPLETE'):build(result['inventory'])


def test_normal_alpha_and_indirect_resources_are_supported(tmp_path):
    p=write_pdf(tmp_path/'alpha.pdf','/GS gs 1 0 0 rg 20 20 80 80 re f',
                b'/ExtGState 6 0 R',(b'<< /GS 7 0 R >>',b'<< /Type /ExtGState /BM /Normal /ca .5 /OP false /op false >>'))
    result=extract_pdf(p,calibration=calibration());assert result['ok'],result['findings']
    assert result['inventory']['objects'][0]['presentation']['opacity']==pytest.approx(.5,abs=1/255)


def test_nondefault_caps_and_stroke_touching_clip(tmp_path):
    p=write_pdf(tmp_path/'cap.pdf','1 w 1 J 2 j 20 20 m 80 20 l 80 80 l S')
    result=extract_pdf(p,calibration=calibration())
    assert not result['ok'] and result['findings'][0]['code']=='PDF_STROKE_CAP_JOIN_REQUIRES_CONVERSION'
    p=write_pdf(tmp_path/'pen.pdf','0 0 100 100 re W n 1 w 0 20 m 0 80 l S')
    result=extract_pdf(p,calibration=calibration())
    assert result['ok'] and result['inventory']['objects'][0]['kind']=='CLIPPED'


@pytest.mark.parametrize('content, expected_kind', [
    ('1 w 1 J 1 j 20 20 m 80 20 l 80 80 l S', 'LWPOLYLINE'),
    ('0 w 1 J 0 j 20 20 m 80 20 l 80 80 l S', 'LWPOLYLINE'),
    ('1 w 1 J 1 j 20 20 m 30 40 60 40 80 20 c S', 'SPLINE'),
])
def test_round_stroke_and_hairline_miter_export_editable_geometry(tmp_path, content, expected_kind):
    source = write_pdf(tmp_path / 'round-stroke.pdf', content)
    result = extract_pdf(source, calibration=calibration())
    assert result['ok'] and result['inventory']['extraction_complete']
    document, mapping = build(result['inventory'])
    target = tmp_path / 'round-stroke.dxf'
    document.saveas(target)
    restored = ezdxf.readfile(target)
    assert len(mapping) == 1
    assert restored.entitydb[next(iter(mapping.values()))].dxftype() == expected_kind


def test_nonzero_round_cap_miter_join_stays_explicitly_unsupported(tmp_path):
    source = write_pdf(tmp_path / 'miter.pdf', '1 w 1 J 0 j 20 20 m 80 20 l 80 80 l S')
    result = extract_pdf(source, calibration=calibration())
    assert not result['ok']
    assert result['findings'][0]['code'] == 'PDF_STROKE_CAP_JOIN_REQUIRES_CONVERSION'


def test_transparent_joined_curves_are_not_silently_split(tmp_path):
    source = write_pdf(tmp_path / 'transparent-curves.pdf',
        '/GS gs 1 w 1 J 1 j 20 20 m 30 40 60 40 80 20 c 90 0 100 0 110 20 c S',
        b'/ExtGState << /GS 6 0 R >>', (b'<< /Type /ExtGState /CA .5 >>',))
    result = extract_pdf(source, calibration=calibration())
    assert not result['ok'] and not result['inventory']['extraction_complete']
    assert result['findings'][0]['code'] == 'PDF_TRANSPARENT_STROKE_JOIN_REQUIRES_CONVERSION'


def test_explicit_return_segment_and_rotated_page_are_preserved(tmp_path):
    p=write_pdf(tmp_path/'return.pdf','0 w 20 20 m 100 20 l 100 100 l 20 20 l S',page_entries=b'/Rotate 90')
    result=extract_pdf(p,calibration=calibration());assert result['ok']
    obj=result['inventory']['objects'][0]
    assert obj['kind']=='LWPOLYLINE' and not obj['expected']['closed']
    assert len(obj['expected']['points'])==4
    assert obj['expected']['points'][0]==obj['expected']['points'][-1]
    assert obj['expected']['points'][0]==[200,2800,0]
    assert result['inventory']['extraction']['view_window_mm']==[0,0,2000,3000]


def test_pdf_export_clips_actual_pen_pixels_not_only_centerline(tmp_path):
    import numpy as np
    import pypdfium2 as pdfium
    from luomu_cad.pdf_export import render_pdf
    p=write_pdf(tmp_path/'pen-clip.pdf','20 20 100 100 re W n 4 w 20 40 m 20 80 l S')
    result=extract_pdf(p,calibration=calibration());assert result['ok']
    doc,_=build(result['inventory']);target=tmp_path/'pen.dxf';doc.saveas(target)
    output,_=render_pdf(target,[300*25.4/72+1e-8,200*25.4/72+1e-8],[0,0,3000,2000],10*72/25.4,0)
    ranges=[]
    for source in (p,output):
        with pdfium.PdfDocument(source) as page:
            image=np.array(page[0].render(scale=4).to_pil())
            visible=image[500:600,50:100,:3].min(axis=2)<100
            _,xs=np.nonzero(visible);ranges.append((xs.min()+50,xs.max()+50))
    # A 4 pt pen at x=20 pt is half-clipped. The old pipeline painted x=72..87.
    assert ranges==[(80,87),(80,87)]


def test_curved_fill_is_never_flattened_or_outlined(tmp_path):
    p=write_pdf(tmp_path/'curve-fill.pdf','20 20 m 20 80 80 80 80 20 c h f')
    result=extract_pdf(p,calibration=calibration())
    assert not result['ok'] and result['findings'][0]['code']=='PDF_CURVED_FILL_REQUIRES_CONVERSION'
    assert result['inventory']['objects']==[]
