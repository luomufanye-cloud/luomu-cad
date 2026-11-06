"""Explicit text-style and short extension-line settings for millimetre drawings."""
import math
from pathlib import Path


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
