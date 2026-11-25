"""Original learning sample drawings for references/industry-learning.

Every sample is drawn true size in model space (mm). The sheet frame and all
annotation sizes are paper millimetres multiplied by the drawing scale, so one
DXF shows both real geometry and the printed presentation. Samples teach
drafting conventions only; they are not engineering, manufacturing or permit
drawings, and their self-checks only inspect what the sample itself states.
"""
from __future__ import annotations

import json
import math
import re
from contextlib import contextmanager
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from .annotations import render_dimension

STYLE = 'LM-FS'      # long FangSong for Chinese text
NUMBERS = 'LM-NUM'   # GB letter/number SHX; %%c renders the diameter sign
NOTICE = 'Luomu CAD 原创学习示例，不是工程、制造或报批图纸'
DATE = '2026-11-24'
A = TextEntityAlignment
SQ3 = math.sqrt(3)

MECH_LAYERS = [('01-粗实线', 'Continuous', 50), ('02-细实线', 'Continuous', 25), ('04-细虚线', 'DASHED', 25),
               ('05-细点画线', 'CENTER', 25), ('08-尺寸', 'Continuous', 25), ('10-剖面线', 'Continuous', 25),
               ('11-文字', 'Continuous', 25), ('图框', 'Continuous', 50), ('图框-细', 'Continuous', 25)]
# Building-type sheets use the line-width group b=0.7: b / 0.5b / 0.25b.
ARCH_LAYERS = [('A-墙体', 'Continuous', 70), ('A-门窗', 'Continuous', 35), ('A-家具', 'Continuous', 18),
               ('A-轴线', 'CENTER', 18), ('A-尺寸', 'Continuous', 18), ('A-文字', 'Continuous', 18),
               ('A-符号', 'Continuous', 18), ('A-填充', 'Continuous', 13), ('图框', 'Continuous', 70),
               ('图框-细', 'Continuous', 18), ('标题栏', 'Continuous', 35)]


def _number(value):
    return f'{value:.2f}'


@contextmanager
def _fixed_metadata():
    previous = ezdxf.options.write_fixed_meta_data_for_testing
    ezdxf.options.write_fixed_meta_data_for_testing = True
    try:
        yield
    finally:
        ezdxf.options.write_fixed_meta_data_for_testing = previous


def _document(layers, scale):
    doc = ezdxf.new('R2013', setup=['linetypes'])
    doc.units = 4
    doc.header['$MEASUREMENT'] = 1
    doc.header['$LTSCALE'] = 0.5 * scale
    style = doc.styles.new(STYLE, dxfattribs={'font': 'simfang.ttf', 'width': 0.7})
    style.set_extended_font_data('FangSong')
    doc.styles.new(NUMBERS, dxfattribs={'font': 'gbenor.shx', 'bigfont': 'gbcbig.shx', 'width': 1.0})
    for name, linetype, weight in layers:
        doc.layers.add(name, color=7, linetype=linetype, lineweight=weight)
    mech = doc.dimstyles.new('LM-MECH')
    mech.dxf.dimtxsty = NUMBERS
    arch = doc.dimstyles.new('LM-ARCH')
    arch.dxf.dimtxsty = NUMBERS
    arch.set_arrows(blk=ezdxf.ARROWS.architectural_tick)
    return doc


class Sheet:
    """Paper-millimetre helpers over a true-size model space."""

    def __init__(self, doc, scale, paper_origin, kind):
        self.doc, self.msp, self.s, self.kind = doc, doc.modelspace(), scale, kind
        self.ox, self.oy = paper_origin  # model coordinates of paper (0, 0)
        self.text_layer = '11-文字' if kind == 'mech' else 'A-文字'
        self.dim_layer = '08-尺寸' if kind == 'mech' else 'A-尺寸'

    def p(self, x, y):
        return (self.ox + x * self.s, self.oy + y * self.s)

    def line(self, a, b, layer, **extra):
        return self.msp.add_line(a, b, dxfattribs={'layer': layer, **extra})

    def poly(self, points, layer, closed=False, fmt='xy', **extra):
        return self.msp.add_lwpolyline(points, format=fmt, close=closed, dxfattribs={'layer': layer, **extra})

    def rect(self, x0, y0, x1, y1, layer, **extra):
        return self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer, closed=True, **extra)

    def circle(self, center, radius, layer, **extra):
        return self.msp.add_circle(center, radius, dxfattribs={'layer': layer, **extra})

    def arc(self, center, radius, start, end, layer):
        return self.msp.add_arc(center, radius, start, end, dxfattribs={'layer': layer})

    def text(self, value, at, h=3.5, layer=None, align=A.BOTTOM_LEFT, rotation=0.0):
        entity = self.msp.add_text(value, height=h * self.s, rotation=rotation,
                                   dxfattribs={'style': STYLE, 'width': 0.7, 'layer': layer or self.text_layer})
        entity.set_placement(at, align=align)
        return entity

    def fill(self, points, layer, color=7):
        hatch = self.msp.add_hatch(color=color, dxfattribs={'layer': layer})
        hatch.paths.add_polyline_path(points, is_closed=True)
        return hatch

    def pattern(self, points, layer, name, paper_spacing, color=8):
        hatch = self.msp.add_hatch(color=color, dxfattribs={'layer': layer})
        hatch.set_pattern_fill(name, scale=paper_spacing * self.s / 3.175)
        hatch.paths.add_polyline_path(points, is_closed=True)
        return hatch

    def arrow(self, tip, direction, layer, length=3.0, width=1.0):
        dx, dy = direction
        norm = math.hypot(dx, dy)
        ux, uy = dx / norm, dy / norm
        back = (tip[0] - ux * length * self.s, tip[1] - uy * length * self.s)
        half = width / 2 * self.s
        return self.fill([tip, (back[0] - uy * half, back[1] + ux * half),
                          (back[0] + uy * half, back[1] - ux * half)], layer)

    def leader(self, points, layer, arrow=True):
        self.poly(points, layer)
        if arrow:
            self.arrow(points[-1], (points[-1][0] - points[-2][0], points[-1][1] - points[-2][1]), layer)

    def _override(self, style, post=None, extra=None):
        s = self.s
        if style == 'LM-MECH':
            values = {'dimtxt': 3.5 * s, 'dimasz': 3 * s, 'dimexe': 2 * s, 'dimexo': 0.0, 'dimgap': 0.8 * s}
        else:
            values = {'dimtxt': 3.5 * s, 'dimasz': 2.5 * s, 'dimexe': 2 * s, 'dimexo': 2 * s, 'dimgap': 1.0 * s}
        values.update({'dimtad': 1, 'dimtih': 0, 'dimtoh': 0, 'dimdec': 0, 'dimscale': 1.0, 'dimlfac': 1.0,
                       'dimclrd': 7, 'dimclre': 7, 'dimclrt': 7, 'dimtxsty': NUMBERS})
        if post:
            values['dimpost'] = post
        values.update(extra or {})
        return values

    def dim(self, p1, p2, base, angle=0.0, post=None, style=None, extra=None):
        style = style or ('LM-MECH' if self.kind == 'mech' else 'LM-ARCH')
        dimension = self.msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dimstyle=style,
                                            override=self._override(style, post, extra),
                                            dxfattribs={'layer': self.dim_layer})
        render_dimension(dimension)
        return dimension.dimension

    def radius(self, center, radius, angle, post=None):
        dimension = self.msp.add_radius_dim(center, radius=radius, angle=angle, dimstyle='LM-MECH',
                                            override=self._override('LM-MECH', post),
                                            dxfattribs={'layer': self.dim_layer})
        render_dimension(dimension)
        return dimension.dimension

    def diameter(self, center, radius, angle):
        dimension = self.msp.add_diameter_dim(center, radius=radius, angle=angle, dimstyle='LM-MECH',
                                              override=self._override('LM-MECH'),
                                              dxfattribs={'layer': self.dim_layer})
        render_dimension(dimension)
        return dimension.dimension

    def table(self, x, top, widths, height, rows, layer, h=3.0):
        """Paper-unit grid; first row is the header."""
        total = sum(widths)
        bottom = top - height * len(rows)
        self.poly([self.p(x, bottom), self.p(x + total, bottom), self.p(x + total, top), self.p(x, top)],
                  layer, closed=True)
        for i in range(1, len(rows)):
            self.line(self.p(x, top - height * i), self.p(x + total, top - height * i), layer)
        edge = x
        for width in widths[:-1]:
            edge += width
            self.line(self.p(edge, bottom), self.p(edge, top), layer)
        for r, row in enumerate(rows):
            edge = x
            for width, value in zip(widths, row):
                self.text(str(value), self.p(edge + width / 2, top - height * (r + 0.5)), h, align=A.MIDDLE_CENTER)
                edge += width

    def frame(self, title, number, scale_label, material='—', projection=False):
        thick = '图框'
        self.rect(*self.p(0, 0), *self.p(420, 297), '图框-细')
        self.rect(*self.p(25, 5), *self.p(415, 292), thick)
        x0, y0 = 235, 5
        outer = thick if self.kind == 'mech' else '标题栏'
        grid = '图框-细'
        self.rect(*self.p(x0, y0), *self.p(x0 + 180, y0 + 32), outer)
        for y in (8, 16, 24):
            self.line(self.p(x0, y0 + y), self.p(x0 + 60, y0 + y), grid)
        self.line(self.p(x0 + 60, y0 + 8), self.p(x0 + 130, y0 + 8), grid)
        self.line(self.p(x0 + 60, y0 + 16), self.p(x0 + 180, y0 + 16), grid)
        for x in (60, 130):
            self.line(self.p(x0 + x, y0), self.p(x0 + x, y0 + 32), grid)
        self.line(self.p(x0 + 14, y0), self.p(x0 + 14, y0 + 32), grid)
        for x in (95, 110):
            self.line(self.p(x0 + x, y0 + 8), self.p(x0 + x, y0 + 16), grid)
        self.line(self.p(x0 + 75, y0), self.p(x0 + 75, y0 + 16), grid)
        cells = [('日期', DATE, 4), ('审核', '—', 12), ('校核', '—', 20), ('设计', 'Luomu CAD', 28)]
        for label, value, y in cells:
            self.text(label, self.p(x0 + 7, y0 + y), 3.0, align=A.MIDDLE_CENTER)
            self.text(value, self.p(x0 + 37, y0 + y), 3.0, align=A.MIDDLE_CENTER)
        self.text(title, self.p(x0 + 95, y0 + 24), 5.0, align=A.MIDDLE_CENTER)
        for label, value, lx, vx in (('材料', material, 67.5, 85), ('比例', scale_label, 102.5, 120)):
            self.text(label, self.p(x0 + lx, y0 + 12), 3.0, align=A.MIDDLE_CENTER)
            self.text(value, self.p(x0 + vx, y0 + 12), 3.0, align=A.MIDDLE_CENTER)
        self.text('图号', self.p(x0 + 67.5, y0 + 4), 3.0, align=A.MIDDLE_CENTER)
        self.text(number, self.p(x0 + 102.5, y0 + 4), 3.0, align=A.MIDDLE_CENTER)
        self.text('Luomu CAD', self.p(x0 + 155, y0 + 27), 3.5, align=A.MIDDLE_CENTER)
        self.text('学习示例', self.p(x0 + 155, y0 + 20), 3.5, align=A.MIDDLE_CENTER)
        if projection:
            self.first_angle_symbol(x0 + 143, y0 + 8)
        else:
            self.text('共1张 第1张', self.p(x0 + 155, y0 + 8), 3.0, align=A.MIDDLE_CENTER)
        self.text('简化标题栏，格式以GB/T 10609.1或GB/T 50001正文为准', self.p(x0, y0 + 34), 2.5)
        self.text(NOTICE, self.p(27, 7), 2.5)

    def first_angle_symbol(self, x, y):
        """First-angle projection symbol, proportions only illustrative."""
        layer = '02-细实线' if self.kind == 'mech' else '图框-细'
        self.poly([self.p(x, y + 1.75), self.p(x + 9, y), self.p(x + 9, y + 7), self.p(x, y + 5.25)], layer, closed=True)
        self.circle(self.p(x + 18, y + 3.5), 3.5 * self.s, layer)
        self.circle(self.p(x + 18, y + 3.5), 1.75 * self.s, layer)
        center = '05-细点画线' if self.kind == 'mech' else 'A-轴线'
        self.line(self.p(x - 1, y + 3.5), self.p(x + 10, y + 3.5), center)
        self.line(self.p(x + 13.5, y + 3.5), self.p(x + 22.5, y + 3.5), center)
        self.line(self.p(x + 18, y - 1), self.p(x + 18, y + 8), center)

    def north(self, x, y):
        r = 12 * self.s
        c = self.p(x, y)
        self.circle(c, r, 'A-符号')
        self.fill([(c[0], c[1] + r), (c[0] - 1.5 * self.s, c[1] - r), (c[0] + 1.5 * self.s, c[1] - r)], 'A-符号')
        self.text('北', self.p(x, y + 14), 5.0, align=A.BOTTOM_CENTER)

    def title(self, x, y, name, scale_label):
        """Drawing name with scale and underline; x, y are paper millimetres."""
        half = len(name) * 7 * 0.7 / 2
        self.text(name, self.p(x, y), 7.0, align=A.BOTTOM_CENTER)
        self.text(scale_label, self.p(x + half + 7, y), 5.0)
        self.line(self.p(x - half, y - 1.5), self.p(x + half, y - 1.5),
                  '01-粗实线' if self.kind == 'mech' else 'A-墙体')


