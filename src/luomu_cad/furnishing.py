"""Explicit plan components, circulation checks and scoped dimension chains."""
import math
import re
from shapely import affinity
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union

KINDS={'bed','sofa','table','chair','cabinet','sink','toilet','shower','hob','fridge'}


def footprint(item):
    return affinity.rotate(box(0,0,item['width'],item['depth']),item.get('rotation',0),origin=(0,0))


def placed(item):
    return affinity.translate(footprint(item),*item['at'])


def validate_furnishing(spec):
    from .plan import number,point,wall_regions,opening_basis
    kind=spec.get('deliverable','geometry_plan')
    if kind not in {'geometry_plan','furnished_plan'}:raise ValueError('Unknown deliverable')
    items=spec.setdefault('furniture',[])
    if not isinstance(items,list) or len(items)>300:raise ValueError('At most 300 furniture items')
    if kind=='furnished_plan' and not items:
        raise ValueError('INCOMPLETE_PLAN: furnished_plan requires explicit furniture')
    ids=set()
    for item in items:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',str(item.get('id',''))) or item['id'] in ids:
            raise ValueError('Furniture IDs must be unique ASCII identifiers')
        ids.add(item['id'])
        if item.get('kind') not in KINDS:raise ValueError('Unsupported furniture kind')
        item['at']=point(item.get('at'),'furniture location')
        for key in ('width','depth'):item[key]=number(item.get(key),key,1)
        item['rotation']=number(item.get('rotation',0),'furniture rotation')%360
    requirements=spec.get('furniture_requirements',{})
    if kind=='furnished_plan' and (not requirements or not spec.get('floor_boundary') or not spec.get('clear_zones')):
        raise ValueError('INCOMPLETE_PLAN: declare floor_boundary, room furniture_requirements and clear_zones')
    rooms={r['id']:r for r in spec.get('rooms',[])}
    for room,required in requirements.items():
        if room not in rooms or not isinstance(required,list) or not required or set(required)-KINDS:
            raise ValueError('Invalid room furniture_requirements')
        present={i['kind'] for i in items if i.get('room')==room}
        if set(required)-present:raise ValueError(f'INCOMPLETE_PLAN: missing furniture in {room}: {sorted(set(required)-present)}')
    if kind=='furnished_plan' and set(requirements)!=set(rooms):
        raise ValueError('INCOMPLETE_PLAN: every declared room needs a furniture requirement')
    zones=[]
    for zone in spec.get('clear_zones',[]):
        if not zone.get('id'):raise ValueError('Clear zone needs an ID')
        x,y=point(zone.get('at'),'clear zone location')
        zones.append((zone['id'],box(x,y,x+number(zone.get('width'),'clear width',1),y+number(zone.get('depth'),'clear depth',1))))
    if not items:return
    walls=unary_union(list(wall_regions(spec).values()))
    floor=Polygon(spec['floor_boundary']) if spec.get('floor_boundary') else None
    cells=[]
    if floor is not None:
        interior=floor.difference(unary_union(list(wall_regions(spec,False).values())))
        cells=list(interior.geoms) if hasattr(interior,'geoms') else [interior]
    shapes=[]
    wall_map={w['id']:w for w in spec['walls']}
    swings=[]
    for op in spec['openings']:
        if op['kind']!='door':continue
        p,u,n=opening_basis(wall_map[op['wall']],op)
        left=op.get('hand','left')=='left';w=op['width']
        sign=1 if op.get('swing_side','left')=='left' else -1
        hx,hy=p if left else (p[0]+w*u[0],p[1]+w*u[1])
        arc=[]
        for k in range(31):
            a=math.radians(k*3+(0 if left else 90))
            arc.append((hx+w*(math.cos(a)*u[0]+sign*math.sin(a)*n[0]),hy+w*(math.cos(a)*u[1]+sign*math.sin(a)*n[1])))
        swings.append((op['id'],Polygon([(hx,hy),*arc]).buffer(0.5)))
    for item in items:
        shape=placed(item)
        if walls.intersection(shape).area>1:raise ValueError(f"Furniture {item['id']} intersects a wall")
        if floor is not None and not floor.buffer(0.01).covers(shape):raise ValueError(f"Furniture {item['id']} is outside floor_boundary")
        if item.get('room'):
            if item['room'] not in rooms:raise ValueError('Furniture references an unknown room')
            matches=[c for c in cells if c.contains(Point(rooms[item['room']]['at']))]
            if floor is not None and (len(matches)!=1 or not matches[0].buffer(0.01).covers(shape)):
                raise ValueError(f"Furniture {item['id']} is outside its declared room")
        for name,other in [*shapes,*zones,*swings]:
            if shape.intersection(other).area>1:raise ValueError(f"Furniture {item['id']} overlaps item/clearance/door {name}")
        shapes.append((item['id'],shape))


