"""Compare actual native facts with a separately reopened original source DXF.

This never constructs a DXF from a DWG. The entire supported native inventory,
native dimension definitions and cached display geometry must correspond to the
original input file before an already verified DXF/PDF pair can cover the DWG.
"""
import math
import re
from pathlib import Path


def compare(actual,doc,tolerance=1e-6):
    if tolerance!=1e-6:raise ValueError('Native-source comparison tolerance is fixed at 1e-6 model units')
    facts=actual['actual'];differences=[]
    from .annotations import drawing_context
    source_context=drawing_context(doc)
    def equal(a,b,where):
        if isinstance(b,(list,tuple)):
            if not isinstance(a,(list,tuple)) or len(a)!=len(b):differences.append(where);return
            for index,(x,y) in enumerate(zip(a,b)):equal(x,y,where+'/'+str(index))
        elif isinstance(b,(int,float)) and not isinstance(b,bool):
            if isinstance(a,bool) or not isinstance(a,(int,float)) or not math.isfinite(a) or abs(a-b)>tolerance:differences.append(where)
        elif a!=b:differences.append(where)
    source={e.dxf.handle:e for e in doc.modelspace()};native={row['Handle']:row for row in facts['model']}
    if set(source)!=set(native):raise ValueError('Native/source complete model handle inventories differ')
    equal(facts['variables']['INSUNITS'],int(doc.units),'units')
    def point(value):
        result=list(value)
        if len(result)!=3 or abs(result[2])>1e-8:raise ValueError('Source geometry must use positive WCS XY scope')
        return result
    def attr(d,name,default):return d.get(name,default) if d.is_supported(name) else default
    def check(row,expected,where):
        for key,value in expected.items():
            if key not in row:raise ValueError('Required actual native property missing: '+key)
            equal(row[key],value,where+'/'+key)
    model_types={'LINE':'AcDbLine','ARC':'AcDbArc','CIRCLE':'AcDbCircle','ELLIPSE':'AcDbEllipse',
        'LWPOLYLINE':'AcDbPolyline','TEXT':'AcDbText','MTEXT':'AcDbMText',
        'DIMENSION':{'AcDbRotatedDimension','AcDbAlignedDimension'}}
    native_layers={item['Name']:item for item in facts['layers']}
    def compare_layer(name,where):
        layer=doc.layers.get(name)
        if name not in native_layers:raise ValueError('Actual native used layer missing: '+name)
        native_layer=native_layers[name]
        transparency=native_layer.get('transparency_xdata')
        if not isinstance(transparency,(list,tuple)) or len(transparency)!=2:
            raise ValueError('Actual native layer transparency readback required')
        if transparency[1] and transparency[1][-1]!=0x020000ff:
            raise ValueError('Actual native nonopaque layer needs a dedicated paper adapter')
        if layer.transparency!=0 or layer.dxf.hasattr('true_color'):
            raise ValueError('Source nonopaque/true-color layer needs an exact native paper adapter')
        check(native_layer,{'Lineweight':layer.dxf.lineweight,'Color':abs(layer.dxf.color),
            'LayerOn':layer.is_on(),'Freeze':layer.is_frozen(),'Plottable':bool(layer.dxf.get('plot',1))},where)
        equal(native_layer['Linetype'].casefold(),layer.dxf.linetype.casefold(),where+'/linetype')
    def block_native(name,stack):
        if name in stack or len(stack)>12:raise ValueError('Native display block recursion unsupported')
        block=facts.get('dimension_blocks',{}).get(name)
        if block is None:raise ValueError('Complete actual native dimension display geometry required')
        rows=[]
        for item in block['entities']:
            groups=item['groups']
            def get(code,default=None):
                found=[value for key,value in groups if key==code]
                if len(found)>1:raise ValueError('Repeated native display group needs an adapter')
                return found[0] if found else default
            kind=get(0);common=[kind,get(8,'0'),get(62,256),get(370,-1),get(6,'BYLAYER').casefold(),get(48,1),get(60,0)]
            compare_layer(get(8,'0'),'display-layer/'+get(8,'0'))
            if get(39,0)!=0 or get(210,[0,0,1])!=[0,0,1] or get(420) is not None or get(440,0x02000000) not in {0x01000000,0x02000000}:
                raise ValueError('Unsupported native display thickness/color/transparency/normal')
            if kind=='TEXT' and (get(51,0) or get(71,0)):
                raise ValueError('Native cached TEXT skew/mirror needs an adapter')
            if kind=='LINE':geometry=[get(10),get(11)]
            elif kind=='POINT':geometry=[get(10)]
            elif kind=='SOLID':geometry=[get(10),get(11),get(12),get(13)]
            elif kind=='CIRCLE':geometry=[get(10),get(40)]
            elif kind=='ARC':geometry=[get(10),get(40),get(50),get(51)]
            elif kind=='ELLIPSE':geometry=[get(10),get(11),get(40),get(41),get(42)]
            elif kind=='TEXT':geometry=[get(10),get(1,''),get(40),get(7,'Standard'),get(50,0),get(41,1),get(72,0),get(73,0)]
            elif kind=='MTEXT':
                if get(90,0):raise ValueError('Native cached MTEXT background needs an adapter')
                if re.search(r'\\[fF]',get(1,'')):raise ValueError('Inline native font selection needs its own verified font adapter')
                if any(code==3 for code,_ in groups):raise ValueError('Chunked native MTEXT needs a dedicated adapter')
                geometry=[get(10),get(1,''),get(40),get(7,'Standard'),get(41,0),get(71,1),get(11,[1,0,0])]
            elif kind=='INSERT':
                scales=[get(41,1),get(42,1),get(43,1)]
                if min(scales)<=0 or abs(scales[0]-scales[1])>1e-8 or scales[2]!=1 or get(66,0):raise ValueError('Display INSERT transform/attributes unsupported')
                geometry=[get(10),scales,get(50,0),block_native(get(2),(*stack,name))]
            else:raise ValueError('Native display object needs an exact adapter: '+str(kind))
            rows.append(common+[geometry])
        return [block['origin'],rows]

    def block_source(name,stack):
        if name in stack or len(stack)>12:raise ValueError('Source display block recursion unsupported')
        block=doc.blocks.get(name)
        if block.block.is_xref:raise ValueError('Source dimension display XREF unsupported')
        rows=[]
        for entity in block:
            kind=entity.dxftype();d=entity.dxf
            common=[kind,d.get('layer','0'),d.get('color',256),d.get('lineweight',-1),d.get('linetype','BYLAYER').casefold(),d.get('ltscale',1),d.get('invisible',0)]
            if attr(d,'thickness',0)!=0 or d.hasattr('true_color') or d.get('transparency',0x02000000) not in {0x01000000,0x02000000}:
                raise ValueError('Source display visual attributes need a dedicated adapter')
            if list(attr(d,'extrusion',(0,0,1)))!=[0,0,1]:
                raise ValueError('Source display extrusion must use positive WCS Z')
            if kind=='TEXT' and (d.get('oblique',0) or d.get('text_generation_flag',0)):
                raise ValueError('Source cached TEXT skew/mirror needs an adapter')
            if kind=='LINE':geometry=[point(d.start),point(d.end)]
            elif kind=='POINT':geometry=[point(d.location)]
            elif kind=='SOLID':geometry=[point(d.vtx0),point(d.vtx1),point(d.vtx2),point(d.vtx3)]
            elif kind=='CIRCLE':geometry=[point(d.center),d.radius]
            elif kind=='ARC':geometry=[point(d.center),d.radius,math.radians(d.start_angle),math.radians(d.end_angle)]
            elif kind=='ELLIPSE':geometry=[point(d.center),point(d.major_axis),d.ratio,d.start_param,d.end_param]
            elif kind=='TEXT':geometry=[point(d.insert),d.text,d.height,d.get('style','Standard'),math.radians(d.get('rotation',0)),d.get('width',1),d.get('halign',0),d.get('valign',0)]
            elif kind=='MTEXT':
                if d.get('bg_fill',0):raise ValueError('Source cached MTEXT background needs an adapter')
                if re.search(r'\\[fF]',entity.text):raise ValueError('Inline source font selection needs a verified adapter')
                angle=math.radians(entity.get_rotation())
                geometry=[point(d.insert),entity.text,d.char_height,d.get('style','Standard'),d.get('width',0),d.get('attachment_point',1),point(d.get('text_direction',(math.cos(angle),math.sin(angle),0)))]
            elif kind=='INSERT':
                scales=[d.get('xscale',1),d.get('yscale',1),d.get('zscale',1)]
                if min(scales)<=0 or abs(scales[0]-scales[1])>1e-8 or scales[2]!=1 or entity.attribs:raise ValueError('Source display INSERT transform/attributes unsupported')
                geometry=[point(d.insert),scales,math.radians(d.get('rotation',0)),block_source(d.name,(*stack,name))]
            else:raise ValueError('Source display object needs an exact adapter: '+kind)
            if kind in {'TEXT','MTEXT'}:fonts.add(d.get('style','Standard'))
            rows.append(common+[geometry])
        return [point(block.block.dxf.base_point),rows]
    fonts=set()
    for handle,entity in source.items():
        row=native[handle];kind=entity.dxftype();where='model/'+handle
        if kind not in model_types:raise ValueError('Source object lacks exact native comparison adapter: '+kind)
        wanted=model_types[kind]
        if row['ObjectName'] not in (wanted if isinstance(wanted,set) else {wanted}):raise ValueError('Native/source entity type mismatch')
        equal(row['effective_lineweight_mm'],source_context.resolve_all(entity).lineweight,where+'/effective_lineweight_mm')
        groups=row.get('native_entity_groups')
        if not groups:raise ValueError('Original native entity definition groups required for paper correspondence')
        def native_group(code,default=None):
            values=[value for key,value in groups if key==code]
            if len(values)>1:raise ValueError('Repeated native model group needs an adapter')
            return values[0] if values else default
        if native_group(39,0)!=0 or native_group(420) is not None or native_group(440,0x02000000) not in {0x01000000,0x02000000}:
            raise ValueError('Native model thickness/true-color/alpha needs a dedicated paper adapter')
        if native_group(210,[0,0,1])!=[0,0,1]:raise ValueError('Native model non-WCS normal unsupported')
        if row['effective_linetype'].casefold()!='continuous':raise ValueError('Native non-continuous line pattern needs an exact native pattern adapter')
        if kind=='TEXT' and any(native_group(code,0) for code in (51,71,72,73)):
            raise ValueError('Actual native TEXT alignment/oblique/mirror unsupported')
        if kind=='MTEXT' and native_group(90,0):raise ValueError('Actual native MTEXT background fill unsupported')
        if kind=='MTEXT' and re.search(r'\\[fF]',row.get('TextString','')):raise ValueError('Actual inline font selection needs a verified adapter')
        if kind=='DIMENSION' and any(native_group(code,0) for code in (51,52,53)):
            raise ValueError('Actual native DIMENSION orientation/oblique override unsupported')
        if entity.dxf.get('extrusion',(0,0,1))!=(0,0,1):
            equal(point(entity.dxf.get('extrusion',(0,0,1))),[0,0,1],where+'/normal')
        if attr(entity.dxf,'thickness',0)!=0 or entity.dxf.hasattr('true_color') or entity.dxf.hasattr('transparency'):
            raise ValueError('Source thickness/true-color/transparency needs a dedicated native paper adapter')
        check(row,{'Layer':entity.dxf.layer,'Lineweight':entity.dxf.get('lineweight',-1),
            'Color':entity.dxf.get('color',256),'Visible':not bool(entity.dxf.get('invisible',0)),
            'LinetypeScale':entity.dxf.get('ltscale',1)},where)
        equal(row['Linetype'].casefold(),entity.dxf.get('linetype','BYLAYER').casefold(),where+'/linetype')
        compare_layer(entity.dxf.layer,where+'/layer')
        if kind=='LINE':values={'StartPoint':point(entity.dxf.start),'EndPoint':point(entity.dxf.end)}
        elif kind in {'CIRCLE','ARC'}:
            values={'Center':point(entity.dxf.center),'Radius':entity.dxf.radius}
            if kind=='ARC':
                # Native API may return -pi/2 where the DXF stores 270 degrees.
                for key,angle in [('StartAngle',entity.dxf.start_angle),('EndAngle',entity.dxf.end_angle)]:
                    delta=(row[key]-math.radians(angle)+math.pi)%(2*math.pi)-math.pi
                    equal(delta,0.,where+'/'+key)
        elif kind=='ELLIPSE':
            values={'Center':point(entity.dxf.center),'MajorAxis':point(entity.dxf.major_axis),
                'RadiusRatio':entity.dxf.ratio,'StartParameter':entity.dxf.start_param,'EndParameter':entity.dxf.end_param}
        elif kind=='LWPOLYLINE':
            if entity.dxf.get('elevation',0)!=0:raise ValueError('Source polyline elevation must be zero in WCS XY scope')
            points=list(entity.get_points('xyseb'))
            values={'Coordinates':[v for p in points for v in p[:2]],'Closed':bool(entity.closed),
                'Bulges':[p[4] for p in points],'VertexWidths':[[p[2],p[3]] for p in points],
                'ConstantWidth':entity.dxf.get('const_width',0)}
        elif kind in {'TEXT','MTEXT'}:
            style=entity.dxf.get('style','Standard');fonts.add(style)
            values={'TextString':entity.dxf.text if kind=='TEXT' else entity.text,
                'InsertionPoint':point(entity.dxf.insert),'Height':entity.dxf.height if kind=='TEXT' else entity.dxf.char_height,
                'StyleName':style}
            if kind=='TEXT':
                if entity.dxf.get('halign',0) or entity.dxf.get('valign',0) or entity.dxf.get('oblique',0) or entity.dxf.get('text_generation_flag',0):
                    raise ValueError('Nondefault TEXT alignment/oblique/mirror needs a native adapter')
                values.update(Rotation=math.radians(entity.dxf.get('rotation',0)),ScaleFactor=entity.dxf.get('width',1))
            else:
                values.update(Width=entity.dxf.width,AttachmentPoint=entity.dxf.attachment_point)
                angle=math.radians(entity.get_rotation())
                equal(native_group(11,[1,0,0]),point(entity.dxf.get('text_direction',(math.cos(angle),math.sin(angle),0))),where+'/text_direction')
                if entity.dxf.get('bg_fill',0):raise ValueError('Source model MTEXT background needs an adapter')
        else:
            if entity.dimtype not in {0,1}:raise ValueError('Native dimension comparison supports linear/aligned definitions')
            equal(native_group(10),point(entity.dxf.defpoint),where+'/definition_line_point')
            if entity.dimtype==0:
                delta=(native_group(50,0)-math.radians(entity.dxf.get('angle',0))+math.pi)%(2*math.pi)-math.pi
                equal(delta,0.,where+'/definition_angle')
            override=entity.override();style=override.get('dimtxsty','Standard');fonts.add(style)
            if (facts['variables']['LWDEFAULT']/100!=source_context.default_lineweight()
                    and any(override.get(key)==-3 for key in ('dimlwd','dimlwe'))):
                raise ValueError('Source exporter default pen differs from the live native default; explicit project mapping required')
            values={'ExtLine1Point':point(entity.dxf.defpoint2),'ExtLine2Point':point(entity.dxf.defpoint3),
                'TextPosition':point(entity.dxf.text_midpoint),'Measurement':entity.get_measurement(),
                'LinearScaleFactor':override.get('dimlfac',1),'TextHeight':override.get('dimtxt',2.5),
                'ScaleFactor':override.get('dimscale',1),'TextStyle':style,
                'DimensionLineWeight':override.get('dimlwd',-2),'ExtensionLineWeight':override.get('dimlwe',-2),
                'UnitsFormat':override.get('dimlunit',2),'PrimaryUnitsPrecision':override.get('dimdec',2)}
            native_block=row.get('native_geometry_block')
            if not native_block:raise ValueError('Actual native dimension display block identity required')
            equal(block_native(native_block,()),block_source(entity.dxf.geometry,()),where+'/display_geometry')
        check(row,values,where)
    for style in fonts:
        if style not in facts['text_styles']:raise ValueError('Actual native font declaration missing')
        record=facts['text_styles'][style];source_style=doc.styles.get(style)
        family,italic,bold=source_style.get_extended_font_data()
        details=record.get('font_details')
        if not family or not isinstance(details,dict):
            raise ValueError('Explicit source and actual native font family/bold/italic declarations required')
        from .native_delivery import verify_font_resource
        verify_font_resource(record['FontFile'],details.get('typeface',''),source_style.dxf.font,family)
        equal(details.get('italic'),italic,'font-italic/'+style)
        equal(details.get('bold'),bold,'font-bold/'+style)
        xdata=record.get('font_xdata')
        if not isinstance(xdata,(list,tuple)) or len(xdata)!=2 or not xdata[0] or not xdata[1] or len(xdata[0])!=len(xdata[1]):
            raise ValueError('Actual native ACAD font family/1071 flags readback required')
        actual_font_tags=[(code,value) for code,value in zip(*xdata) if code!=1001]
        source_font_tags=[(tag.code,tag.value) for tag in source_style.get_xdata('ACAD')]
        # Compare the actual opaque packed flags exactly. This checks charset,
        # pitch/family and bold/italic without guessing undocumented bit shifts.
        equal(actual_font_tags,source_font_tags,'font-packed-flags/'+style)
        if source_style.dxf.flags & 5:raise ValueError('Source vertical/shape text styles need a dedicated native adapter')
        check(record,{'Height':source_style.dxf.height,'Width':source_style.dxf.width,
            'ObliqueAngle':math.radians(source_style.dxf.oblique),'TextGenerationFlag':source_style.dxf.generation_flags},'text-style/'+style)
        equal(Path(record['BigFontFile']).name.casefold(),Path(source_style.dxf.bigfont).name.casefold(),'bigfont/'+style)
    return {'passed':not differences,'differences':differences,'native_model_objects_compared':len(native),
        'dimension_display_blocks_compared':len(facts.get('dimension_blocks',{})),
        'scope':'actual native supported model definitions, display geometry, layers and font-file declarations versus original DXF',
        'native_autocad_plot_verified':False,'reconstructed_dxf_used':False}