def _save(doc, path):
    """Save with reproducible bytes.

    ezdxf stamps the write time into its metadata and emits CLASS records in set
    order. Pin the stamp and sort the CLASS records; no proxy objects exist, so
    class order carries no meaning here.
    """
    with _fixed_metadata():
        doc.saveas(path)
    text = Path(path).read_text(encoding='utf-8')
    text = re.sub(r'(\d+\.\d+\.\d+\S*) @ \d{4}-\d{2}-\d{2}T[0-9:.+-]+', r'\1 @ ' + DATE + 'T00:00:00+00:00', text)
    head = 'SECTION\n  2\nCLASSES\n'
    start = text.find(head)
    if start >= 0:
        body_start = start + len(head)
        end = text.find('  0\nENDSEC\n', body_start)
        records = ['  0\nCLASS\n' + chunk for chunk in text[body_start:end].split('  0\nCLASS\n') if chunk]
        text = text[:body_start] + ''.join(sorted(records)) + text[end:]
    Path(path).write_text(text, encoding='utf-8', newline='\n')


def canonical(path):
    """Saved DXF text with line endings normalised (git may check out CRLF)."""
    return Path(path).read_text(encoding='utf-8').replace('\r\n', '\n')


def _check(item, ok, basis):
    return {'item': item, 'result': 'pass' if ok else 'fail', 'basis': basis}


def _measurements(doc):
    return sorted(round(float(e.get_measurement()), 3) for e in doc.modelspace().query('DIMENSION'))


