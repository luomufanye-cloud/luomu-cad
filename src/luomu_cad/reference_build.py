"""Deterministic editable DXF construction from an independently reviewed inventory."""
import math
import ezdxf
from ezdxf.colors import rgb2int,float2transparency
from .redraw_quality import coordinate_basis


def build(inventory):
    if inventory.get('extraction_complete') is False:
        raise ValueError('PDF_EXTRACTION_INCOMPLETE: resolve source extraction findings before building a complete drawing')
    objects=inventory.get('objects')
    if not isinstance(objects,list) or not objects:
        raise ValueError('Nonempty source inventory required')
    coordinate_basis(inventory)
    # Reject nonfinite data before passing it into CAD constructors.
    import json
    json.dumps(inventory,allow_nan=False)
    doc=ezdxf.new('R2018',setup=True);doc.units=inventory['units'];m=doc.modelspace();mapping={}
    def add_entity(m,kind,value,paint,key):
        attrs={'true_color':rgb2int(paint['rgb']),'lineweight':paint['lineweight'],
               'transparency':float2transparency(1-paint['opacity']),'linetype':paint['linetype']}
        if paint['linetype'] not in doc.linetypes:raise ValueError('Source linetype requires a defined pattern: '+paint['linetype'])
        if kind=='CLIPPED':
            from ezdxf.xclip import XClip
            from shapely.geometry import Polygon
            polygon=Polygon(value['clip_polygon'])
            if not polygon.is_valid or polygon.area<=0:raise ValueError('Valid nonempty clipping polygon required')
            child=value['entity']
            if child['kind'] not in ('LINE','ARC','CIRCLE','LWPOLYLINE','SPLINE','TEXT','HATCH'):
                raise ValueError('Unsupported clipped entity')
            block=doc.blocks.new('SOURCE-CLIP-'+str(key))
            add_entity(block,child['kind'],child['expected'],paint,str(key)+'-child')
            entity=m.add_blockref(block.name,(0,0,0),dxfattribs={**attrs,'transparency':float2transparency(0)})
            clip=XClip(entity);clip.set_block_clipping_path(value['clip_polygon']);clip.enable_clipping()
            doc.header['$XCLIPFRAME']=0
        elif kind=='LINE':entity=m.add_line(value['start'],value['end'],dxfattribs=attrs)
        elif kind=='ARC':entity=m.add_arc(**{k:value[k] for k in ('center','radius','start_angle','end_angle')},dxfattribs=attrs)
        elif kind=='CIRCLE':entity=m.add_circle(value['center'],value['radius'],dxfattribs=attrs)
        elif kind=='LWPOLYLINE':entity=m.add_lwpolyline(value['points'],format='xyb',close=value['closed'],dxfattribs=attrs)
        elif kind=='SPLINE':
            entity=m.add_open_spline(value['control_points'],degree=value['degree'],knots=value['knots'],dxfattribs=attrs)
            if value.get('weights'):entity.weights=value['weights'];entity.dxf.flags|=4
        elif kind=='TEXT':
            name='SOURCE-TEXT-'+str(key)
            style=doc.styles.new(name,dxfattribs={'font':value['font']})
            if value.get('font_family'):style.set_extended_font_data(value['font_family'])
            entity=m.add_text(value['text'],dxfattribs={**attrs,'style':name,'insert':value['at'],
                             'height':value['height'],'width':value['width'],'rotation':value['rotation']})
        elif kind=='DIMENSION':
            a,b=value['start'],value['end']
            if math.dist(a,b)==0:raise ValueError('Nonzero dimension required')
            if value.get('display_text') not in (None,''):
                try:float(value['display_text'])
                except (TypeError,ValueError):raise ValueError('Formatted dimension display needs an explicit formatter')
            dim=m.add_linear_dim(base=value['line_at'],p1=a,p2=b,
                angle=math.degrees(math.atan2(b[1]-a[1],b[0]-a[0])),
                override={**value['style'],'dimlfac':value['dimlfac']},dxfattribs=attrs)
            dim.render();entity=dim.dimension
        elif kind=='HATCH':
            if not value['solid']:raise ValueError('Patterned HATCH needs explicit pattern data')
            entity=m.add_hatch(dxfattribs=attrs);entity.dxf.hatch_style=value['hatch_style']
            for loop in value['loops']:
                entity.paths.add_polyline_path(loop['points'],is_closed=loop['closed'],flags=1 if loop['external'] else 0)
        else:raise ValueError('Unsupported source entity: '+str(kind))
        return entity
    for obj in objects:
        sid=obj['id'];kind=obj['kind'];value=obj['expected'];paint=obj['presentation']
        if not isinstance(sid,str) or not sid or sid in mapping:raise ValueError('Distinct source IDs required')
        entity=add_entity(m,kind,value,paint,len(mapping))
        mapping[sid]=entity.dxf.handle
    return doc,mapping
