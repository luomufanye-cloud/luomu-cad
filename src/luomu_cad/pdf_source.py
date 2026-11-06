"""Measured PDF vector extraction. No layout inference or source-file mutation.

PDFium is an external dependency. All PDFium calls are serialized: its native
library is not thread safe. Generated inventories are source measurements, not
evidence that the final drawing has passed visual or engineering review.
"""
import ctypes as ct
import hashlib
import json
import math
from pathlib import Path
import threading

from .reference_geometry import PageTransform
from .reference_presentation import font_ink_bounds, measured_text_attributes, stroke_attributes

_LOCK = threading.RLock()
_IDENTITY = (1., 0., 0., 1., 0., 0.)


def _number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2 or not all(_number(x) for x in value):
        raise ValueError('Finite PDF [x, y] coordinates required')
    return tuple(value)


def calibration_scale(calibration):
    """A measured baseline plus an independent, nonparallel check are required."""
    required = {'source_points', 'distance_mm', 'check_points', 'check_distance_mm', 'tolerance_mm'}
    if not isinstance(calibration, dict) or required - calibration.keys():
        raise ValueError('Calibration requires source_points, distance_mm, check_points, check_distance_mm, tolerance_mm')
    for key in ('distance_mm', 'check_distance_mm', 'tolerance_mm'):
        if not _number(calibration[key]) or calibration[key] <= 0:
            raise ValueError('Calibration distances and tolerance must be positive finite mm')
    vectors = []
    for key in ('source_points', 'check_points'):
        pair = calibration[key]
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError('Two measured endpoints required for each calibration')
        a, b = map(_point, pair)
        vectors.append((b[0] - a[0], b[1] - a[1]))
    first, second = vectors
    lengths = list(map(lambda v: math.hypot(*v), vectors))
    if min(lengths) <= 0:
        raise ValueError('Zero length calibration baseline')
    if abs(first[0] * second[1] - first[1] * second[0]) / math.prod(lengths) < .2:
        raise ValueError('Independent calibration check must use a different direction')
    scale = calibration['distance_mm'] / lengths[0]
    difference = abs(lengths[1] * scale - calibration['check_distance_mm'])
    if difference > calibration['tolerance_mm']:
        raise ValueError('CALIBRATION_CONFLICT: independent measurement differs by %.6g mm' % difference)
    return scale, difference


def _mul(a, b):
    """Composition a(b(point)), PDF six-value affine convention."""
    return (a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5])


def _apply(m, p):
    return (m[0]*p[0]+m[2]*p[1]+m[4], m[1]*p[0]+m[3]*p[1]+m[5])


def _matrix(raw, obj):
    m = raw.FS_MATRIX()
    if not raw.FPDFPageObj_GetMatrix(obj, m):raise ValueError('PDF_MATRIX_UNREADABLE')
    return tuple(getattr(m, k) for k in ('a', 'b', 'c', 'd', 'e', 'f'))


def _address(obj):
    return ct.cast(obj, ct.c_void_p).value


def _segments(raw, count, getter):
    """Read move/line/cubic segments without sampling Beziers into polylines."""
    paths = []; current = None; i = 0
    while i < count:
        segment = getter(i); kind = raw.FPDFPathSegment_GetType(segment)
        x, y = ct.c_float(), ct.c_float()
        if not raw.FPDFPathSegment_GetPoint(segment, x, y):raise ValueError('PDF_PATH_POINT_UNREADABLE')
        point = (float(x.value), float(y.value))
        if kind == raw.FPDF_SEGMENT_MOVETO:
            current = {'start': point, 'segments': [], 'closed': False}; paths.append(current)
        elif current is None:raise ValueError('PDF_PATH_WITHOUT_MOVE')
        elif kind == raw.FPDF_SEGMENT_LINETO:
            current['segments'].append(('line', point))
        elif kind == raw.FPDF_SEGMENT_BEZIERTO:
            controls = [point]
            for j in (1, 2):
                if i+j >= count:raise ValueError('PDF_CUBIC_INCOMPLETE')
                segment = getter(i+j)
                if raw.FPDFPathSegment_GetType(segment) != raw.FPDF_SEGMENT_BEZIERTO:raise ValueError('PDF_CUBIC_INCOMPLETE')
                if not raw.FPDFPathSegment_GetPoint(segment, x, y):raise ValueError('PDF_PATH_POINT_UNREADABLE')
                controls.append((float(x.value), float(y.value)))
            current['segments'].append(('cubic', *controls)); i += 2
        else:raise ValueError('PDF_SEGMENT_UNSUPPORTED')
        if raw.FPDFPathSegment_GetClose(segment):current['closed'] = True
        i += 1
    return paths