# ---------------------------------------------------------------- mechanical
def mechanical(path):
    s = 0.5  # 2:1 enlargement: 0.5 model mm per paper mm
    doc = _document(MECH_LAYERS, s)
    sh = Sheet(doc, s, (-25.0, -100.0), 'mech')  # paper (50, 200) is the left end of the shaft axis
    thick, thin, center, hatch = '01-粗实线', '02-细实线', '05-细点画线', '10-剖面线'
    for a, b in [((1, 15), (40, 15)), ((40, 18), (60, 18)), ((60, 12), (95, 12)), ((95, 10), (119, 10)),
                 ((0, 14), (1, 15)), ((119, 10), (120, 9))]:
        sh.line(a, b, thick)
        sh.line((a[0], -a[1]), (b[0], -b[1]), thick)
    for x, half in [(0, 14), (1, 15), (40, 18), (60, 18), (95, 12), (100, 10), (119, 10), (120, 9)]:
        sh.line((x, -half), (x, half), thick)  # x=100 is the thread termination line
    sh.line((100, 8.5), (120, 8.5), thin)
    sh.line((100, -8.5), (120, -8.5), thin)
    sh.line((-2, 0), (122, 0), center)
    # keyway facing the viewer, 25 long and 8 wide
    sh.line((16, 4), (33, 4), thick)
    sh.line((16, -4), (33, -4), thick)
    sh.arc((16, 0), 4, 90, 270, thick)
    sh.arc((33, 0), 4, -90, 90, thick)
    # cutting plane A-A at x=30, projection towards +x
    for sign in (1, -1):
        sh.line((30, sign * 16), (30, sign * 18.5), thick)
        sh.line((30, sign * 18.5), (32, sign * 18.5), thin)
        sh.arrow((33.5, sign * 18.5), (1, 0), thin)
    sh.text('A', (30.3, 19.2), align=A.BOTTOM_LEFT)
    sh.text('A', (30.3, -19.0), align=A.TOP_LEFT)
    # removed section A-A
    cx = 150.0
    edge = math.sqrt(15 ** 2 - 4 ** 2)
    start = math.degrees(math.asin(4 / 15))
    sh.arc((cx, 0), 15, start, 360 - start, thick)
    for a, b in [((cx + edge, 4), (cx + 11, 4)), ((cx + 11, 4), (cx + 11, -4)), ((cx + 11, -4), (cx + edge, -4))]:
        sh.line(a, b, thick)
    bulge = math.tan(math.radians(360 - 2 * start) / 4)
    section = sh.msp.add_hatch(color=7, dxfattribs={'layer': hatch})
    section.set_pattern_fill('ANSI31', scale=0.5)
    section.paths.add_polyline_path([(cx + edge, 4, bulge), (cx + edge, -4, 0), (cx + 11, -4, 0), (cx + 11, 4, 0)],
                                    is_closed=True)
    sh.line((cx - 17, 0), (cx + 17, 0), center)
    sh.line((cx, -17), (cx, 17), center)
    sh.text('A-A', (cx, 19), align=A.BOTTOM_CENTER)
    # dimensions (true values; post-fixes carry the code only)
    sh.dim((6, 15), (6, -15), (6, 0), 90, '%%c<>k6')
    sh.dim((50, 18), (50, -18), (50, 0), 90, '%%c<>')
    sh.dim((78, 12), (78, -12), (78, 0), 90, '%%c<>')
    sh.dim((110, 10), (110, -10), (110, 0), 90, 'M<>')
    sh.dim((0, 14), (12, 0), (0, 25))
    sh.dim((12, 0), (37, 0), (0, 25))
    sh.dim((100, 10), (120, 9), (0, 25))
    sh.dim((0, -14), (40, -18), (0, -25))
    sh.dim((40, -18), (60, -18), (0, -25))
    sh.dim((95, -12), (120, -9), (0, -25))
    sh.dim((0, -14), (120, -9), (0, -31))
    sh.dim((cx + edge, 4), (cx + edge, -4), (cx + 20, 0), 90, '<>N9')
    sh.dim((cx - 15, 0), (cx + 11, 0), (0, -20))
    # surface texture Ra 1.6 on the fitted diameter (material removal required)
    px, py, h1, h2 = 18.5, 15.0, 5 * s, 10.5 * s
    sh.poly([(px - h1 / SQ3, py + h1), (px, py), (px + h2 / SQ3, py + h2), (px + h2 / SQ3 + 12 * s, py + h2)], thin)
    sh.line((px - h1 / SQ3, py + h1), (px + h1 / SQ3, py + h1), thin)
    sh.text('Ra 1.6', (px + h2 / SQ3 + 0.4, py + h2 - 0.5), align=A.TOP_LEFT)
    # datum A on the axis of the fitted diameter, aligned with its dimension line
    sh.fill([(5.125, 15), (6.875, 15), (6, 16.5)], thin)
    sh.line((6, 16.5), (6, 17.5), thin)
    sh.rect(4.25, 17.5, 7.75, 21.0, thin)
    sh.text('A', (6, 19.25), align=A.MIDDLE_CENTER)
    # circular run-out of the dia.36 surface relative to A
    fx, fy = 44.0, 22.0
    for x0, x1 in ((0, 3.5), (3.5, 9.5), (9.5, 13.0)):
        sh.rect(fx + x0, fy, fx + x1, fy + 3.5, thin)
    sh.line((fx + 0.7, fy + 0.7), (fx + 2.5, fy + 2.5), thin)
    sh.arrow((fx + 2.9, fy + 2.9), (1, 1), thin, length=1.6, width=0.8)
    sh.text('0.02', (fx + 6.5, fy + 1.75), align=A.MIDDLE_CENTER)
    sh.text('A', (fx + 11.25, fy + 1.75), align=A.MIDDLE_CENTER)
    sh.line((fx + 1.75, fy), (fx + 1.75, 19.5), thin)
    sh.arrow((fx + 1.75, 18), (0, -1), thin)
    # majority surface texture near the title block: Ra 6.3 (basic symbol)
    mx, my = sh.p(318, 47)
    sh.poly([(mx - h1 / SQ3, my + h1), (mx, my), (mx + h2 / SQ3, my + h2), (mx + h2 / SQ3 + 12 * s, my + h2)], thin)
    sh.line((mx - h1 / SQ3, my + h1), (mx + h1 / SQ3, my + h1), thin)
    sh.text('Ra 6.3', (mx + h2 / SQ3 + 0.4, my + h2 - 0.5), align=A.TOP_LEFT)
    bx, by = sh.p(347, 47)
    sh.text('(', sh.p(340, 45.5), 10.0)
    sh.poly([(bx - h1 / SQ3, by + h1), (bx, by), (bx + h2 / SQ3, by + h2)], thin)
    sh.text(')', sh.p(354, 45.5), 10.0)
    notes = ['技术要求', '1. 未注线性尺寸公差按GB/T 1804-m。', '2. 未注倒角C1。', '3. 调质处理220～250HBW（示意）。',
             '4. 键槽宽8N9、槽底尺寸26，未注公差的键槽尺寸按设计确定。']
    for i, line in enumerate(notes):
        sh.text(line, sh.p(40 if i else 60, 128 - i * 7), 5.0 if i == 0 else 3.5)
    sh.frame('阶梯轴', 'LM-LS-01', '2:1', '45', projection=True)
    _save(doc, path)
    measured = _measurements(ezdxf.readfile(path))
    expected = sorted([30.0, 36.0, 24.0, 20.0, 12.0, 25.0, 20.0, 40.0, 20.0, 25.0, 120.0, 8.0, 26.0])
    chain = 40 + 20 + 25
    return {
        'id': 'mechanical-shaft', 'file': Path(path).name, 'route': 'mechanical',
        'learning_note': 'references/industry-learning/mechanical.md', 'title': '阶梯轴零件图', 'scale': '2:1',
        'demonstrates': ['A3留装订边图框与简化标题栏', '2:1放大比例：模型按实际尺寸，尺寸数字为实际值',
                         '粗细两种线宽2:1，细点画线轴线超出轮廓', '键槽移出断面A-A：剖切符号、箭头、字母与45°剖面线',
                         '外螺纹M20：大径粗实线、小径细实线画入倒角、螺纹终止线', '轴段公差带代号φ30k6与键槽宽8N9',
                         '基准A与圆跳动公差框格', '表面结构Ra 1.6及标题栏附近的多数表面简化注法',
                         '长度尺寸链留开口环（φ24段35不注）', '第一角画法识别符号'],
        'standard_ids': ['drawing-sheets', 'title-block', 'drawing-scales', 'drawing-fonts', 'drawing-projection',
                         'mechanical-lines', 'mechanical-views', 'mechanical-sections', 'mechanical-hatching',
                         'mechanical-dimensions', 'mechanical-tolerance-notation', 'iso-fits', 'general-tolerances',
                         'gps-tolerances', 'surface-texture', 'mechanical-threads'],
        'self_checks': [
            _check('原生尺寸实测值与设计值一致', measured == expected, '回读DIMENSION实测值'),
            _check('长度尺寸链不封闭', chain != 120, '40+20+25≠120，φ24段为开口环'),
            _check('螺纹小径为大径的0.85倍', abs(17 / 20 - 0.85) < 1e-9, '小径线y=±8.5，大径y=±10'),
        ]}


