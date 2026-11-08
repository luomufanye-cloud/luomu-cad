"""Explicit text-style and short extension-line settings for millimetre drawings."""
import math
from pathlib import Path


def drawing_context(doc):
    """Shared DXF exporter context; DXF does not store AutoCAD's LWDEFAULT.

    The exporter default is .25 mm. This is never asserted to be a live CAD
    host setting: native checks independently read the actual LWDEFAULT.
    Project-selected explicit layers/pens remain authoritative.
    """
    from ezdxf.addons.drawing.properties import RenderContext
    return RenderContext(doc)


def dimension_lineweights(doc, layer, override=None, entity_lineweight=None):
    """Select concrete DIM/extension pens from this project's layer/overrides.

    No industry-wide pen is assumed. Explicit valid per-call pens are kept,
    including DXF's legal zero-width hairline declaration;
    ByLayer/ByBlock defaults are resolved before rendering, so anonymous LINEs
    cannot accidentally inherit layer 0's unrelated plotting weight.
    """
    from ezdxf.lldxf.const import VALID_DXF_LINEWEIGHTS
    if layer not in doc.layers:raise ValueError('Selected dimension layer must exist')
    default=doc.header.get('$LWDEFAULT',25)
    layer_pen=doc.layers.get(layer).dxf.lineweight
    if layer_pen==-3:layer_pen=default
    def concrete(value):
        if type(value) is not int or value<0 or value not in VALID_DXF_LINEWEIGHTS:
            raise ValueError('A concrete supported dimension pen is required')
        return value
    layer_pen=concrete(layer_pen)
    base=layer_pen if entity_lineweight in (None,-1,-2) else default if entity_lineweight==-3 else concrete(entity_lineweight)
    result={}
    for key in ('dimlwd','dimlwe'):
        value=(override or {}).get(key,base)
        value=layer_pen if value==-1 else base if value==-2 else default if value==-3 else value
        result[key]=concrete(value)
    return result


def render_dimension(dimension, layer=None):
    """Render one native DIMENSION with source-selected concrete stroke pens."""
    entity=dimension.dimension
    if layer is not None:entity.dxf.layer=layer
    pens=dimension_lineweights(entity.doc,entity.dxf.layer,dimension.dimstyle_attribs,
                              entity.dxf.get('lineweight',-1))
    dimension.update(pens)
    dimension.render()
    return pens


def dimension_stroke_findings(doc,spec):
    """Inspect DIM declarations and the actual cached LINE/ARC stroke pens.

    Resolve legal ByLayer/ByBlock against the real instance and recursively
    inspect cached geometry using the same parent-state adapter as PDF export.
    """
    context=drawing_context(doc);errors=[];measured=[]
    rules={name.casefold():rule for name,rule in spec['layers'].items()}
    budget=0
    def inspect_dimension(dimension,nested):
        handle=dimension.dxf.handle;parent=context.resolve_all(dimension);rule=rules.get(parent.layer.casefold())
        if rule is None:
            errors.append('DIMENSION_STYLE_LAYER_UNSPECIFIED:'+handle);return
        lo,hi=rule['lineweight_mm'];override=dimension.override()
        for key in ('dimlwd','dimlwe'):
            value=override.get(key)
            if value==-1:
                layer=context.layers.get(parent.layer.casefold());effective=layer.lineweight if layer is not None else None
            elif value==-2:effective=parent.lineweight
            elif value==-3:effective=context.default_lineweight()
            elif type(value) is int and value>0:effective=value/100
            else:effective=None
            if effective is None:errors.append('DIMENSION_PEN_UNSUPPORTED:'+handle+':'+key)
            elif not lo<=effective<=hi:errors.append('DIMENSION_PEN:'+handle+':'+key)
            measured.append({'dimension':handle,'property':key,'raw_pen':value,
                             'lineweight_mm':effective,'method':'actual dimension instance inheritance'})
        try:block=doc.blocks.get(dimension.dxf.geometry)
        except Exception:
            errors.append('DIMENSION_DISPLAY_MISSING:'+handle);return
        strokes=0
        def display(collection,names=()):
            nonlocal strokes,budget
            for child in collection:
                budget+=1
                if budget>100000 or len(names)>16:raise ValueError('Dimension display inspection budget exceeded')
                actual=context.resolve_all(child)
                if child.dxftype()=='INSERT':
                    inner=child.block();name=child.dxf.name
                    if inner is None or inner.block.is_xref or name in names:
                        errors.append('DIMENSION_DISPLAY_REFERENCE_UNSUPPORTED:'+handle);continue
                    context.push_state(actual)
                    try:display(inner,(*names,name))
                    finally:context.pop_state()
                elif child.dxftype() in {'LINE','ARC','CIRCLE','ELLIPSE','LWPOLYLINE'}:
                    if child.dxftype()=='LWPOLYLINE' and (child.dxf.get('const_width',0)>0 or any(a or b for a,b in child.get_points('se'))):
                        # Arrow ticks can be filled wide-polyline geometry;
                        # the PDF backend paints their area, not a pen stroke.
                        measured.append({'dimension':handle,'display_handle':child.dxf.handle,
                            'kind':'FILLED_WIDE_POLYLINE','paper_stroke':False,'nested_instance':nested or bool(names)})
                        continue
                    strokes+=1
                    row={'dimension':handle,'display_handle':child.dxf.handle,'kind':child.dxftype(),
                        'layer':actual.layer,'lineweight_mm':actual.lineweight,'method':'actual cached stroke instance inheritance',
                        'nested_instance':nested or bool(names)}
                    if child.dxftype()=='LINE':row.update(start=list(child.dxf.start),end=list(child.dxf.end))
                    measured.append(row)
                    if not lo<=actual.lineweight<=hi:errors.append('DIMENSION_DISPLAY_STROKE:'+handle+'/'+child.dxf.handle)
                    if 'linetypes' in rule and actual.linetype_name.casefold() not in {name.casefold() for name in rule['linetypes']}:
                        errors.append('DIMENSION_DISPLAY_LINETYPE:'+handle+'/'+child.dxf.handle)
        context.push_state(parent)
        try:display(block)
        finally:context.pop_state()
        if not strokes:errors.append('DIMENSION_DISPLAY_STROKES_MISSING:'+handle)
    def visit(collection,names=()):
        for entity in collection:
            if entity.dxftype()=='DIMENSION':inspect_dimension(entity,bool(names))
            elif entity.dxftype()=='INSERT':
                block=entity.block();name=entity.dxf.name
                if block is None or block.block.is_xref or name in names or len(names)>16:
                    errors.append('DIMENSION_INSTANCE_REFERENCE_UNSUPPORTED');continue
                context.push_state(context.resolve_all(entity))
                try:visit(block,(*names,name))
                finally:context.pop_state()
    visit(doc.modelspace())
    return {'errors':errors,'dimensions':measured,'plot_style_verified':False}