def _rgba(raw, obj, stroke=False):
    values = [ct.c_uint() for _ in range(4)]
    fn = raw.FPDFPageObj_GetStrokeColor if stroke else raw.FPDFPageObj_GetFillColor
    if not fn(obj, *values):raise ValueError('PDF_COLOR_UNREADABLE')
    return [v.value for v in values]


def _paint(rgba, width=0):
    attrs = stroke_attributes([c/255 for c in rgba[:3]], width, rgba[3]/255)
    return {'rgb': rgba[:3], 'opacity': rgba[3]/255, 'lineweight': attrs['lineweight'], 'linetype': 'CONTINUOUS'}


def _winding(point, ring):
    x, y = point; value = 0
    for a, b in zip(ring, ring[1:]+ring[:1]):
        side = (b[0]-a[0])*(y-a[1]) - (x-a[0])*(b[1]-a[1])
        if a[1] <= y < b[1] and side > 0:value += 1
        elif b[1] <= y < a[1] and side < 0:value -= 1
    return value


def _fill_polygons(rings, even_odd):
    from shapely.geometry import LineString
    from shapely.ops import polygonize, unary_union
    boundaries = [LineString(r+[r[0]]) for r in rings if len(r) >= 3]
    if not boundaries:raise ValueError('PDF_FILL_EMPTY')
    faces = list(polygonize(unary_union(boundaries))); selected = []
    for face in faces:
        p = face.representative_point(); winding = sum(_winding((p.x, p.y), ring) for ring in rings)
        if (abs(winding) % 2 != 0) if even_odd else (winding != 0):selected.append(face)
    if not selected:return []
    combined = unary_union(selected)
    return [combined] if combined.geom_type == 'Polygon' else list(combined.geoms)


def _font_name(raw, obj):
    font = raw.FPDFTextObj_GetFont(obj)
    size = raw.FPDFFont_GetBaseFontName(font, None, 0)
    if not size:raise ValueError('PDF_FONT_NAME_UNREADABLE')
    buf = ct.create_string_buffer(size); raw.FPDFFont_GetBaseFontName(font, buf, size)
    return buf.value.decode('utf-8', errors='replace')


def _compositing_findings(source, page):
    """Inspect parsed resource dictionaries; PDFium has no blend-mode getter."""
    from pypdf import PdfReader
    from pypdf.generic import ContentStream
    reader=PdfReader(source);findings=[];seen=set()
    def resolve(value):return value.get_object() if hasattr(value,'get_object') else value
    def is_true(value):
        value=resolve(value)
        return value is True or getattr(value,'value',False) is True
    def walk(stream, resources, location, depth=0):
        if depth>15:raise ValueError('PDF_RESOURCE_DEPTH_EXCEEDED')
        resources=resolve(resources)
        for operands,operator in ContentStream(stream,reader).operations:
            if operator==b'gs':
                state=resolve(resources.get('/ExtGState',{})).get(operands[0])
                if state is None:raise ValueError('PDF_GRAPHICS_STATE_MISSING')
                state=state.get_object();mode=resolve(state.get('/BM','/Normal'))
                if isinstance(mode,list):mode=mode[0] if mode else '/Normal'
                if mode not in ('/Normal','/Compatible'):
                    findings.append({'code':'PDF_BLEND_MODE_REQUIRES_CONVERSION','detail':str(mode),'source_locator':location})
                if state.get('/SMask','/None')!='/None':
                    findings.append({'code':'PDF_SOFT_MASK_REQUIRES_CONVERSION','detail':'Soft mask changes visible paint','source_locator':location})
                if is_true(state.get('/OP',False)) or is_true(state.get('/op',False)):
                    findings.append({'code':'PDF_OVERPRINT_REQUIRES_CONVERSION','detail':'Overprint changes visible paint','source_locator':location})
            elif operator==b'Do':
                child=resolve(resources.get('/XObject',{})).get(operands[0])
                if child is None:raise ValueError('PDF_XOBJECT_RESOURCE_MISSING')
                child=child.get_object()
                if child.get('/Subtype')=='/Form':
                    key=id(child)
                    if key in seen:continue
                    seen.add(key)
                    group=child.get('/Group')
                    if group and group.get_object().get('/S')=='/Transparency':
                        findings.append({'code':'PDF_TRANSPARENCY_GROUP_REQUIRES_CONVERSION','detail':'Group compositing requires explicit conversion','source_locator':location})
                    walk(child,child.get('/Resources',resources),{**location,'resource':str(operands[0])},depth+1)
    selected=reader.pages[page]
    if selected.get_contents() is not None:walk(selected.get_contents(),selected.get('/Resources',{}),{'page':page})
    return findings