# ---------------------------------------------------------------- product
def product(path):
    s = 1.0
    doc = _document(MECH_LAYERS, s)
    sh = Sheet(doc, s, (0.0, 0.0), 'mech')
    thick, thin, hidden, center = '01-粗实线', '02-细实线', '04-细虚线', '05-细点画线'
    W, D, H, R = 180.0, 120.0, 35.0, 8.0
    fx, fy = 50.0, 200.0      # front view origin: object x, height z
    tx, ty = 50.0, 55.0       # top view origin: object x, depth y (front edge at the bottom)
    lx = 255.0                # left view: paper x = lx + (D - y), back face next to the front view
    button = (30.0, 60.0, 10.0)   # x, y from front, diameter; protrudes 1 mm
    led = (150.0, 20.0, 3.0)      # x, z on the front face, diameter
    usb = (60.0, 72.0, 10.0, 15.0)  # back-face opening x0, x1, z0, z1
    vents = [(120.0, 150.0, 70.0 + 6 * i) for i in range(6)]
    # front view
    sh.rect(fx, fy, fx + W, fy + H, thick)
    bx0, bx1 = fx + button[0] - button[2] / 2, fx + button[0] + button[2] / 2
    sh.poly([(bx0, fy + H), (bx0, fy + H + 1), (bx1, fy + H + 1), (bx1, fy + H)], thick)
    sh.circle((fx + led[0], fy + led[1]), led[2] / 2, thick)
    sh.line((fx + led[0] - 4, fy + led[1]), (fx + led[0] + 4, fy + led[1]), center)
    sh.line((fx + led[0], fy + led[1] - 4), (fx + led[0], fy + led[1] + 4), center)
    sh.rect(fx + usb[0], fy + usb[2], fx + usb[1], fy + usb[3], hidden)
    sh.line((fx + button[0], fy + H - 3), (fx + button[0], fy + H + 4), center)
    # top view: rounded rectangle, vents, button
    k = math.tan(math.radians(90) / 4)
    x0, y0, x1, y1 = tx, ty, tx + W, ty + D
    sh.poly([(x0 + R, y0, 0), (x1 - R, y0, k), (x1, y0 + R, 0), (x1, y1 - R, k), (x1 - R, y1, 0),
             (x0 + R, y1, k), (x0, y1 - R, 0), (x0, y0 + R, k)], thick, closed=True, fmt='xyb')
    for a, b, y in vents:
        sh.poly([(tx + a + 1.5, ty + y - 1.5, 0), (tx + b - 1.5, ty + y - 1.5, 1), (tx + b - 1.5, ty + y + 1.5, 0),
                 (tx + a + 1.5, ty + y + 1.5, 1)], thick, closed=True, fmt='xyb')
    bc = (tx + button[0], ty + button[1])
    sh.circle(bc, button[2] / 2, thick)
    sh.line((bc[0] - 8, bc[1]), (bc[0] + 8, bc[1]), center)
    sh.line((bc[0], bc[1] - 8), (bc[0], bc[1] + 8), center)
    # left view
    sh.rect(lx, fy, lx + D, fy + H, thick)
    ly0, ly1 = lx + D - button[1] - button[2] / 2, lx + D - button[1] + button[2] / 2
    sh.poly([(ly0, fy + H), (ly0, fy + H + 1), (ly1, fy + H + 1), (ly1, fy + H)], thick)
    sh.line(((ly0 + ly1) / 2, fy + H - 3), ((ly0 + ly1) / 2, fy + H + 4), center)
    # dimensions
    sh.dim((fx, fy), (fx, fy + H), (40, 0), 90)
    sh.dim((fx, fy + H), (fx + led[0], fy + led[1]), (0, fy + H + 10))
    sh.dim((fx + W, fy), (fx + led[0], fy + led[1]), (fx + W + 12, 0), 90)
    sh.diameter((fx + led[0], fy + led[1]), led[2] / 2, 45)
    sh.dim((x0, y0 + R), (x1, y0 + R), (0, 45))
    sh.dim((x1 - R, y0), (x1 - R, y1), (248, 0), 90)
    sh.dim((x1 - R, y0), (tx + vents[0][1], ty + vents[0][2]), (240, 0), 90)
    sh.dim((x0, y1 - R), bc, (0, 185))
    sh.dim((x0, y1 - R), (tx + vents[0][0], ty + vents[0][2]), (0, 192))
    sh.dim((x0 + R, y0), bc, (38, 0), 90)
    sh.diameter(bc, button[2] / 2, 45)
    sh.radius((x0 + R, y1 - R), R, 135)
    sh.leader([(tx + 175, ty + 112), (tx + 158, ty + 112), (tx + 150, ty + vents[-1][2] + 1.5)], thin)
    sh.text('6×槽30×3 间距6', (tx + 150, ty + 113))
    notes = ['技术要求', '1. 材料PC+ABS，壁厚2。', '2. 外表面细蚀纹，颜色浅灰（色板由设计确认）。',
             '3. 未注圆角R0.5；拔模斜度在结构设计阶段确定。', '4. 背面USB开口12×5以细虚线示意，',
             '   位置尺寸在后视图标注（本示例未绘）。']
    for i, line in enumerate(notes):
        sh.text(line, (262 if i else 290, 175 - i * 7), 5.0 if i == 0 else 3.5)
    sh.frame('路由器外壳 外观尺寸图', 'LM-LS-02', '1:1', 'PC+ABS', projection=True)
    _save(doc, path)
    measured = _measurements(ezdxf.readfile(path))
    aligned_x = math.isclose(fx + button[0], bc[0])
    aligned_z = math.isclose(fy + H + 1, fy + H + 1)
    equal_y = math.isclose((ly0 + ly1) / 2, lx + (D - button[1]))
    return {
        'id': 'product-enclosure', 'file': Path(path).name, 'route': 'product',
        'learning_note': 'references/industry-learning/product-design.md', 'title': '路由器外壳外观尺寸图',
        'scale': '1:1',
        'demonstrates': ['第一角画法三视图：俯视图在主视图下方、左视图在右方，按投影关系配置时不标视图名称',
                         '长对正、高平齐、宽相等',
                         '俯视图与左视图中靠近主视图的一侧是物体后面', '细虚线表示背面开口（不可见轮廓）',
                         '圆角R、孔径φ、槽组的数量×尺寸注法', '小尺寸靠近图形、大尺寸在外', '材料与表面工艺写在技术要求中'],
        'standard_ids': ['drawing-projection', 'mechanical-views', 'mechanical-lines', 'mechanical-dimensions',
                         'simplified-dimensions', 'drawing-sheets', 'title-block', 'drawing-fonts'],
        'self_checks': [
            _check('按钮在主视图与俯视图x坐标一致（长对正）', aligned_x, '主视图凸起中心与俯视图圆心'),
            _check('按钮在主视图与左视图高度一致（高平齐）', aligned_z, '两视图凸起顶面z=36'),
            _check('按钮在俯视图与左视图前后位置一致（宽相等）', equal_y, '距前面60，左视图自后面量起60'),
            _check('外形尺寸180×120×35已注全', {180.0, 120.0, 35.0} <= set(measured), '回读DIMENSION实测值'),
        ]}


# ---------------------------------------------------------------- interior
def _walls(segments, openings):
    shapes = [LineString(seg).buffer(t / 2, cap_style=2, join_style=2) for seg, t in segments]
    region = unary_union(shapes)
    for x0, y0, x1, y1 in openings:
        region = region.difference(box(x0, y0, x1, y1))
    return list(region.geoms) if hasattr(region, 'geoms') else [region]


def _draw_regions(sh, regions, layer):
    for polygon in regions:
        for ring in [polygon.exterior, *polygon.interiors]:
            sh.poly([tuple(round(v, 6) for v in c) for c in list(ring.coords)[:-1]], layer, closed=True)


def _door(sh, hinge, closed_dir, open_dir, width, layer='A-门窗'):
    cx, cy = hinge
    sh.line(hinge, (cx + open_dir[0] * width, cy + open_dir[1] * width), layer)
    a0 = math.degrees(math.atan2(closed_dir[1], closed_dir[0]))
    a1 = math.degrees(math.atan2(open_dir[1], open_dir[0]))
    if (a1 - a0) % 360 > 180:
        a0, a1 = a1, a0
    sh.arc(hinge, width, a0, a1, layer)
    return Polygon([hinge, (cx + closed_dir[0] * width, cy + closed_dir[1] * width),
                    (cx + (closed_dir[0] + open_dir[0]) * width, cy + (closed_dir[1] + open_dir[1]) * width),
                    (cx + open_dir[0] * width, cy + open_dir[1] * width)])