def short_extensions(scale, length=3.0, gap=1.5, beyond=1.0):
    """Paper-mm presentation choices, not a mandatory drafting standard.

    Keep original dimension definition points. Values are converted once to
    model units, so DIMSCALE is one; callers must position dimension chains
    outside the actual building envelope separately.
    """
    for value in (scale, length, gap, beyond):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError('Annotation lengths and scale must be finite and positive')
    return {'dimscale': 1.0, 'dimfxlon': 1, 'dimfxl': scale * length,
            'dimexo': scale * gap, 'dimexe': scale * beyond}


def configure_cjk_style(doc, name, font_path=None):
    """Set only the requested style, with font-file AND typeface metadata.

    No fonts are copied or redistributed. No text, geometry, units or other
    styles are changed. Availability/glyph coverage do not prove native display.
    """
    candidates = [Path(font_path)] if font_path else [
        Path('C:/Windows/Fonts/msyh.ttc'), Path('C:/Windows/Fonts/simhei.ttf'),
        Path('C:/Windows/Fonts/simsun.ttc')]
    font = next((p for p in candidates if p.is_file()), None)
    if font is None:
        return {'available': False, 'style': name, 'native_display_verified': False}
    from fontTools.ttLib import TTFont
    with TTFont(str(font), fontNumber=0) as face:
        family = face['name'].getDebugName(1)
        if not family:
            raise ValueError('Font has no family name')
    style = doc.styles.get(name) if name in doc.styles else doc.styles.new(name)
    style.dxf.font = font.name
    style.dxf.bigfont = ''
    style.set_extended_font_data(family)
    return {'available': True, 'font': font.name, 'family': family, 'style': name,
            'native_display_verified': False}


def text_style_findings(doc):
    """Read-only warning gate for CJK style mapping and corrupted text.

    Scan layouts and block definitions. Does not repair content from guesses,
    flatten MTEXT formatting or mistake a valid Unicode string for visible glyphs.
    """
    findings = []
    for entity in doc.entitydb.values():
        if not entity.is_alive or entity.dxftype() not in ('TEXT', 'MTEXT', 'ATTRIB', 'ATTDEF'):
            continue
        value = entity.plain_text() if entity.dxftype() == 'MTEXT' else entity.dxf.text
        if '\ufffd' in value or '??' in value:
            findings.append({'kind': 'suspect_text_loss', 'handle': entity.dxf.handle})
        if any('\u3400' <= ch <= '\u9fff' for ch in value):
            name = entity.dxf.style
            if name not in doc.styles:
                findings.append({'kind': 'missing_text_style', 'handle': entity.dxf.handle, 'style': name})
            else:
                style = doc.styles.get(name)
                if style.dxf.font.lower().endswith(('.ttf', '.ttc')) and not style.get_extended_font_data()[0]:
                    findings.append({'kind': 'cjk_typeface_missing', 'handle': entity.dxf.handle, 'style': name})
    return findings