def _glyphs(raw, page, obj, ancestors):
    """Read actual unrotated ink bounds in an in-memory parsing document.

    The temporary matrices are restored, and the PDF is never saved. Measuring
    each glyph retains source TJ spacing instead of stretching a whole sentence.
    """
    saved = [(ancestor, _matrix(raw, ancestor)) for ancestor in (*ancestors, obj)]
    try:
        for target, _ in saved:
            if not raw.FPDFPageObj_SetMatrix(target, raw.FS_MATRIX(*_IDENTITY)):
                raise ValueError('PDF_TEXT_NORMALIZATION_FAILED')
        tp = raw.FPDFText_LoadPage(page)
        if not tp:raise ValueError('PDF_TEXT_PAGE_UNREADABLE')
        try:
            values = []
            for index in range(raw.FPDFText_CountChars(tp)):
                if _address(raw.FPDFText_GetTextObject(tp, index)) != _address(obj):continue
                if raw.FPDFText_IsGenerated(tp, index) == 1:continue
                code = raw.FPDFText_GetUnicode(tp, index)
                if not code or raw.FPDFText_HasUnicodeMapError(tp, index) == 1:
                    raise ValueError('PDF_TEXT_UNICODE_UNMAPPED')
                text = chr(code)
                if text.isspace():continue
                bounds = [ct.c_double() for _ in range(4)]
                if not raw.FPDFText_GetCharBox(tp, index, *bounds):raise ValueError('PDF_GLYPH_BOUNDS_UNREADABLE')
                left, right, bottom, top = [v.value for v in bounds]
                x, y = ct.c_double(), ct.c_double()
                if not raw.FPDFText_GetCharOrigin(tp, index, x, y):raise ValueError('PDF_GLYPH_ORIGIN_UNREADABLE')
                values.append({'text': text, 'origin': (x.value,y.value),
                               'bounds': (left-x.value,bottom-y.value,right-x.value,top-y.value)})
            return values
        finally:raw.FPDFText_ClosePage(tp)
    finally:
        for target, matrix in reversed(saved):raw.FPDFPageObj_SetMatrix(target, raw.FS_MATRIX(*matrix))