def interior(path):
    s = 50.0
    doc = _document(ARCH_LAYERS, s)
    sh = Sheet(doc, s, (-110 * s, -160 * s), 'arch')
    W, H, T = 4200.0, 3600.0, 200.0
    door = (600.0, 1500.0)
    window = (1350.0, 2850.0)
    # extend each wall by half a thickness so the corners close
    regions = _walls([((( -T / 2, 0), (W + T / 2, 0)), T), (((W, -T / 2), (W, H + T / 2)), T),
                      (((W + T / 2, H), (-T / 2, H)), T), (((0, H + T / 2), (0, -T / 2)), T)],
                     [(door[0], -T, door[1], T), (window[0], H - T, window[1], H + T)])
    _draw_regions(sh, regions, 'A-墙体')
    for y in (H - T / 2, H - T / 6, H + T / 6, H + T / 2):
        sh.line((window[0], y), (window[1], y), 'A-门窗')
    swing = _door(sh, (door[0], T / 2), (1, 0), (0, 1), door[1] - door[0])
    furniture = {'床': box(2100, 900, W - T / 2, 2700), '床头柜1': box(W - T / 2 - 450, 450, W - T / 2, 850),
                 '床头柜2': box(W - T / 2 - 450, 2750, W - T / 2, 3150), '衣柜': box(T / 2, 1500, T / 2 + 600, 3300)}
    for name, shape in furniture.items():
        x0, y0, x1, y1 = shape.bounds
        sh.rect(x0, y0, x1, y1, 'A-家具')
    sh.rect(W - T / 2 - 500, 1000, W - T / 2 - 100, 1750, 'A-家具')
    sh.rect(W - T / 2 - 500, 1850, W - T / 2 - 100, 2600, 'A-家具')
    for y in (1900, 2400, 2900):
        sh.line((T / 2, y), (T / 2 + 600, y), 'A-家具')
    sh.text('床 1800×2000', (3000, 1800), 3.0, align=A.MIDDLE_CENTER, layer='A-家具')
    sh.text('衣柜', (T / 2 + 300, 1700), 3.0, align=A.MIDDLE_CENTER, layer='A-家具', rotation=90)
    # axes and bubbles (numbers left->right, letters bottom->top)
    bubble = 4.5 * s
    for x, label in ((0, '1'), (W, '2')):
        sh.line((x, -1500), (x, H + 600), 'A-轴线')
        sh.circle((x, -1500 - bubble), bubble, 'A-符号')
        sh.text(label, (x, -1500 - bubble), 5.0, align=A.MIDDLE_CENTER)
    for y, label in ((0, 'A'), (H, 'B')):
        sh.line((-1500, y), (W + 600, y), 'A-轴线')
        sh.circle((-1500 - bubble, y), bubble, 'A-符号')
        sh.text(label, (-1500 - bubble, y), 5.0, align=A.MIDDLE_CENTER)
    # dimensions: chains inside, totals outside
    yb = -T / 2
    sh.dim((0, yb), (door[0], yb), (0, -700))
    sh.dim((door[0], yb), (door[1], yb), (0, -700))
    sh.dim((door[1], yb), (W, yb), (0, -700))
    sh.dim((0, yb), (W, yb), (0, -1100))
    yt = H + T / 2
    sh.dim((0, yt), (window[0], yt), (0, H + 700))
    sh.dim((window[0], yt), (window[1], yt), (0, H + 700))
    sh.dim((window[1], yt), (W, yt), (0, H + 700))
    sh.dim((-T / 2, 0), (-T / 2, H), (-1100, 0), 90)
    sh.dim((W + T / 2, 0), (W + T / 2, H), (W + 700, 0), 90)
    # room name, area, finished floor level
    area = (W - T) * (H - T) / 1e6
    sh.text('卧室', (1400, 2450), 5.0, align=A.MIDDLE_CENTER)
    sh.text(f'{area:.2f}平方米', (1400, 2150), 3.5, align=A.MIDDLE_CENTER)
    ex, ey = 950.0, 1500.0
    sh.poly([(ex - 3 * s, ey + 3 * s), (ex, ey), (ex + 3 * s, ey + 3 * s)], 'A-符号')
    sh.line((ex - 3 * s, ey + 3 * s), (ex + 16 * s, ey + 3 * s), 'A-符号')
    sh.text('±0.000', (ex + 3.5 * s, ey + 3.6 * s), 3.5)
    # elevation index (A-D) and detail index 1
    ix, iy, r = 1400.0, 3000.0, 5 * s
    sh.circle((ix, iy), r, 'A-符号')
    for (dx, dy), letter in (((0, 1), 'A'), ((1, 0), 'B'), ((0, -1), 'C'), ((-1, 0), 'D')):
        tip = (ix + dx * (r + 3 * s), iy + dy * (r + 3 * s))
        sh.fill([tip, (ix + dx * r - dy * 2 * s, iy + dy * r + dx * 2 * s),
                 (ix + dx * r + dy * 2 * s, iy + dy * r - dx * 2 * s)], 'A-符号')
        sh.text(letter, (ix + dx * r * 0.55, iy + dy * r * 0.55), 2.5, align=A.MIDDLE_CENTER)
    dx_, dy_ = 1800.0, 1150.0
    sh.circle((dx_, dy_), r, 'A-符号')
    sh.line((dx_ - r, dy_), (dx_ + r, dy_), 'A-符号')
    sh.text('1', (dx_, dy_ + r / 2), 3.0, align=A.MIDDLE_CENTER)
    sh.text('—', (dx_, dy_ - r / 2), 3.0, align=A.MIDDLE_CENTER)
    sh.poly([(dx_ - r, dy_), (650, dy_), (650, 1500)], 'A-符号')
    sh.north(375, 250)
    sh.title(152, 108, '卧室平面布置图', '1:50')
    notes = ['说明', '1. 尺寸单位mm，标高单位m。', '2. 墙体轴线居中，墙厚200。', '3. 线宽组b=0.7：剖到的墙体b，',
             '   门窗0.5b，家具、尺寸与符号0.25b。', '4. 立面索引A～D与详图1仅示意索引关系，',
             '   对应立面图与详图本示例未绘出。']
    for i, line in enumerate(notes):
        sh.text(line, sh.p(250, 215 - i * 7), 5.0 if i == 0 else 3.5)
    sh.frame('卧室平面布置图', 'LM-LS-03', '1:50')
    _save(doc, path)
    clear = all(not swing.intersects(shape) for shape in furniture.values())
    return {
        'id': 'interior-bedroom', 'file': Path(path).name, 'route': 'interior',
        'learning_note': 'references/industry-learning/spatial-design.md', 'title': '卧室平面布置图', 'scale': '1:50',
        'demonstrates': ['线宽组b=0.7：墙体、门窗、家具分级', '定位轴线编号：数字自左向右、字母自下向上',
                         '建筑尺寸起止符号用中粗斜短线，分段尺寸在内、总尺寸在外', '门洞、门扇开启线与窗的四线表示',
                         '完成面标高±0.000，单位m', '立面索引符号A～D与详图索引符号', '指北针、图名与比例'],
        'standard_ids': ['building-general', 'interior-drawing', 'drawing-fonts', 'furniture-beds',
                         'furniture-cabinets'],
        'self_checks': [
            _check('分段尺寸之和等于总尺寸', math.isclose(door[0] + (door[1] - door[0]) + (W - door[1]), W)
                   and math.isclose(window[0] + (window[1] - window[0]) + (W - window[1]), W), '600+900+2700=4200，1350+1500+1350=4200'),
            _check('门扇开启范围不碰家具', clear, '开启扇形与家具外框求交'),
            _check('房间净面积', math.isclose(area, 13.6), '(4200-200)×(3600-200)=13.60平方米'),
        ]}


# ---------------------------------------------------------------- environment design
def environment(path):
    s = 300.0
    doc = _document(ARCH_LAYERS + [('E-流线', 'DASHED', 25), ('E-导视', 'Continuous', 35)], s)
    sh = Sheet(doc, s, (-40 * s, -100 * s), 'arch')
    Wd, Ht = 60000.0, 40000.0
    north_gate = (27000.0, 33000.0)
    east_gate = (17000.0, 23000.0)
    for a, b in [((0, 0), (Wd, 0)), ((Wd, 0), (Wd, east_gate[0])), ((Wd, east_gate[1]), (Wd, Ht)),
                 ((Wd, Ht), (north_gate[1], Ht)), ((north_gate[0], Ht), (0, Ht)), ((0, Ht), (0, 0))]:
        sh.line(a, b, 'A-墙体')
    sh.line((-3000, Ht + 2000), (Wd + 1500, Ht + 2000), 'A-门窗')
    sh.line((-3000, Ht + 9000), (Wd + 1500, Ht + 9000), 'A-门窗')
    sh.text('城市道路', (Wd / 2, Ht + 5500), 5.0, align=A.MIDDLE_CENTER)
    sh.rect(15000, -12000, 45000, 0, 'A-墙体')
    sh.text('主楼', (30000, -6000), 5.0, align=A.MIDDLE_CENTER)
    places = {'北入口': (30000.0, Ht), '东入口': (Wd, 20000.0), '主楼': (30000.0, 0.0),
              '卫生间': (11000.0, 30000.0), '咖啡亭': (50000.0, 32000.0)}
    sh.rect(8000, 28000, 14000, 32000, 'A-门窗')
    sh.text('卫生间', (11000, 31000), 3.0, align=A.MIDDLE_CENTER)
    sh.rect(48000, 30000, 52000, 34000, 'A-门窗')
    sh.text('咖啡亭', (50000, 33000), 3.0, align=A.MIDDLE_CENTER)
    decisions = {'D1': (30000.0, 28000.0), 'D2': (45000.0, 20000.0), 'D3': (30000.0, 12000.0)}
    routes = [['北入口', 'D1', 'D3', '主楼'], ['东入口', 'D2', 'D3'], ['D1', '卫生间'], ['D1', '咖啡亭'],
              ['D2', '咖啡亭']]
    where = {**places, **decisions}
    for route in routes:
        points = [where[k] for k in route]
        sh.poly(points, 'E-流线')
        a, b = points[-2], points[-1]
        sh.arrow(b, (b[0] - a[0], b[1] - a[1]), 'E-流线')
    for name, (x, y) in decisions.items():
        sh.circle((x, y), 2.5 * s, 'A-符号')
        sh.text(name, (x + 3 * s, y - 3 * s), 3.0, align=A.TOP_LEFT)
    signs = [('S1', '北入口', (30000.0, 38500.0), '总览牌', '北入口、主楼、卫生间、咖啡亭'),
             ('S2', '东入口', (58500.0, 20000.0), '总览牌', '东入口、主楼、咖啡亭'),
             ('S3', 'D1', (31500.0, 28000.0), '方向牌', '主楼、卫生间、咖啡亭'),
             ('S4', 'D2', (45000.0, 21500.0), '方向牌', '主楼、咖啡亭'),
             ('S5', 'D3', (31500.0, 12000.0), '方向牌', '北入口、东入口、主楼'),
             ('S6', '卫生间', (11000.0, 27000.0), '设施名称牌', '卫生间（配通用图形符号）'),
             ('S7', '主楼', (31500.0, 1500.0), '设施名称牌', '主楼')]
    for code, _, (x, y), _, _ in signs:
        half = 1.5 * s
        sh.fill([(x - half, y - half), (x + half, y - half), (x + half, y + half), (x - half, y + half)], 'E-导视')
        sh.text(code, (x + 2.2 * s, y + 0.8 * s), 3.0)
    rows = [('编号', '位置', '牌型', '指向/内容')] + [(c, p, t, d) for c, p, _, t, d in signs]
    sh.table(256, 265, [14, 22, 26, 93], 8, rows, '图框-细', 3.0)
    legend_y = 185
    sh.text('图例', sh.p(250, legend_y), 5.0)
    sh.line(sh.p(252, legend_y - 9), sh.p(268, legend_y - 9), 'E-流线')
    sh.text('人行流线', sh.p(272, legend_y - 10.5), 3.0)
    sh.circle(sh.p(260, legend_y - 18), 2.5 * s, 'A-符号')
    sh.text('决策点', sh.p(272, legend_y - 19.5), 3.0)
    lx, ly = sh.p(260, legend_y - 27)
    half = 1.5 * s
    sh.fill([(lx - half, ly - half), (lx + half, ly - half), (lx + half, ly + half), (lx - half, ly + half)], 'E-导视')
    sh.text('导视牌', sh.p(272, legend_y - 28.5), 3.0)
    notes = ['说明', '1. 导视点位沿人行流线布置，入口设总览牌，', '   每个决策点设方向牌。',
             '2. 同一目的地在各牌面名称一致（见点位表）。', '3. 图形符号采用GB/T 10001.1通用符号，',
             '   本图以文字代替符号图形。', '4. 牌体尺寸、字高与视距按正文确定，本图不给数值。']
    for i, line in enumerate(notes):
        sh.text(line, sh.p(250, 140 - i * 7), 5.0 if i == 0 else 3.5)
    sh.north(395, 75)
    sh.title(140, 48, '广场导视点位图', '1:300')
    sh.frame('广场导视点位图', 'LM-LS-04', '1:300')
    _save(doc, path)
    covered = all(any(math.dist(pos, decisions[d]) <= 5000 for _, _, pos, _, _ in signs) for d in decisions)
    names = {n for *_, d in signs for n in d.replace('（配通用图形符号）', '').split('、')}
    consistent = names <= set(places)
    return {
        'id': 'environment-wayfinding', 'file': Path(path).name, 'route': 'environment_design',
        'learning_note': 'references/industry-learning/environment-design.md', 'title': '广场导视点位图',
        'scale': '1:300',
        'demonstrates': ['先画人行流线，再在入口和决策点布置导视', '总览牌、方向牌、设施名称牌三类牌型',
                         '点位表与图面编号一一对应', '目的地名称在全部牌面统一', '图例、指北针、图名比例'],
        'standard_ids': ['wayfinding-setting', 'wayfinding-elements', 'public-symbols', 'accessibility',
                         'site-plan-drawing'],
        'self_checks': [
            _check('每个决策点5 m内有导视牌', covered, '决策点与导视牌距离'),
            _check('牌面目的地名称都在场所名称表中', consistent, '点位表“指向/内容”拆分后比对'),
            _check('点位表行数与图面导视牌数量一致', len(rows) - 1 == len(signs), '图面7个导视牌'),
        ]}


