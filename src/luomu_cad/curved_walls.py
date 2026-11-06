"""Exact circular-wall boundaries with explicitly measured arc-length openings."""
import math
import ezdxf
from .plan import number, point


def normalize(spec):
    if set(spec)-{'walls'}:raise ValueError('Unknown curved-wall specification fields')
    walls=spec.get('walls')
    if not isinstance(walls,list) or not 1<=len(walls)<=100:raise ValueError('Require 1..100 circular walls')
    result=[];ids=set()
    for w in walls:
        if set(w)-{'id','center','radius','thickness','start_angle','sweep_angle','openings'}:
            raise ValueError('Unknown curved-wall fields')
        wid=w.get('id')
        if not isinstance(wid,str) or not wid or wid in ids:raise ValueError('Distinct wall IDs required')
        ids.add(wid)
        center=point(w.get('center'),'center');radius=number(w.get('radius'),'radius',1)
        thickness=number(w.get('thickness'),'thickness',1)
        if radius<=thickness/2:raise ValueError('Inside radius must be positive')
        start=number(w.get('start_angle'),'start angle')%360
        sweep=number(w.get('sweep_angle'),'sweep angle',.001)
        if sweep>360:raise ValueError('Sweep must be at most 360 degrees')
        length=radius*math.radians(sweep);openings=[];oids=set()
        raw=w.get('openings',[])
        if not isinstance(raw,list) or len(raw)>200:raise ValueError('At most 200 arc-length openings')
        for op in raw:
            if set(op)-{'id','offset','arc_width'}:raise ValueError('Opening requires measured arc_width, not chord width')
            oid=op.get('id')
            if not isinstance(oid,str) or not oid or oid in oids:raise ValueError('Distinct opening IDs required')
            oids.add(oid)
            offset=number(op.get('offset'),'arc offset',0);width=number(op.get('arc_width'),'arc width',1)
            if offset+width>length+1e-8:raise ValueError('Opening outside arc wall')
            if width>=length-1e-8:raise ValueError('Opening removes the entire wall')
            openings.append({'id':oid,'offset':offset,'arc_width':width})
        openings.sort(key=lambda x:x['offset'])
        if any(a['offset']+a['arc_width']>=b['offset']-1e-8 for a,b in zip(openings,openings[1:])):
            raise ValueError('Arc openings overlap or touch')
        result.append({'id':wid,'center':center,'radius':radius,'thickness':thickness,
                       'start_angle':start,'sweep_angle':sweep,'openings':openings})
    return {'walls':result}


def draw(spec):
    spec=normalize(spec);doc=ezdxf.new('R2018');doc.units=4
    doc.layers.new('CURVED-WALL',dxfattribs={'color':7,'lineweight':35})
    model=doc.modelspace();owners={};expected={}
    def keep(entity,fields,handles):
        handles.append(entity.dxf.handle);expected[entity.dxf.handle]={'type':entity.dxftype(),**fields}
    for w in spec['walls']:
        handles=[];owners[w['id']]=handles;start=w['start_angle'];r=w['radius'];cx,cy=w['center']
        inner,outer=r-w['thickness']/2,r+w['thickness']/2
        if w['sweep_angle']==360 and not w['openings']:
            for radius in (inner,outer):
                keep(model.add_circle((cx,cy),radius,dxfattribs={'layer':'CURVED-WALL'}),
                     {'center':[cx,cy,0],'radius':radius},handles)
            continue
        length=r*math.radians(w['sweep_angle']);cursor=0;intervals=[]
        for op in w['openings']:
            if op['offset']>cursor+1e-8:intervals.append((cursor,op['offset']))
            cursor=op['offset']+op['arc_width']
        if length>cursor+1e-8:intervals.append((cursor,length))
        # A full ring with a gap has no artificial seam at the start angle.
        if w['sweep_angle']==360 and len(intervals)>1 and intervals[0][0]==0 and intervals[-1][1]==length:
            intervals=[(intervals[-1][0],length+intervals[0][1])]+intervals[1:-1]
        for low,high in intervals:
            a=start+math.degrees(low/r);b=start+math.degrees(high/r)
            for radius in (inner,outer):
                fields={'center':[cx,cy,0],'radius':radius,'start_angle':a%360,'end_angle':b%360}
                keep(model.add_arc(**fields,dxfattribs={'layer':'CURVED-WALL'}),fields,handles)
            for angle in (a,b):
                ux,uy=math.cos(math.radians(angle)),math.sin(math.radians(angle))
                p=[cx+inner*ux,cy+inner*uy,0];q=[cx+outer*ux,cy+outer*uy,0]
                keep(model.add_line(p,q,dxfattribs={'layer':'CURVED-WALL'}),{'start':p,'end':q},handles)
    return doc,spec,owners,expected


def verify(path,expected):
    doc=ezdxf.readfile(path);entities={e.dxf.handle:e for e in doc.modelspace()};errors=[]
    if set(entities)!=set(expected):errors.append('Curve object coverage changed')
    if doc.units!=4:errors.append('Units must be mm')
    for handle,fields in expected.items():
        entity=entities.get(handle)
        if entity is None:continue
        if entity.dxftype()!=fields['type']:errors.append('Type changed: '+handle);continue
        for key,value in fields.items():
            if key=='type':continue
            actual=entity.dxf.get(key)
            distance=math.dist(actual,value) if isinstance(value,list) else abs(actual-value)
            if not math.isfinite(distance) or distance>1e-7:errors.append('Curve readback mismatch: '+handle+':'+key)
    return {'ok':not errors,'errors':errors,'checked_entities':len(expected)}