def extract_pdf(source, *, page=0, calibration, font_map=None, max_objects=50000):
    """Return a source inventory plus concrete per-object conversion findings.

    Coordinates and calibration are in unrotated PDF user-space points, Y up.
    The page's declared rotation is applied to the resulting CAD view. A false
    result is diagnostic only: it must not be presented as a completed redraw.
    """
    scale, error = calibration_scale(calibration)
    if isinstance(page, bool) or not isinstance(page, int) or page < 0:raise ValueError('Zero-based PDF page required')
    if not isinstance(max_objects,int) or isinstance(max_objects,bool) or not 1 <= max_objects <= 200000:
        raise ValueError('max_objects must be 1..200000')
    source = Path(source)
    if not source.is_file() or source.suffix.lower() != '.pdf':raise ValueError('Existing PDF source required')
    if source.stat().st_size > 100*1024*1024:raise ValueError('PDF exceeds 100 MiB input limit')
    font_map = font_map or {}
    if not isinstance(font_map, dict):raise ValueError('font_map must map PDF font names to existing font files')
    with _LOCK:
        import pypdfium2 as pdfium
        import pypdfium2.raw as raw
        with pdfium.PdfDocument(source) as doc:
            if page >= len(doc):raise ValueError('PDF page outside document')
            pg = doc[page]; bounds = pg.get_bbox(); rotation = pg.get_rotation()
            x0,y0,x1,y1 = bounds
            rotations = {0:(1,0,0,1,-x0,-y0),90:(0,-1,1,0,-y0,x1),
                         180:(-1,0,0,-1,x1,y1),270:(0,1,-1,0,y1,-x0)}
            if rotation not in rotations:raise ValueError('Invalid PDF page rotation')
            view_matrix = rotations[rotation]; transform = PageTransform(scale, flip_y=False)
            inventory = {'schema_version':1,'delivery_target':'offline_dxf','units':4,'page':page,
                         'view':'Measured PDF page '+str(page+1),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                         'calibration':dict(calibration),'mm_per_pdf_unit':scale,'review_regions':['full_view','text','curves','fills'],
                         'objects':[],'extraction':{'engine':'pypdfium2','engine_version':str(pdfium.PYPDFIUM_INFO),
                         'page_rotation':rotation,'page_bounds_pt':list(bounds),'source_coordinate_system':'PDF user space, Y up',
                         'text_mode':'editable individual glyphs preserving source spacing'}}
            view_corners=[transform.point(_apply(view_matrix,p)) for p in [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]]
            inventory['extraction']['view_window_mm']=[min(p[0] for p in view_corners),min(p[1] for p in view_corners),
                                                      max(p[0] for p in view_corners),max(p[1] for p in view_corners)]
            findings=_compositing_findings(source,page); source_objects=0; fonts=set(); used_fonts={}; glyph_cache={}
            from shapely.geometry import Polygon,LineString,MultiPoint,box
            page_clip=box(*bounds)

            def add(sid, kind, expected, paint, locator, clip):
                if len(inventory['objects']) >= max_objects:raise ValueError('PDF_ENTITY_BUDGET_EXCEEDED')
                vertices=[page_point(_IDENTITY,p)[:2] for p in clip.exterior.coords[:-1]]
                model_clip=Polygon(vertices)
                if kind=='LINE':footprint=LineString([expected['start'][:2],expected['end'][:2]])
                elif kind=='SPLINE':footprint=MultiPoint([p[:2] for p in expected['control_points']]).convex_hull
                elif kind=='LWPOLYLINE':
                    pts=[p[:2] for p in expected['points']]
                    footprint=LineString(pts+[pts[0]] if expected['closed'] else pts)
                elif kind=='HATCH':footprint=Polygon([p[:2] for p in expected['loops'][0]['points']])
                elif kind=='TEXT':
                    source_box=expected.pop('_ink_corners')
                    footprint=Polygon(source_box)
                else:raise ValueError('PDF_CLIP_ENTITY_UNSUPPORTED')
                # Include the pen footprint at the source plot scale; clipping
                # only endpoints misses concave cuts and half-width edge strokes.
                radius=paint['lineweight']/100/2*scale*72/25.4 if kind in ('LINE','SPLINE','LWPOLYLINE') else 0
                if radius:footprint=footprint.buffer(radius)
                if not model_clip.buffer(1e-5*scale).covers(footprint):
                    expected={'clip_polygon':vertices,'entity':{'kind':kind,'expected':expected}}
                    kind='CLIPPED'
                inventory['objects'].append({'id':sid,'kind':kind,'expected':expected,'presentation':paint,
                    'source_locator':locator,'tolerance':max(.001,scale*1e-5)})

            def page_point(matrix, point):return transform.point(_apply(_mul(view_matrix,matrix),point))

            def effective_clip(obj, parent, inherited):
                region=inherited
                clip=raw.FPDFPageObj_GetClipPath(obj)
                count=raw.FPDFClipPath_CountPaths(clip) if clip else 0
                for k in range(max(0,count)):
                    n=raw.FPDFClipPath_CountPathSegments(clip,k)
                    paths=_segments(raw,n,lambda i:raw.FPDFClipPath_GetPathSegment(clip,k,i))
                    if len(paths)!=1 or any(s[0]!='line' for s in paths[0]['segments']):raise ValueError('PDF_COMPLEX_CLIP_REQUIRES_CONVERSION')
                    ring=[paths[0]['start']]+[s[1] for s in paths[0]['segments']]
                    polygon=Polygon([_apply(parent,p) for p in ring])
                    if not polygon.is_valid:raise ValueError('PDF_INVALID_CLIP_POLYGON')
                    region=region.intersection(polygon)
                if not region.is_empty and (region.geom_type!='Polygon' or region.interiors):
                    raise ValueError('PDF_MULTIREGION_CLIP_REQUIRES_CONVERSION')
                return region

            def visit(container, parent=_IDENTITY, prefix='', ancestors=(), inherited_clip=page_clip):
                nonlocal source_objects
                count=raw.FPDFFormObj_CountObjects(container) if ancestors else raw.FPDFPage_CountObjects(container)
                getter=raw.FPDFFormObj_GetObject if ancestors else raw.FPDFPage_GetObject
                for index in range(count):
                    source_objects+=1
                    if source_objects>max_objects:raise ValueError('PDF_OBJECT_BUDGET_EXCEEDED')
                    obj=getter(container,index);sid=prefix+str(index);locator={'page':page,'object_path':sid}
                    try:
                        kind=raw.FPDFPageObj_GetType(obj);matrix=_mul(parent,_matrix(raw,obj))
                        clip=effective_clip(obj,parent,inherited_clip)
                        if clip.is_empty:continue
                        if kind==raw.FPDF_PAGEOBJ_FORM:
                            if len(ancestors)>=15:raise ValueError('PDF_FORM_DEPTH_EXCEEDED')
                            visit(obj,matrix,sid+'.',(*ancestors,obj),clip);continue
                        if kind==raw.FPDF_PAGEOBJ_PATH:
                            n=raw.FPDFPath_CountSegments(obj)
                            paths=_segments(raw,n,lambda i:raw.FPDFPath_GetPathSegment(obj,i))
                            fill,stroke=ct.c_int(),ct.c_int()
                            if not raw.FPDFPath_GetDrawMode(obj,fill,stroke):raise ValueError('PDF_PAINT_MODE_UNREADABLE')
                            if stroke.value and raw.FPDFPageObj_GetDashCount(obj)>0:raise ValueError('PDF_DASH_PATTERN_REQUIRES_CONVERSION')
                            pending=[]
                            if fill.value:
                                if any(s[0]=='cubic' for p in paths for s in p['segments']):raise ValueError('PDF_CURVED_FILL_REQUIRES_CONVERSION')
                                rings=[[page_point(matrix,p['start'])[:2]]+[page_point(matrix,s[1])[:2] for s in p['segments']] for p in paths]
                                for fi,poly in enumerate(_fill_polygons(rings,fill.value==raw.FPDF_FILLMODE_ALTERNATE)):
                                    loops=[{'points':[[x,y,0] for x,y in poly.exterior.coords[:-1]],'closed':True,'external':True}]
                                    loops.extend({'points':[[x,y,0] for x,y in hole.coords[:-1]],'closed':True,'external':False} for hole in poly.interiors)
                                    pending.append((sid+'-fill-'+str(fi),'HATCH',{'solid':True,'hatch_style':0,'loops':loops},_paint(_rgba(raw,obj))))
                            if stroke.value:
                                width=ct.c_float()
                                if not raw.FPDFPageObj_GetStrokeWidth(obj,width):raise ValueError('PDF_STROKE_WIDTH_UNREADABLE')
                                if raw.FPDFPageObj_GetLineCap(obj)!=0 or raw.FPDFPageObj_GetLineJoin(obj)!=0:
                                    raise ValueError('PDF_STROKE_CAP_JOIN_REQUIRES_CONVERSION')
                                sx,sy=math.hypot(matrix[0],matrix[1]),math.hypot(matrix[2],matrix[3])
                                if width.value and (abs(sx-sy)>1e-5 or abs(matrix[0]*matrix[2]+matrix[1]*matrix[3])>1e-5):raise ValueError('PDF_ANISOTROPIC_STROKE_REQUIRES_CONVERSION')
                                paint=_paint(_rgba(raw,obj,True),width.value*sx)
                                for pi,path in enumerate(paths):
                                    if len(path['segments'])>1 and all(s[0]=='line' for s in path['segments']):
                                        pts=[path['start']]+[s[1] for s in path['segments']]
                                        if path['closed'] and pts[-1]==pts[0]:pts.pop()
                                        if len(pts)>1:
                                            pending.append((sid+'-path-'+str(pi),'LWPOLYLINE',
                                                {'points':[[*page_point(matrix,p)[:2],0] for p in pts],
                                                 'closed':path['closed']},paint))
                                        continue
                                    current=path['start']
                                    for si,segment in enumerate(path['segments']):
                                        key=sid+'-stroke-'+str(pi)+'-'+str(si)
                                        if segment[0]=='line':
                                            if current!=segment[1]:pending.append((key,'LINE',{'start':page_point(matrix,current),'end':page_point(matrix,segment[1])},paint))
                                        else:
                                            pending.append((key,'SPLINE',{'degree':3,'knots':[0,0,0,0,1,1,1,1],
                                                'control_points':[page_point(matrix,p) for p in (current,*segment[1:])]},paint))
                                        current=segment[-1]
                                    if path['closed'] and current!=path['start']:
                                        pending.append((sid+'-close-'+str(pi),'LINE',{'start':page_point(matrix,current),'end':page_point(matrix,path['start'])},paint))
                            for args in pending:add(*args,locator,clip)
                        elif kind==raw.FPDF_PAGEOBJ_TEXT:
                            name=_font_name(raw,obj);fonts.add(name)
                            if raw.FPDFTextObj_GetTextRenderMode(obj)!=0:raise ValueError('PDF_TEXT_RENDER_MODE_REQUIRES_CONVERSION')
                            font=font_map.get(name) or font_map.get(name.split('+',1)[-1])
                            if not font:raise ValueError('PDF_FONT_MAPPING_REQUIRED:'+name)
                            font=Path(font)
                            if not font.is_file():raise ValueError('PDF_FONT_FILE_MISSING:'+name)
                            if name not in used_fonts:
                                from fontTools.ttLib import TTFont
                                with TTFont(font,fontNumber=0) as table:family=table['name'].getBestFamilyName()
                                used_fonts[name]={'file':font.name,'sha256':hashlib.sha256(font.read_bytes()).hexdigest(),
                                                  'family':family or font.stem}
                            # Rotation and separate X/Y scaling are supported, shear/reflection
                            # needs explicit text geometry rather than a misleading substitute.
                            combined=_mul(view_matrix,matrix);sx=math.hypot(combined[0],combined[1]);sy=math.hypot(combined[2],combined[3])
                            if sx==0 or sy==0 or combined[0]*combined[3]-combined[1]*combined[2]<=0 or abs(combined[0]*combined[2]+combined[1]*combined[3])>1e-5*sx*sy:
                                raise ValueError('PDF_SHEARED_OR_REFLECTED_TEXT_REQUIRES_CONVERSION')
                            glyphs=_glyphs(raw,pg,obj,ancestors);pending=[]
                            for gi,glyph in enumerate(glyphs):
                                ox,oy=glyph['origin'];l,b,r,t=glyph['bounds']
                                key=(str(font),glyph['text'])
                                if key not in glyph_cache:glyph_cache[key]=font_ink_bounds(glyph['text'],font)
                                measured=measured_text_attributes(transform,source_ink_bounds=(l*sx,b*sy,r*sx,t*sy),
                                    source_origin=_apply(combined,glyph['origin']),source_direction=combined[:2],target_ink_bounds=glyph_cache[key])
                                expected={'text':glyph['text'],'at':measured['insert'],'height':measured['height'],'width':measured['width'],
                                          'rotation':measured['rotation'],'font':font.name,'font_family':used_fonts[name]['family'],
                                          '_ink_corners':[page_point(matrix,p)[:2] for p in [(ox+l,oy+b),(ox+r,oy+b),(ox+r,oy+t),(ox+l,oy+t)]]}
                                pending.append((sid+'-glyph-'+str(gi),'TEXT',expected,_paint(_rgba(raw,obj))))
                            for args in pending:add(*args,locator,clip)
                        elif kind==raw.FPDF_PAGEOBJ_IMAGE:raise ValueError('PDF_RASTER_IMAGE_REQUIRES_TRACING')
                        elif kind==raw.FPDF_PAGEOBJ_SHADING:raise ValueError('PDF_SHADING_REQUIRES_CONVERSION')
                        else:raise ValueError('PDF_OBJECT_TYPE_UNSUPPORTED:'+str(kind))
                    except (ValueError,RuntimeError) as exc:
                        findings.append({'code':str(exc).split(':',1)[0],'detail':str(exc),'source_locator':locator})
            visit(pg)
            inventory['extraction']['fonts']=used_fonts
            inventory['extraction']['source_object_count']=source_objects
            inventory['extraction']['findings']=findings
            inventory['extraction_complete']=not findings and bool(inventory['objects'])
            inventory['dimension_semantics']='PDF graphics do not identify DIMENSION entities; semantic reconstruction requires a reviewed dimension inventory'
            # Identical types for in-process and MCP/JSON consumers.
            inventory=json.loads(json.dumps(inventory,ensure_ascii=False,allow_nan=False))
            return {'ok':not findings and bool(inventory['objects']),'inventory':inventory,'findings':findings,
                    'stats':{'source_objects':source_objects,'cad_entities':len(inventory['objects']),
                             'fonts':sorted(fonts),'calibration_check_error_mm':error},
                    'complete_redraw_accepted':False}