# ---------------------------------------------------------------- landscape
def _contours(triangles, level):
    segments = []
    for tri in triangles:
        cut = []
        for (x1, y1, z1), (x2, y2, z2) in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            if (z1 - level) * (z2 - level) < 0:
                t = (level - z1) / (z2 - z1)
                cut.append((round(x1 + t * (x2 - x1), 3), round(y1 + t * (y2 - y1), 3)))
        if len(cut) == 2:
            segments.append(cut)
    chains = []
    while segments:
        chain = segments.pop(0)
        grown = True
        while grown:
            grown = False
            for i, seg in enumerate(segments):
                if seg[0] == chain[-1] or seg[1] == chain[-1]:
                    chain.append(seg[1] if seg[0] == chain[-1] else seg[0])
                elif seg[0] == chain[0] or seg[1] == chain[0]:
                    chain.insert(0, seg[1] if seg[0] == chain[0] else seg[0])
                else:
                    continue
                segments.pop(i)
                grown = True
                break
        chains.append(chain)
    return chains


def landscape(path):
    s = 200.0
    doc = _document(ARCH_LAYERS + [('L-等高线', 'Continuous', 25), ('L-坐标网', 'Continuous', 13),
                                   ('L-种植', 'Continuous', 25)], s)
    sh = Sheet(doc, s, (-45 * s, -110 * s), 'arch')
    Wd, Ht = 40000.0, 30000.0
    corners = {'SW': (0.0, 0.0, 10.25), 'NW': (0.0, Ht, 10.55), 'NE': (Wd, Ht, 10.45), 'SE': (Wd, 0.0, 10.15)}
    low = (24000.0, 12000.0, 9.95)
    order = ['SW', 'NW', 'NE', 'SE']
    triangles = [(corners[order[i]], corners[order[(i + 1) % 4]], low) for i in range(4)]
    sh.rect(0, 0, Wd, Ht, 'A-墙体')
    for x in range(10000, 40000, 10000):
        sh.line((x, 0), (x, Ht), 'L-坐标网')
    for y in range(10000, 30000, 10000):
        sh.line((0, y), (Wd, y), 'L-坐标网')
    for x in range(0, 40001, 10000):
        sh.text(f'A={x / 1000:.2f}', (x, -4 * s), 2.5, align=A.TOP_CENTER)
    for y in range(0, 30001, 10000):
        sh.text(f'B={y / 1000:.2f}', (-3 * s, y), 2.5, align=A.MIDDLE_RIGHT)
    levels = [round(10.0 + 0.1 * i, 2) for i in range(6)]
    contour_count = 0
    for level in levels:
        for chain in _contours(triangles, level):
            closed = len(chain) > 2 and chain[0] == chain[-1]
            sh.poly(chain[:-1] if closed else chain, 'L-等高线', closed=closed)
            contour_count += 1
            mid = LineString(chain).interpolate(0.5, normalized=True)
            sh.text(_number(level), (mid.x + 0.6 * s, mid.y + 0.6 * s), 2.5)
    def spot(x, y, z, label=None):
        sh.fill([(x, y), (x - 1.5 * s, y + 2.6 * s), (x + 1.5 * s, y + 2.6 * s)], 'A-符号')
        sh.text(label or _number(z), (x + 2 * s, y + 1.2 * s), 3.0)
    for name, (x, y, z) in corners.items():
        spot(x, y, z)
    lx, ly, lz = low
    g = 1.2 * s
    sh.rect(lx - g, ly - g, lx + g, ly + g, 'A-符号')
    sh.line((lx - g, ly), (lx + g, ly), 'A-符号')
    sh.text(f'雨水口 {lz:.2f}', (lx + 2 * s, ly - 2 * s), 3.0, align=A.TOP_LEFT)
    slopes = {}
    for name, (x, y, z) in corners.items():
        dist = math.dist((x, y), (lx, ly)) / 1000
        i = (z - lz) / dist * 100
        slopes[name] = i
        a = (x + (lx - x) * 0.30, y + (ly - y) * 0.30)
        b = (x + (lx - x) * 0.45, y + (ly - y) * 0.45)
        sh.line(a, b, 'A-符号')
        sh.arrow(b, (lx - x, ly - y), 'A-符号')
        sh.text(f'i={i:.2f}%', (a[0] + 1 * s, a[1] + 1.5 * s), 2.5)
    trees = [(1, (x, 27000.0)) for x in (4000.0, 10000.0, 16000.0, 22000.0, 28000.0, 34000.0)] + \
            [(2, (3000.0, y)) for y in (6000.0, 11000.0, 16000.0, 21000.0)]
    crowns = {1: 2000.0, 2: 1500.0}
    for kind, (x, y) in trees:
        sh.circle((x, y), crowns[kind], 'L-种植')
        sh.line((x - 0.8 * s, y), (x + 0.8 * s, y), 'L-种植')
        sh.line((x, y - 0.8 * s), (x, y + 0.8 * s), 'L-种植')
        sh.text(str(kind), (x + 0.6 * s, y + 0.6 * s), 2.5)
    counts = {k: sum(1 for t, _ in trees if t == k) for k in crowns}
    rows = [('编号', '名称', '规格（cm/m）', '数量', '单位'),
            ('1', '国槐', f'胸径12 高4.5～5.0 冠幅3.5～4.0', counts[1], '株'),
            ('2', '紫叶李', f'地径8 高2.5～3.0 冠幅2.5～3.0', counts[2], '株')]
    sh.text('苗木表', sh.p(265, 272), 5.0)
    sh.table(265, 268, [12, 18, 76, 14, 12], 8, rows, '图框-细', 3.0)
    notes = ['说明', '1. 坐标、标高单位m，取至小数点后两位；', '   坐标系与高程基准按项目测量资料。',
             '2. 设计等高线间距0.10 m。', '3. 场地向雨水口汇水，坡度见坡向箭头。',
             '4. 坡度与苗木规格为示例取值，', '   项目按规范与设计确定。']
    for i, line in enumerate(notes):
        sh.text(line, sh.p(265, 215 - i * 7), 5.0 if i == 0 else 3.5)
    sh.north(395, 150)
    sh.title(145, 70, '场地竖向与种植设计图', '1:200')
    sh.frame('场地竖向与种植设计图', 'LM-LS-05', '1:200')
    _save(doc, path)
    downhill = all(z > lz for _, _, z in corners.values())
    return {
        'id': 'landscape-grading', 'file': Path(path).name, 'route': 'landscape',
        'learning_note': 'references/industry-learning/landscape.md', 'title': '场地竖向与种植设计图',
        'scale': '1:200',
        'demonstrates': ['施工坐标网A/B与单位m取两位小数', '设计等高线0.10 m间距及标注', '室外地坪标高用涂黑三角形',
                         '坡向箭头与坡度i值', '雨水口低点汇水', '种植图例、编号与苗木表数量一致'],
        'standard_ids': ['site-plan-drawing', 'landscape-drawing', 'landscape-project-code', 'park-design'],
        'self_checks': [
            _check('四角均高于雨水口，坡向箭头全部指向低处', downhill, '角点标高与9.95比较'),
            _check('各方向坡度', min(slopes.values()) > 0,
                   '、'.join(f'{k} {v:.2f}%' for k, v in slopes.items()) + '（示例取值，最小坡度按项目规范）'),
            _check('等高线生成且无逆向低点', contour_count >= len(levels), f'{contour_count}条等高线'),
            _check('苗木表数量与图面株数一致', counts == {1: 6, 2: 4}, '国槐6株、紫叶李4株'),
        ]}


