"""Source-inventory coverage checks, separate from generator self-consistency."""
import hashlib
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import ezdxf
from ezdxf.colors import aci2rgb
from luomu_cad.annotations import text_style_findings


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close(a,b,tol):
    if isinstance(a,(list,tuple)) or hasattr(a,'__iter__') and not isinstance(a,str):
        return len(a)==len(b) and all(close(x,y,tol) for x,y in zip(a,b))
    return isinstance(a,(int,float)) and math.isfinite(a) and abs(a-b)<=tol


def audit_reference(path, inventory, mapping, source_path):
    """Inventory must be reviewed against the source, not extracted from output."""
    doc=ezdxf.readfile(path);entities={e.dxf.handle:e for e in doc.modelspace()}
    errors=[]
    if inventory.get('schema_version')!=1:raise ValueError('Reference inventory schema_version must be 1')
    if inventory.get('delivery_target') not in ('offline_dxf','live_cad'):raise ValueError('Explicit delivery_target required')
    if not isinstance(inventory.get('page'),int) or inventory['page']<0 or not inventory.get('view'):
        raise ValueError('Reference inventory requires page and view')
    if sha(source_path)!=inventory.get('source_sha256'):errors.append('SOURCE_HASH_MISMATCH')
    objects=inventory.get('objects')
    if not isinstance(objects,list) or not objects:raise ValueError('Independent source objects are required')
    ids=[s.get('id') for s in objects]
    if any(not isinstance(x,str) or not x for x in ids) or len(set(ids))!=len(ids):raise ValueError('Unique reference IDs required')
    if not isinstance(mapping,dict):raise ValueError('reference_map must map source IDs to output handles')
    used=[];dimensions=[];texts=[];text_entities=[]
    for spec in objects:
        sid=spec['id'];kind=spec.get('kind');expected=spec.get('expected',{})
        if not spec.get('source_locator'):raise ValueError('Every reference object needs a source locator')
        tol=spec.get('tolerance')
        if isinstance(tol,bool) or not isinstance(tol,(int,float)) or not math.isfinite(tol) or tol<=0:raise ValueError('Positive reference tolerance required')
        handle=mapping.get(sid)
        if not isinstance(handle,str) or handle not in entities:
            errors.append('REFERENCE_OBJECT_MISSING:'+sid);continue
        used.append(handle);e=entities[handle]
        if e.dxftype()!=kind:errors.append('REFERENCE_TYPE:'+sid);continue
        checks=[]
        if kind=='LINE':
            checks=[close(e.dxf.start,expected['start'],tol) and close(e.dxf.end,expected['end'],tol) or
                    close(e.dxf.end,expected['start'],tol) and close(e.dxf.start,expected['end'],tol)]
        elif kind in ('ARC','CIRCLE'):
            checks=[close(e.dxf.center,expected['center'],tol),close(e.dxf.radius,expected['radius'],tol)]
            if kind=='ARC':
                for key in ('start_angle','end_angle'):
                    difference=abs((e.dxf.get(key)-expected[key]+180)%360-180)
                    checks.append(math.isfinite(difference) and difference<=1e-6)
        elif kind=='SPLINE':
            checks=[e.dxf.degree==expected['degree'],close(list(e.control_points),expected['control_points'],tol),
                    close(list(e.knots),expected['knots'],1e-9),close(list(e.weights),expected.get('weights',[]),1e-9)]
        elif kind=='LWPOLYLINE':
            checks=[e.closed==expected['closed'],close(list(e.get_points('xyb')),expected['points'],tol)]
        elif kind=='TEXT':
            texts.append(expected['text'])
            text_entities.append({'handle':handle,'tolerance':tol,**{k:expected[k] for k in ('text','at','height','rotation')}})
            checks=[close(e.dxf.width,expected['width'],1e-6),e.dxf.halign==0,e.dxf.valign==0,
                    e.dxf.text_generation_flag==0,close(e.dxf.oblique,0,1e-6)]
            style=doc.styles.get(e.dxf.style)
            checks.append(style.dxf.font.casefold()==expected['font'].casefold())
        elif kind=='HATCH':
            checks=[bool(e.dxf.solid_fill)==expected['solid'],e.dxf.hatch_style==expected['hatch_style']]
            actual=[]
            for loop in e.paths:
                if not hasattr(loop,'vertices'):
                    errors.append('REFERENCE_HATCH_EDGE_UNSUPPORTED:'+sid);continue
                actual.append({'points':[list(p) for p in loop.vertices],
                               'closed':bool(loop.is_closed),'external':bool(loop.path_type_flags & 1)})
            wanted=expected['loops']
            checks.append(len(actual)==len(wanted) and all(
                a['closed']==b['closed'] and a['external']==b['external'] and close(a['points'],b['points'],tol)
                for a,b in zip(actual,wanted)))
        elif kind=='DIMENSION':
            dimensions.append({'handle':handle,'tolerance':tol,**{k:expected[k] for k in ('start','end','measurement','dimlfac','display_text','style')}})
            checks=[close(e.dxf.defpoint,expected['line_at'],tol)]
        else:errors.append('REFERENCE_TYPE_UNSUPPORTED:'+sid)
        if checks and not all(checks):errors.append('REFERENCE_GEOMETRY:'+sid)
        presentation=spec.get('presentation')
        if not isinstance(presentation,dict) or not all(k in presentation for k in ('linetype','rgb','lineweight','opacity')):
            raise ValueError('Source-derived linetype, rgb, lineweight and opacity required for every object')
        rgb=presentation['rgb'];opacity=presentation['opacity'];weight=presentation['lineweight']
        if not isinstance(rgb,list) or len(rgb)!=3 or any(type(c)!=int or not 0<=c<=255 for c in rgb):
            raise ValueError('Explicit source RGB bytes required')
        if type(weight)!=int or weight<0 or not isinstance(opacity,(int,float)) or isinstance(opacity,bool) or not math.isfinite(opacity) or not 0<=opacity<=1:
            raise ValueError('Explicit finite source opacity and resolved lineweight required')
        layer=doc.layers.get(e.dxf.layer)
        color_entity=layer if e.dxf.color==256 and not e.dxf.hasattr('true_color') else e
        if color_entity.dxf.color==0 and not color_entity.dxf.hasattr('true_color'):
            errors.append('REFERENCE_BYBLOCK_UNRESOLVED:'+sid)
        else:
            actual_rgb=color_entity.rgb if color_entity.rgb is not None else aci2rgb(abs(color_entity.dxf.color))
            if list(actual_rgb)!=rgb:errors.append('REFERENCE_COLOR:'+sid)
        actual_weight=e.dxf.lineweight
        if actual_weight==-1:actual_weight=layer.dxf.lineweight
        if actual_weight!=weight:errors.append('REFERENCE_LINEWEIGHT:'+sid)
        if e.is_transparency_by_block:errors.append('REFERENCE_BYBLOCK_OPACITY:'+sid)
        actual_opacity=1-(layer.transparency if e.is_transparency_by_layer else e.transparency)
        if abs(actual_opacity-opacity)>1/255+1e-9:errors.append('REFERENCE_OPACITY:'+sid)
        actual=e.dxf.get('linetype','BYLAYER')
        if actual.upper()=='BYLAYER':actual=doc.layers.get(e.dxf.layer).dxf.linetype
        if actual.upper()!=presentation['linetype'].upper():errors.append('REFERENCE_LINETYPE:'+sid)
    if len(used)!=len(set(used)):errors.append('REFERENCE_HANDLE_REUSED')
    errors.extend('UNMAPPED_OUTPUT:'+h for h in sorted(entities.keys()-set(used)))
    errors.extend('UNKNOWN_REFERENCE_ID:'+s for s in sorted(set(mapping)-set(ids)))
    # Use source expectations, never generator-owned dimension coordinates.
    from verify_redraw import audit
    contract={'source':inventory['view'],'units':inventory['units'],'dimensions':dimensions,'texts':texts,
              'text_entities':text_entities,'dimensions_absent_reason':'No mapped dimensions in source comparison',
              'texts_absent_reason':'No mapped text in source comparison'}
    structure=audit(path,contract)
    errors.extend(structure['errors'])
    errors.extend('ANNOTATION:'+f['kind']+':'+f.get('handle','') for f in text_style_findings(doc))
    return {'checks_passed':not errors,'errors':list(dict.fromkeys(errors)),
            'source_objects':len(objects),'mapped_objects':len(used),'source_sha256':inventory['source_sha256'],
            'drawing_sha256':sha(path),'inventory_sha256':hashlib.sha256(json.dumps(inventory,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
            'scope':'Comparison to declared source inventory; completeness of that inventory requires source review'}


def review_findings(review, reference, inventory, directory):
    """Bind declared visual review to immutable inputs and actual review images."""
    if not isinstance(review,dict):return ['VISUAL_REVIEW_REQUIRED']
    errors=[]
    for key in ('source_sha256','drawing_sha256','inventory_sha256'):
        if review.get(key)!=reference[key]:errors.append('STALE_REVIEW:'+key)
    regions=inventory.get('review_regions',[])
    if not isinstance(regions,list) or not regions or 'full_view' not in regions:raise ValueError('Review regions must include full_view')
    checks=review.get('regions',{})
    for region in regions:
        item=checks.get(region,{})
        if item.get('reviewed') is not True or not item.get('observations') or item.get('unresolved')!=[]:
            errors.append('VISUAL_REGION_INCOMPLETE:'+region);continue
        for side in ('source','output'):
            artifact=item.get(side,{})
            background=artifact.get('background_rgb')
            if not isinstance(background,list) or len(background)!=3 or any(type(c)!=int or not 0<=c<=255 for c in background):
                errors.append('REVIEW_BACKGROUND_REQUIRED:'+region+':'+side)
            p=Path(directory)/artifact.get('path','')
            if not p.is_file() or sha(p)!=artifact.get('sha256'):
                errors.append('REVIEW_ARTIFACT:'+region+':'+side);continue
            try:
                from PIL import Image
                with Image.open(p) as picture:picture.verify()
            except Exception:errors.append('REVIEW_IMAGE_INVALID:'+region+':'+side)
        if item.get('source',{}).get('background_rgb')!=item.get('output',{}).get('background_rgb'):
            errors.append('REVIEW_BACKGROUND_MISMATCH:'+region)
    if not review.get('reviewer'):errors.append('REVIEWER_REQUIRED')
    if inventory['delivery_target']=='live_cad':
        native=review.get('native_display',{})
        if native.get('method')!='cad_mcp' or native.get('drawing_sha256')!=reference['drawing_sha256'] or not native.get('document_token'):
            errors.append('NATIVE_CAD_REVIEW_REQUIRED')
        artifact=native.get('preview',{});p=Path(directory)/artifact.get('path','')
        if not p.is_file() or sha(p)!=artifact.get('sha256'):errors.append('NATIVE_PREVIEW_REQUIRED')
    return errors