def draw_furnishing(doc,spec,add,selected):
    for item in spec.get('furniture',[]):
        group='furniture:'+item['id']
        if selected is not None and group not in selected:continue
        name='LUOMU_F_'+item['id'];w,d=item['width'],item['depth'];kind=item['kind']
        block=doc.blocks.new(name)
        def rect(x,y,a,b):block.add_lwpolyline([(x,y),(a,y),(a,b),(x,b)],close=True)
        def line(a,b):block.add_line(a,b)
        rect(0,0,w,d)
        if kind=='bed':
            rect(w*.05,d*.78,w*.46,d*.96);rect(w*.54,d*.78,w*.95,d*.96)
            line((0,d*.7),(w,d*.7))
        elif kind=='sofa':
            rect(w*.06,d*.12,w*.94,d*.8)
            line((w/3,d*.12),(w/3,d*.8));line((2*w/3,d*.12),(2*w/3,d*.8))
            line((w*.06,d*.8),(w*.94,d*.8))
        elif kind in {'sink','toilet'}:
            block.add_ellipse((w/2,d*.5),major_axis=(w*.32,0,0),ratio=min(1,d*.28/(w*.32)))
            if kind=='toilet':rect(w*.1,d*.8,w*.9,d*.98)
        elif kind=='hob':
            for x in (w*.3,w*.7):block.add_circle((x,d*.5),min(w,d)*.16)
        elif kind=='shower':
            line((0,0),(w,d));line((0,d),(w,0))
            block.add_circle((w*.8,d*.8),min(w,d)*.05)
        elif kind in {'cabinet','fridge'}:
            line((0,0),(w,d));line((0,d),(w,0))
        elif kind=='chair':line((0,d*.8),(w,d*.8))
        add(doc.modelspace().add_blockref(name,item['at'],dxfattribs={
            'rotation':item.get('rotation',0),'layer':'FURNITURE'}),group)


def draw_dimension_chains(spec,dimension,regions,scale):
    raw=spec.get('chains')
    if not raw:return
    options=raw if isinstance(raw,dict) else {}
    ids=options.get('wall_ids',list(regions))
    if not ids or set(ids)-set(regions):raise ValueError('chains.wall_ids requires existing walls')
    # Measure outer faces of explicitly selected walls, never all axis points.
    selected=unary_union([regions[i] for i in ids])
    x0,y0,x1,y1=selected.bounds
    occupied=unary_union(list(regions.values())).bounds
    sides=options.get('sides',['bottom','left'])
    if set(sides)-{'bottom','left','top','right'}:raise ValueError('Unknown dimension chain side')
    levels=options.get('levels',['overall'])
    if not levels or set(levels)-{'openings','axes','overall'}:raise ValueError('Unknown dimension chain level')
    from .plan import opening_basis,number
    walls={w['id']:w for w in spec['walls']}
    for side in sides:
        horizontal=side in {'bottom','top'}
        lo,hi=(x0,x1) if horizontal else (y0,y1)
        anchor=(y0 if side=='bottom' else y1) if horizontal else (x0 if side=='left' else x1)
        for level_index,level in enumerate(levels):
            if level=='overall':ticks=[lo,hi]
            elif level=='axes':
                ticks=options.get('axis_x' if horizontal else 'axis_y')
                if not ticks:raise ValueError('Axis chain needs explicit axis_x/axis_y references')
                ticks=[number(t,'axis tick') for t in ticks]
            else:
                ticks=[lo,hi]
                for op in spec['openings']:
                    if op['wall'] not in ids:continue
                    p,u,n=opening_basis(walls[op['wall']],op)
                    if (horizontal and abs(u[1])>1e-7) or (not horizontal and abs(u[0])>1e-7):continue
                    if abs((p[1] if horizontal else p[0])-anchor)>walls[op['wall']]['thickness']/2+0.1:continue
                    ticks.extend([p[0] if horizontal else p[1],(p[0]+u[0]*op['width']) if horizontal else (p[1]+u[1]*op['width'])])
            ticks=sorted(set(ticks))
            if level=='openings' and len(ticks)==2:continue
            if len(ticks)<2 or ticks[0]<lo-.01 or ticks[-1]>hi+.01:raise ValueError('Chain references outside selected envelope')
            # Lines clear the full visible geometry (e.g. balcony), but endpoints
            # still measure only the selected building envelope.
            margin=(12+10*level_index)*scale
            line_at=(occupied[1]-margin if side=='bottom' else occupied[3]+margin) if horizontal else (occupied[0]-margin if side=='left' else occupied[2]+margin)
            for a,b in zip(ticks,ticks[1:]):
                p1,p2=((a,anchor),(b,anchor)) if horizontal else ((anchor,a),(anchor,b))
                distance=line_at-anchor if horizontal else anchor-line_at
                dimension(p1,p2,distance,'overall-dim')