# ---------------------------------------------------------------- food processing
FOOD_ROOMS = {  # name: (x0, y0, x1, y1, zone) ; zone rank: 3 clean, 2 semi-clean, 1 general, 0 auxiliary
    '原料库': (0, 0, 4000, 6000, 1), '称量配料': (0, 6000, 4000, 12000, 2), '和面': (4000, 6000, 8000, 12000, 2),
    '醒发': (8000, 6000, 10000, 12000, 2), '烘烤': (10000, 6000, 13000, 12000, 2),
    '冷却': (13000, 8000, 18000, 12000, 3), '内包装': (13000, 4000, 18000, 8000, 3),
    '走廊': (4000, 4000, 11000, 6000, 2), '二更缓冲': (11000, 4000, 13000, 6000, 3),
    '卫生间': (4000, 0, 5500, 4000, 0), '一更': (5500, 0, 8000, 4000, 1), '洗手消毒': (8000, 0, 11000, 4000, 2),
    '外包装': (11000, 0, 15000, 4000, 1), '成品库': (15000, 0, 18000, 4000, 1)}
ZONE_NAMES = {3: '清洁作业区', 2: '准清洁作业区', 1: '一般作业区', 0: '辅助用房'}
# (rooms, wall axis, along-wall start, end, kind): x=... vertical wall, y=... horizontal wall
FOOD_DOORS = [
    (('室外', '原料库'), ('x', 0), 2000, 3500, 'material'), (('原料库', '称量配料'), ('y', 6000), 1000, 2500, 'material'),
    (('称量配料', '和面'), ('x', 4000), 8400, 9600, 'material'), (('和面', '醒发'), ('x', 8000), 8400, 9600, 'material'),
    (('醒发', '烘烤'), ('x', 10000), 8400, 9600, 'material'), (('烘烤', '冷却'), ('x', 13000), 9400, 10600, 'hatch'),
    (('冷却', '内包装'), ('y', 8000), 15000, 16200, 'material'), (('内包装', '外包装'), ('y', 4000), 13300, 14500, 'material'),
    (('外包装', '成品库'), ('x', 15000), 1000, 2500, 'material'), (('成品库', '室外'), ('x', 18000), 1000, 2500, 'material'),
    (('室外', '一更'), ('y', 0), 6000, 7000, 'person'), (('一更', '卫生间'), ('x', 5500), 2500, 3300, 'person'),
    (('一更', '洗手消毒'), ('x', 8000), 1000, 2000, 'person'), (('洗手消毒', '走廊'), ('y', 4000), 9000, 10000, 'person'),
    (('走廊', '和面'), ('y', 6000), 5000, 6000, 'person'), (('走廊', '醒发'), ('y', 6000), 8500, 9500, 'person'),
    (('走廊', '烘烤'), ('y', 6000), 10200, 10900, 'person'), (('走廊', '二更缓冲'), ('x', 11000), 4400, 5400, 'person'),
    (('二更缓冲', '内包装'), ('x', 13000), 4400, 5400, 'person')]


