"""Generate straight-wall architectural plans with project-owned geometry rules.

Inputs are millimetres. Geometry is computed here using the Shapely/ezdxf APIs;
there is no dependency on another CAD application's server or drawing templates.
"""
from __future__ import annotations
import copy
import math
from pathlib import Path

import ezdxf
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union


def number(value, name, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number in mm")
    value = float(value)
    if abs(value) > 1_000_000 or (minimum is not None and value < minimum):
        raise ValueError(f"{name} outside supported range")
    return value


def point(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} requires [x, y]")
    return tuple(number(v, name) for v in value)


def spans(wall):
    pts = wall["axis"] + ([wall["axis"][0]] if wall.get("closed") else [])
    offset = 0.
    result = []
    for a, b in zip(pts, pts[1:]):
        length = math.dist(a, b)
        result.append((offset, offset + length, a, ((b[0]-a[0])/length, (b[1]-a[1])/length)))
        offset += length
    return result


def opening_basis(wall, opening):
    start, end = opening["offset"], opening["offset"] + opening["width"]
    for low, high, a, u in spans(wall):
        if start >= low + 1e-5 and end <= high - 1e-5:
            return ((a[0]+(start-low)*u[0], a[1]+(start-low)*u[1]), u, (-u[1], u[0]))
    raise ValueError(f"Opening {opening['id']} crosses a corner/end or is outside its wall")


def validate_spec(spec):
    spec = copy.deepcopy(spec)
    if spec.get("lang", "zh") not in {"zh", "en"}:
        raise ValueError("lang supports zh or en")
    walls = spec.get("walls", [])
    if not isinstance(walls, list) or not 1 <= len(walls) <= 100:
        raise ValueError("walls requires 1..100 straight-polyline walls")
    ids, wall_map = set(), {}
    for wall in walls:
        identifier = wall.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            raise ValueError("Wall ids must be distinct nonempty strings")
        ids.add(identifier)
        if wall.get("justification", "center") != "center":
            raise ValueError("Only explicit centre-axis walls are supported in this release")
        wall["thickness"] = number(wall.get("thickness"), "thickness", 1)
        axis = wall.get("axis", [])
        if not isinstance(axis, list) or not 2 <= len(axis) <= 100:
            raise ValueError("Each wall needs 2..100 axis points")
        wall["axis"] = [point(p, "axis") for p in axis]
        if any(math.dist(a,b) < 1 for a,b in zip(wall["axis"], wall["axis"][1:])):
            raise ValueError("Wall segment must be at least 1 mm")
        if wall.get("closed") and (len(axis)<3 or not Polygon(wall["axis"]).is_valid or Polygon(wall["axis"]).area < 1):
            raise ValueError("Closed wall axis must form a valid polygon")
        path = wall["axis"] + ([wall["axis"][0]] if wall.get("closed") else [])
        if not LineString(path).is_simple:
            raise ValueError("Self-intersecting wall axes are unsupported")
        wall_map[identifier] = wall
    openings = spec.setdefault("openings", [])
    if not isinstance(openings, list) or len(openings)>200:
        raise ValueError("At most 200 openings")
    occupied, opening_ids = {}, set()
    for opening in openings:
        identifier = opening.get("id")
        if not isinstance(identifier,str) or not identifier or identifier in opening_ids:
            raise ValueError("Opening ids must be distinct nonempty strings")
        opening_ids.add(identifier)
        if opening.get("kind") not in {"door", "window", "sliding_door"} or opening.get("wall") not in wall_map:
            raise ValueError("Opening requires a known wall and kind door/window/sliding_door")
        for k, minimum in (("offset",0),("width",1)):
            opening[k]=number(opening.get(k), k, minimum)
        for k in ("height","sill"):
            if k in opening:
                opening[k]=number(opening[k], k, 0)
        opening_basis(wall_map[opening["wall"]], opening)
        if opening.get("hand","left") not in {"left","right"}:
            raise ValueError("Door hand must be left or right")
        if opening.get('swing_side','left') not in {'left','right'}:
            raise ValueError('swing_side must be left or right of the wall direction')
        if 'dimension_offset' in opening:opening['dimension_offset']=number(opening['dimension_offset'],'dimension offset')
        if 'tag_at' in opening:opening['tag_at']=point(opening['tag_at'],'opening tag location')
        interval=(opening["offset"],opening["offset"]+opening["width"])
        for low,high in occupied.setdefault(opening["wall"],[]):
            if max(low,interval[0]) < min(high,interval[1]) + 1:
                raise ValueError("Openings overlap or leave less than 1 mm between them")
        occupied[opening["wall"]].append(interval)
    room_ids=set()
    for room in spec.get("rooms",[]):
        if not room.get("id") or room["id"] in room_ids:
            raise ValueError("Room ids must be unique")
        room_ids.add(room["id"])
        room["at"]=point(room.get("at"), "room location")
    for schedule in spec.get("schedules",[]):
        if schedule.get("kind") not in {"doors","windows","rooms"}:
            raise ValueError("Unsupported schedule kind")
        schedule["at"]=point(schedule.get("at"), "schedule location")
    boundary=spec.get('floor_boundary')
    if boundary is not None:
        spec['floor_boundary']=[point(p,'floor boundary') for p in boundary]
        shape=Polygon(spec['floor_boundary'])
        if not shape.is_valid or shape.area<1:raise ValueError('Invalid floor_boundary')
    from .furnishing import validate_furnishing
    validate_furnishing(spec)
    return spec


def wall_regions(spec, with_gaps=True):
    regions={}
    for wall in spec["walls"]:
        axis=wall["axis"]+([wall["axis"][0]] if wall.get("closed") else [])
        geometry=LineString(axis).buffer(wall["thickness"]/2,cap_style=2,join_style=2)
        # Earlier walls own intersections, giving subsequent partitions clean T joins.
        if regions:
            geometry=geometry.difference(unary_union(list(regions.values())))
        regions[wall["id"]]=geometry
    if with_gaps:
        wall_map={w["id"]:w for w in spec["walls"]}
        for op in spec["openings"]:
            wall=wall_map[op["wall"]]
            p,u,n=opening_basis(wall,op)
            h=wall["thickness"]/2+0.01
            cut=Polygon([(p[0]+x*u[0]+y*n[0],p[1]+x*u[1]+y*n[1]) for x,y in ((0,-h),(op["width"],-h),(op["width"],h),(0,h))])
            regions[wall["id"]]=regions[wall["id"]].difference(cut)
    return regions


def room_areas(spec):
    boundaries=([Polygon(spec['floor_boundary'])] if spec.get('floor_boundary') else
                [Polygon(w["axis"]) for w in spec["walls"] if w.get("closed")])
    if not boundaries:
        return {r["id"]:None for r in spec.get("rooms",[])}
    region=max(boundaries,key=lambda p:p.area).difference(unary_union(list(wall_regions(spec,False).values())))
    cells=list(region.geoms) if hasattr(region,"geoms") else [region]
    result={}
    for room in spec.get("rooms",[]):
        matches=[p for p in cells if p.contains(Point(room["at"]))]
        if len(matches)!=1:
            raise ValueError(f"Room {room['id']} location is not inside a measurable enclosure")
        result[room["id"]]=matches[0].area/1_000_000
    return result


def new_document():
    doc=ezdxf.new("R2013")
    doc.units=4
    doc.appids.add("LUOMU")
    for name,color,weight in (("WALL",7,35),("DOOR",7,18),("WINDOW",7,18),("TEXT",7,18),("DIM",7,13),("FURNITURE",7,13),("BORDER",7,35)):
        doc.layers.add(name,color=color,lineweight=weight)
    doc.styles.new("LUOMU",dxfattribs={"font":"msyh.ttc"})
    doc.styles.get("LUOMU").set_extended_font_data("Microsoft YaHei")
    return doc


def draw_groups(doc,spec,groups=None):
    selected=set(groups) if groups is not None else None
    model=doc.modelspace()
    owners={}
    scale=number(spec.get('sheet',{}).get('scale',50),'sheet scale',1)
    def add(entity,group):
        entity.set_xdata("LUOMU",[(1000,group)])
        owners.setdefault(group,[]).append(entity.dxf.handle)
        return entity
    def text(value,at,group,height=None):
        height=height if height is not None else 3.5*scale
        return add(model.add_text(str(value),dxfattribs={"insert":at,"height":height,"style":"LUOMU","layer":"TEXT"}),group)
    def dimension(a,b,base,group):
        from .annotations import short_extensions
        # Preserve the physical dimension-line side while normalizing reading direction.
        if (b[0]<a[0]-1e-8) or (abs(b[0]-a[0])<1e-8 and b[1]<a[1]):
            a,b=b,a
            base=-base
        dim=model.add_aligned_dim(p1=a,p2=b,distance=base,dimstyle="Standard",override={
            "dimtxt":3.5*scale,"dimasz":2*scale,"dimgap":0.8*scale,"dimtad":1,
            "dimclrd":7,"dimclre":7,"dimclrt":7,"dimtxsty":"LUOMU","dimlfac":1,
            "dimdec":0,**short_extensions(scale)})
        dim.dimension.dxf.layer="DIM"
        add(dim.dimension,group)
        dim.render()
    regions=wall_regions(spec)
    for key,region in regions.items():
        group="wall:"+key
        if selected is not None and group not in selected:
            continue
        polygons=list(region.geoms) if hasattr(region,"geoms") else [region]
        for polygon in polygons:
            if polygon.is_empty:
                continue
            for ring in [polygon.exterior,*polygon.interiors]:
                add(model.add_lwpolyline(list(ring.coords)[:-1],close=True,dxfattribs={"layer":"WALL"}),group)
    wall_map={w["id"]:w for w in spec["walls"]}
    for op in spec["openings"]:
        group="opening:"+op["id"]
        if selected is not None and group not in selected:
            continue
        p,u,n=opening_basis(wall_map[op["wall"]],op)
        def at(x,y):
            return (p[0]+x*u[0]+y*n[0],p[1]+x*u[1]+y*n[1])
        width=op["width"]
        if op["kind"]=="window":
            for y in (-wall_map[op["wall"]]["thickness"]/3,0,wall_map[op["wall"]]["thickness"]/3):
                add(model.add_line(at(0,y),at(width,y),dxfattribs={"layer":"WINDOW"}),group)
        elif op['kind']=='sliding_door':
            h=wall_map[op['wall']]['thickness']/4
            for x1,x2,y in ((0,width*.55,-h),(width*.45,width,h)):
                add(model.add_lwpolyline([at(x1,y-15),at(x2,y-15),at(x2,y+15),at(x1,y+15)],close=True,dxfattribs={'layer':'DOOR'}),group)
        else:
            left=op.get("hand","left")=="left"
            sign=1 if op.get('swing_side','left')=='left' else -1
            hinge=at(0 if left else width,0)
            add(model.add_line(hinge,at(0 if left else width,sign*width),dxfattribs={"layer":"DOOR"}),group)
            angle=math.degrees(math.atan2(u[1],u[0]))
            closed=angle+(0 if left else 180);opened=angle+sign*90
            start,end=(closed,opened) if sign*(1 if left else -1)>0 else (opened,closed)
            add(model.add_arc(hinge,width,start,end,dxfattribs={"layer":"DOOR"}),group)
        text(op.get("tag",op["id"]),op.get('tag_at',at(width/2,7*scale)),group)
        dimension(at(0,0),at(width,0),op.get('dimension_offset',-7*scale),group)
    from .furnishing import draw_furnishing
    draw_furnishing(doc,spec,add,selected)
    areas=room_areas(spec)
    for room in spec.get("rooms",[]):
        group="room:"+room["id"]
        if selected is None or group in selected:
            value=areas[room["id"]]
            text(room.get("name",room["id"]),room["at"],group,4*scale)
            text(f"{value:.2f} m²" if value is not None else "面积待核实",(room["at"][0],room["at"][1]-6*scale),group)
    if selected is None or "schedules" in selected:
        for table in spec.get("schedules",[]):
            kind=table["kind"]
            x,y=table["at"]
            text({"doors":"门表","windows":"窗表","rooms":"房间表"}[kind],(x,y),"schedules",4*scale)
            items=spec.get("rooms",[]) if kind=="rooms" else [o for o in spec["openings"] if o["kind"] in ({"door","sliding_door"} if kind=="doors" else {"window"})]
            for row,item in enumerate(items,1):
                entry=(f"{item['id']} {item.get('name','')} {areas[item['id']]:.2f} m²" if areas.get(item['id']) is not None else f"{item['id']} {item.get('name','')} 面积待核实") if kind=="rooms" else f"{item['id']} 宽 {item['width']:g} 高 {item.get('height','待核实')}"
                if kind=="windows":entry+=f" 窗台 {item.get('sill','待核实')}"
                text(entry,(x,y-7*scale*row),"schedules",3*scale)
    if selected is None or 'overall-dim' in selected:
        from .furnishing import draw_dimension_chains
        draw_dimension_chains(spec,dimension,regions,scale)
    if selected is None:
        all_points=[p for w in spec["walls"] for p in w["axis"]]
        xs,ys=zip(*all_points)
        sheet=spec.get("sheet")
        if sheet:
            scale=number(sheet.get("scale"),"sheet scale",1)
            if sheet.get("sheet_size") not in {"A3","A1"}:
                raise ValueError("Sheet requires A3 or A1")
            w,h=(420,297) if sheet["sheet_size"]=="A3" else (841,594)
            content_right=max([max(xs),*[t["at"][0]+5000 for t in spec.get("schedules",[])]])
            x=(min(xs)+content_right-w*scale)/2
            y=(min(ys)+max(ys)-h*scale)/2
            add(model.add_lwpolyline([(x,y),(x+w*scale,y),(x+w*scale,y+h*scale),(x,y+h*scale)],close=True,dxfattribs={"layer":"BORDER"}),"sheet")
            text(f"{sheet.get('intent','CAD平面')}   mm   1:{scale:g}",(x+5*scale,y+6*scale),"sheet",4*scale)
    return owners,areas


def measured_check(path,spec,owners):
    """Re-read saved entities and measure opening dimensions and wall gap centres."""
    doc=ezdxf.readfile(path)
    checks=[]
    wall_map={w["id"]:w for w in spec["walls"]}
    wall_lines=[]
    for e in doc.modelspace().query('LWPOLYLINE[layer=="WALL"]'):
        coords=list(e.get_points("xy"))
        if e.closed:
            coords.append(coords[0])
        wall_lines.append(LineString(coords))
    for op in spec["openings"]:
        entities=[doc.entitydb.get(h) for h in owners["opening:"+op["id"]]]
        dims=[e for e in entities if e is not None and e.dxftype()=="DIMENSION"]
        measured=float(dims[0].get_measurement()) if len(dims)==1 else None
        checks.append({"id":op["id"],"target_width":op["width"],"measured_width":measured,"ok":measured is not None and abs(measured-op["width"])<0.01})
        p,u,n=opening_basis(wall_map[op["wall"]],op)
        midpoint=Point(p[0]+u[0]*op["width"]/2,p[1]+u[1]*op["width"]/2)
        for sign in (-1,1):
            face=Point(midpoint.x+n[0]*wall_map[op["wall"]]["thickness"]/2*sign,midpoint.y+n[1]*wall_map[op["wall"]]["thickness"]/2*sign)
            checks.append({"id":op["id"]+f":gap:{sign}","ok":not any(line.distance(face)<0.001 for line in wall_lines)})
    from ezdxf import bbox
    from .furnishing import placed
    for item in spec.get('furniture',[]):
        entities=[doc.entitydb.get(h) for h in owners.get('furniture:'+item['id'],[])]
        refs=[e for e in entities if e is not None and e.dxftype()=='INSERT']
        expected=placed(item).bounds
        bounds=bbox.extents(refs)
        actual=[bounds.extmin.x,bounds.extmin.y,bounds.extmax.x,bounds.extmax.y] if bounds.has_data else []
        transform_ok=(len(refs)==1 and
            abs((refs[0].dxf.rotation-item.get('rotation',0)+180)%360-180)<.001 and
            all(abs(a-b)<.01 for a,b in zip(refs[0].dxf.insert,(*item['at'],0))) and
            all(abs(refs[0].dxf.get(axis,1)-1)<1e-9 for axis in ('xscale','yscale','zscale')))
        checks.append({'id':'furniture:'+item['id'],'expected_bounds':expected,'actual_bounds':actual,
                       'transform_matches':transform_ok,
                       'ok':transform_ok and len(actual)==4 and all(abs(a-b)<0.01 for a,b in zip(actual,expected))})
    scale=spec.get('sheet',{}).get('scale',50)
    for dim in doc.modelspace().query('DIMENSION'):
        style=dim.override()
        checks.append({'id':'paper_text:'+dim.dxf.handle,'paper_height_mm':style.get('dimtxt',0)/scale,
                       'ok':abs(style.get('dimtxt',0)/scale-3.5)<1e-6 and style.get('dimlfac',1)==1})
    return {"ok":all(c["ok"] for c in checks),"checks":checks,"scope":"Saved native dimension geometry and opening face gaps; not structural/design approval"}