def correspondence_preview(snapshot,source,target):
    """Render full original-source extents only after actual native equivalence.

    This is explicitly an offline correspondence preview, not native Export.
    The caller must still recheck live facts and file hashes before delivery.
    """
    import ezdxf
    from ezdxf import bbox
    from .qa import file_hash
    from .pdf_export import render_pdf
    import pypdfium2 as pdfium
    source=Path(source).resolve();target=Path(target).resolve()
    if target.exists() or target.suffix.lower()!='.png':raise ValueError('New PNG preview path required')
    native_hash=snapshot['file_sha256'];source_hash=file_hash(source)
    if file_hash(Path(snapshot['path']))!=native_hash:raise ValueError('Native file changed before correspondence preview')
    doc=ezdxf.readfile(source);compared=compare({'actual':snapshot['facts']},doc)
    if not compared['passed']:raise ValueError('Native-source geometry differs: '+str(compared['differences']))
    bounds=bbox.extents(doc.modelspace(),fast=False)
    if not bounds.has_data:raise ValueError('Full source extents unavailable')
    x0,y0=bounds.extmin.x,bounds.extmin.y;x1,y1=bounds.extmax.x,bounds.extmax.y
    pad=max(x1-x0,y1-y0)*.05+1
    window=[x0-pad,y0-pad,x1+pad,y1+pad]
    scale=max((window[2]-window[0])/400,(window[3]-window[1])/277)*1.001
    data,settings=render_pdf(source,[420,297],window,scale,10)
    pdf=pdfium.PdfDocument(data);page=pdf[0];bitmap=page.render(scale=1.5)
    try:bitmap.to_pil().save(target)
    finally:bitmap.close();page.close();pdf.close()
    if file_hash(source)!=source_hash or file_hash(Path(snapshot['path']))!=native_hash:
        raise ValueError('Native/source files changed during correspondence preview')
    return {'path':str(target),'sha256':file_hash(target),'kind':'native_source_correspondence',
        'native_export':False,'full_model_coverage_verified':True,'native_file_sha256':native_hash,
        'source_path':str(source),'source_file_sha256':source_hash,'native_snapshot_sha256':snapshot['snapshot_sha256'],
        'comparison':compared,'settings':settings,'source_model_bbox':[x0,y0,x1,y1],
        'limits':'Offline full-source preview after complete supported native equivalence; not a native CAD paper plot'}