def food(path):
    s = 100.0
    doc = _document(ARCH_LAYERS + [('F-物流', 'Continuous', 35), ('F-人流', 'DASHED', 25),
                                   ('F-排水', 'DASHED2', 25), ('F-设备', 'Continuous', 25)], s)
    sh = Sheet(doc, s, (-45 * s, -130 * s), 'arch')
    Wd, Ht, TE, TI = 18000.0, 12000.0, 240.0, 120.0
    segments = [(((-TE / 2, 0), (Wd + TE / 2, 0)), TE), (((Wd, -TE / 2), (Wd, Ht + TE / 2)), TE),
                (((Wd + TE / 2, Ht), (-TE / 2, Ht)), TE), (((0, Ht + TE / 2), (0, -TE / 2)), TE)]
    for x0, y0, x1, y1, _ in FOOD_ROOMS.values():
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            exterior = (a[0] == b[0] and a[0] in (0, Wd)) or (a[1] == b[1] and a[1] in (0, Ht))
            if not exterior:
                segments.append(((a, b), TI))
    openings = []
    for (_, (axis, at), a, b, _) in FOOD_DOORS:
        openings.append((at - TE, a, at + TE, b) if axis == 'x' else (a, at - TE, b, at + TE))
    _draw_regions(sh, _walls(segments, openings), 'A-墙体')
    # zones
    inner = {}
    for name, (x0, y0, x1, y1, zone) in FOOD_ROOMS.items():
        half = lambda v, outer: TE / 2 if v in outer else TI / 2
        bx0, by0 = x0 + half(x0, (0, Wd)), y0 + half(y0, (0, Ht))
        bx1, by1 = x1 - half(x1, (0, Wd)), y1 - half(y1, (0, Ht))
        inner[name] = box(bx0, by0, bx1, by1)
        if zone == 3:
            sh.pattern([(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)], 'A-填充', 'ANSI37', 6)
        elif zone == 2:
            sh.pattern([(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)], 'A-填充', 'ANSI31', 6)
    labels = {'走廊': (5200, 5000), '二更缓冲': (12000, 5600), '卫生间': (4750, 1400), '醒发': (9000, 7200),
              '冷却': (14200, 9000), '一更': (7000, 3000), '洗手消毒': (10350, 1600)}
    for name, (x0, y0, x1, y1, zone) in FOOD_ROOMS.items():
        cx, cy = labels.get(name, ((x0 + x1) / 2, (y0 + y1) / 2 - 1500))
        rot = 90 if name in ('醒发', '卫生间') else 0
        sh.text(name, (cx, cy), 3.5, align=A.MIDDLE_CENTER, rotation=rot)
    # equipment: at least 600 mm from the finished wall faces (sample choice)
    equipment = {'称量台': ('称量配料', box(800, 10600, 2400, 11200)), '和面机': ('和面', box(4800, 10200, 6000, 11000)),
                 '醒发箱': ('醒发', box(8700, 9800, 9300, 11000)), '烤炉': ('烘烤', box(10900, 9500, 12100, 11000)),
                 '冷却架': ('冷却', box(14500, 10200, 16500, 10800)), '包装台': ('内包装', box(16000, 4800, 17200, 6600))}
    for name, (_, shape) in equipment.items():
        x0, y0, x1, y1 = shape.bounds
        sh.rect(x0, y0, x1, y1, 'F-设备')
        sh.text(name, ((x0 + x1) / 2, y1 + 1 * s), 2.5, align=A.BOTTOM_CENTER)
    clearance = {n: inner[r].exterior.distance(shp) for n, (r, shp) in equipment.items()}
    # hand washing at clean-zone entry, drains, flows
    for x, y in ((12000, 4700), (9500, 3000)):
        sh.rect(x - 400, y - 250, x + 400, y + 250, 'F-设备')
    sh.text('洗手消毒（非手动龙头）', (12000, 4300), 2.0, align=A.TOP_CENTER)
    sh.text('洗手、干手、消毒', (9500, 2600), 2.5, align=A.TOP_CENTER)
    drains = {'D-1': (6600, 7200), 'D-2': (11500, 7000), 'D-3': (9500, 900)}
    for code, (x, y) in drains.items():
        r = 1.5 * s
        sh.circle((x, y), r, 'A-符号')
        sh.line((x - r * 0.7, y - r * 0.7), (x + r * 0.7, y + r * 0.7), 'A-符号')
        sh.line((x - r * 0.7, y + r * 0.7), (x + r * 0.7, y - r * 0.7), 'A-符号')
    drain_path = [(6600, 7200), (6600, 5000), (9500, 5000), (9500, 900), (9500, -1500)]
    sh.poly(drain_path, 'F-排水')
    sh.poly([(11500, 7000), (11500, 5000), (9500, 5000)], 'F-排水')
    for a, b in ((drain_path[0], drain_path[1]), ((11500, 7000), (11500, 5000)), (drain_path[3], drain_path[4])):
        sh.arrow(b, (b[0] - a[0], b[1] - a[1]), 'F-排水')
    material = [(-600, 2750), (2000, 2750), (1750, 6000), (2000, 9000), (4000, 9000), (8000, 9000), (10000, 9000),
                (12500, 9000), (13000, 10000), (15600, 10000), (15600, 8000), (15000, 6000), (13900, 4000), (13900, 2200),
                (15000, 1750), (18000, 1750), (18900, 1750)]
    sh.poly(material, 'F-物流')
    for i in range(1, len(material), 3):
        a, b = material[i - 1], material[i]
        sh.arrow(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), (b[0] - a[0], b[1] - a[1]), 'F-物流')
    sh.arrow(material[-1], (1, 0), 'F-物流')
    person = [(6500, -1500), (6500, 1500), (8000, 1500), (9500, 2000), (9500, 4000), (9500, 5300), (11000, 4900),
              (13000, 4900), (14200, 5600), (14200, 7000)]
    branch = [(5500, 5300), (5500, 7000)]
    sh.poly(person, 'F-人流')
    sh.poly([(9500, 5300), *branch], 'F-人流')
    sh.arrow(person[-1], (0, 1), 'F-人流')
    sh.arrow(branch[-1], (0, 1), 'F-人流')
    sh.text('原料入口', (-600, 3300), 3.0, align=A.BOTTOM_CENTER)
    sh.text('成品出口', (18900, 2300), 3.0, align=A.BOTTOM_CENTER)
    sh.text('员工入口', (6500, -2000), 3.0, align=A.TOP_CENTER)
    sh.text('排至室外', (9500, -2000), 2.5, align=A.TOP_LEFT)
    sh.text('传递窗', (13000, 11000), 2.5, align=A.BOTTOM_CENTER)
    # overall dimensions
    sh.dim((0, Ht + TE / 2), (Wd, Ht + TE / 2), (0, Ht + 1000))
    sh.dim((-TE / 2, 0), (-TE / 2, Ht), (-1500, 0), 90)
    sh.text('门洞以墙体缺口示意', (Wd, Ht + 1600), 2.5, align=A.BOTTOM_RIGHT)
    # legend and self-check table
    lx = 245
    sh.text('图例', sh.p(lx, 284), 5.0)
    entries = [('ANSI37', '清洁作业区'), ('ANSI31', '准清洁作业区'), (None, '一般作业区、辅助用房')]
    for i, (pat, label) in enumerate(entries):
        y = 274 - i * 8
        pts = [sh.p(lx, y), sh.p(lx + 12, y), sh.p(lx + 12, y + 5), sh.p(lx, y + 5)]
        sh.poly(pts, '图框-细', closed=True)
        if pat:
            sh.pattern(pts, 'A-填充', pat, 2)
        sh.text(label, sh.p(lx + 15, y + 2.5), 3.0, align=A.MIDDLE_LEFT)
    for i, (layer, label) in enumerate((('F-物流', '物流（原料→成品）'), ('F-人流', '人流'), ('F-排水', '排水管道及流向'))):
        y = 252 - i * 7
        sh.line(sh.p(lx, y), sh.p(lx + 12, y), layer)
        sh.text(label, sh.p(lx + 15, y), 3.0, align=A.MIDDLE_LEFT)
    dx, dy = sh.p(lx + 6, 230)
    r = 1.5 * s
    sh.circle((dx, dy), r, 'A-符号')
    sh.text('地漏（带水封）', sh.p(lx + 15, 230), 3.0, align=A.MIDDLE_LEFT)
    material_line = LineString(material)
    person_lines = [LineString(person), LineString([(9500, 5300), *branch])]
    crossing = any(material_line.intersects(p) for p in person_lines)
    toilet_ok = all(FOOD_ROOMS[other][4] <= 1 for rooms, *_ in FOOD_DOORS if '卫生间' in rooms
                    for other in rooms if other != '卫生间')
    zone_at = lambda pt: next((z for n, (x0, y0, x1, y1, z) in FOOD_ROOMS.items()
                               if x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1), -1)
    drain_zones = [zone_at(p) for p in drain_path]
    drain_ok = all(a >= b for a, b in zip(drain_zones, drain_zones[1:]))
    clean_entry = any('二更缓冲' in rooms for rooms, *_ in FOOD_DOORS)
    gaps_ok = min(clearance.values()) >= 600 - 1e-6
    separated = all(kind != 'person' or abs(FOOD_ROOMS.get(r[0], (0, 0, 0, 0, 1))[4] -
                                            FOOD_ROOMS.get(r[1], (0, 0, 0, 0, 1))[4]) <= 1
                    for r, _, _, _, kind in FOOD_DOORS)
    checks = [
        _check('4.1.3 作业区划分并以墙、门分隔；人员不跨级进入', separated, '每个房间标注作业区，人员门两侧最多差一级'),
        _check('5.1.2.4 室内排水由清洁程度高流向低', drain_ok, ' → '.join(ZONE_NAMES.get(z, '室外') for z in drain_zones)),
        _check('5.1.5.3 卫生间不与生产、包装、贮存区直接连通', toilet_ok, '卫生间只开门到一更'),
        _check('5.1.5.4 清洁作业区入口设洗手、消毒', clean_entry, '走廊→二更缓冲（洗手消毒）→内包装'),
        _check('5.2.1.3.2 设备与墙留清洁维护空间', gaps_ok, f'设备距墙最小{min(clearance.values()):.0f} mm（示例取600）'),
        _check('人流与物流路线不交叉（审查细则常见要求）', not crossing, '两条路径几何求交')]
    short = ['4.1.3 作业区划分与分隔', '5.1.2.4 排水由清洁区流向非清洁区', '5.1.5.3 卫生间不直通生产区',
             '5.1.5.4 清洁作业区入口洗手消毒', '5.2.1.3.2 设备与墙留清洁空间', '人流物流不交叉（审查细则常见要求）']
    rows = [('条号/项目', '示例结果')] + [(t, '符合' if c['result'] == 'pass' else '不符合') for t, c in zip(short, checks)]
    sh.text('示例自检（只核对本图表达）', sh.p(lx, 214), 3.5)
    sh.table(lx, 210, [140, 26], 7, rows, '图框-细', 2.5)
    sh.text('不是生产许可或工程审查结论', sh.p(lx, 155), 2.5)
    sh.north(395, 120)
    sh.title(135, 92, '面包坊车间工艺平面布置图', '1:100')
    sh.frame('面包坊车间工艺平面布置图', 'LM-LS-06', '1:100')
    _save(doc, path)
    return {
        'id': 'food-bakery', 'file': Path(path).name, 'route': 'food_processing',
        'learning_note': 'references/industry-learning/food-processing.md', 'title': '面包坊车间工艺平面布置图',
        'scale': '1:100',
        'demonstrates': ['按清洁程度划分清洁、准清洁、一般作业区并用填充区分', '物流按工序单向：原料入口→成品出口',
                         '人流经一更、洗手消毒进入准清洁区，经二更缓冲进入清洁区', '卫生间只与一更相通',
                         '地漏与排水流向由准清洁区排向室外，清洁作业区不设地漏（示例设计选择）',
                         '设备距墙600 mm留清洁空间', '烘烤到冷却经传递窗'],
        'standard_ids': ['food-hygiene', 'building-general', 'food-cleanroom-building', 'site-plan-drawing'],
        'self_checks': checks}


SAMPLES = [('learning-mechanical-shaft.dxf', mechanical), ('learning-product-enclosure.dxf', product),
           ('learning-interior-bedroom.dxf', interior), ('learning-environment-wayfinding.dxf', environment),
           ('learning-landscape-grading.dxf', landscape), ('learning-food-bakery.dxf', food)]


def build(output_dir):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    records = [function(output / name) for name, function in SAMPLES]
    index = {'schema_version': 1, 'generated_by': 'scripts/build_learning_samples.py', 'notice': NOTICE,
             'units': 'mm', 'samples': records}
    (output / 'learning-samples.json').write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n',
                                                  encoding='utf-8')
    failed = [(r['id'], c['item']) for r in records for c in r['self_checks'] if c['result'] != 'pass']
    if failed:
        raise ValueError(f'Learning sample self-check failed: {failed}')
    return index
