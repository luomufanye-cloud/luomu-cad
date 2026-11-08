"""Luomu CAD solid workflow. Copyright (c) 2026 luomufanye-cloud.

Project state, script capture, receipts, feature matching and exact comparisons are
implemented here; build123d and OpenCascade provide the external geometry kernel.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager, redirect_stdout
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import traceback

ENGINE_VERSION = '1.0'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    os.replace(temporary,path)


def state_file():
    return Path.cwd()/'.luomu-solid/project.json'


def state():
    return json.loads(state_file().read_text(encoding='utf8'))


@contextmanager
def project_lock():
    lock=Path.cwd()/'.luomu-solid/write.lock'
    try:
        fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:
        raise ValueError('SOLID_PROJECT_BUSY: inspect run_status before further writes') from None
    try:
        os.write(fd,str(os.getpid()).encode());os.close(fd)
        yield
    finally:
        lock.unlink()


def load_shape(path):
    from build123d import import_step, import_brep
    path=Path(path)
    if not path.is_file():raise ValueError('Geometry file missing')
    shape=import_brep(str(path)) if path.suffix.lower()=='.brep' else import_step(str(path))
    if shape is None:raise ValueError('Geometry could not be read')
    return shape


def metrics(shape):
    from OCP.BRep import BRep_Tool
    box=shape.bounding_box()
    minimum=[box.min.X,box.min.Y,box.min.Z];maximum=[box.max.X,box.max.Y,box.max.Z]
    solids=list(shape.solids());shells=list(shape.shells())
    valid=bool(shape.is_valid and solids and all(BRep_Tool.IsClosed_s(s.wrapped) for s in shells))
    return {'bounding_box':{axis:[round(a,7),round(b,7)] for axis,a,b in zip('xyz',minimum,maximum)},
        'dimensions':{axis:round(b-a,7) for axis,a,b in zip('xyz',minimum,maximum)},
        'volume':round(sum(s.volume for s in solids),7),'surface_area':round(shape.area,7),
        'face_count':len(shape.faces()),'edge_count':len(shape.edges()),'solid_count':len(solids),
        'shell_count':len(shells),'is_valid':valid,'reliable':valid}


def mesh_validation(shape):
    """Check welded triangle-edge incidence on each native solid independently."""
    records=[]
    for solid in shape.solids():
        vertices,triangles=solid.tessellate(.03,.1)
        ids=[tuple(round(v,6) for v in (point.X,point.Y,point.Z)) for point in vertices]
        edges=Counter();orientation=Counter()
        for triangle in triangles:
            a,b,c=(ids[i] for i in triangle)
            for start,end in ((a,b),(b,c),(c,a)):
                if start==end:continue
                edge=tuple(sorted((start,end)));edges[edge]+=1
                orientation[edge]+=1 if start<end else -1
        bad=sum(count!=2 for count in edges.values())
        flipped=sum(value!=0 for value in orientation.values())
        records.append({'triangles':len(triangles),'nonmanifold_edges':bad,'orientation_errors':flipped,
                        'passed':bool(triangles) and bad==0 and flipped==0})
    return {'passed':bool(records) and all(r['passed'] for r in records),'solids':records,
            'requested_linear_tolerance_mm':.03,'weld_quantization_mm':1e-6}


def cylindrical_features(shape):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    surfaces={}
    for index,face in enumerate(shape.faces()):
        adaptor=BRepAdaptor_Surface(face.wrapped,True)
        if adaptor.GetType()!=GeomAbs_Cylinder:continue
        cylinder=adaptor.Cylinder();direction=cylinder.Axis().Direction();p=cylinder.Location()
        axis=[direction.X(),direction.Y(),direction.Z()]
        first=next((v for v in axis if abs(v)>1e-9),1)
        if first<0:axis=[-v for v in axis]
        point=[p.X(),p.Y(),p.Z()]
        scalar=sum(a*b for a,b in zip(point,axis))
        anchor=[v-scalar*n for v,n in zip(point,axis)]
        points=[v.center() for v in face.vertices()]
        axial=[v.X*axis[0]+v.Y*axis[1]+v.Z*axis[2] for v in points]
        key=(round(cylinder.Radius(),6),*(round(v,6) for v in axis),*(round(v,5) for v in anchor))
        row={'radius_mm':cylinder.Radius(),'axis_vector':axis,'axis_point_mm':anchor,
             'interval_mm':[min(axial),max(axial)],'face_ids':[f'face_{index+1}']}
        surfaces.setdefault(key,[]).append(row)
    result=[]
    for rows in surfaces.values():
        rows.sort(key=lambda r:r['interval_mm'][0])
        merged=[]
        for row in rows:
            if merged and row['interval_mm'][0]<=merged[-1]['interval_mm'][1]+1e-6:
                merged[-1]['interval_mm'][1]=max(merged[-1]['interval_mm'][1],row['interval_mm'][1])
                merged[-1]['face_ids']+=row['face_ids']
            else:merged.append(row)
        for row in merged:
            vector=row['axis_vector'];name='other'
            for index,component in enumerate(vector):
                if abs(abs(component)-1)<1e-7:name=('+' if component>0 else '-')+'xyz'[index]
            result.append({**row,'type':'cylinder','diameter_mm':round(row['radius_mm']*2,7),'axis':name})
    return result


def measurements(path, include_features=True):
    shape=load_shape(path)
    data={'status':'success','metrics':metrics(shape)}
    if include_features:data['features']=cylindrical_features(shape)
    return data


def _finite(value, label, nonnegative=True):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or (nonnegative and value<0):
        raise ValueError(label+' requires a finite nonnegative number')
    return value


def check_features(path, specification):
    data=measurements(path);matched=[];missing=[];structure=[]
    if not isinstance(specification,dict):raise ValueError('Feature requirements must be an object')
    for field,actual in [('expect_solids',data['metrics']['solid_count']),('expect_shells',data['metrics']['shell_count'])]:
        if field in specification:
            expected=specification[field]
            if type(expected) is not int or expected<0:raise ValueError('Nonnegative structural count required')
            structure.append({'name':field,'expected':expected,'actual':actual,'passed':actual==expected})
    targets=specification.get('features',[])
    if not isinstance(targets,list) or (not targets and not structure):raise ValueError('Explicit feature or structure requirements required')
    for target in targets:
        if target.get('type')!='cylinder':raise ValueError('Unsupported feature type')
        diameter=_finite(target.get('diameter_mm'),'Diameter')
        if diameter<=0:raise ValueError('Positive diameter required')
        count=target.get('count')
        if type(count) is not int or count<0:raise ValueError('Nonnegative count required')
        tolerance=_finite(target.get('diameter_tolerance_mm',specification.get('diameter_tolerance_mm',.1)),'Diameter tolerance')
        count_tolerance=target.get('count_tolerance',specification.get('count_tolerance',0))
        if type(count_tolerance) is not int or count_tolerance<0:raise ValueError('Nonnegative count tolerance required')
        axis=target.get('axis')
        if axis is not None and axis not in ('+x','-x','+y','-y','+z','-z','other'):raise ValueError('Invalid feature axis')
        matches=[f for f in data['features'] if abs(f['diameter_mm']-diameter)<=tolerance+1e-8
                 and (axis is None or f['axis'].lstrip('+-')==axis.lstrip('+-'))]
        row={'name':target.get('name','cylinder'),'expected_count':count,'actual_count':len(matches),
             'matched_features':matches,'passed':abs(len(matches)-count)<=count_tolerance}
        matched.append(row)
        if not row['passed']:missing.append(row['name'])
    return {**data,'passed':data['metrics']['is_valid'] and all(r['passed'] for r in matched+structure),
            'matched_features':matched,'missing_features':missing,'structure_checks':structure}


def _occupied(shape):
    return 0.0 if shape is None else sum(s.volume for s in shape.solids())


def compare(reference,candidate):
    before,after=load_shape(reference),load_shape(candidate)
    if not metrics(before)['is_valid'] or not metrics(after)['is_valid']:raise ValueError('Exact comparison requires valid closed solids')
    shared=before.intersect(after);removed=before.cut(after);added=after.cut(before)
    volumes={name:round(_occupied(shape),7) for name,shape in
             [('reference',before),('candidate',after),('shared',shared),('reference_only',removed),('candidate_only',added)]}
    volumes['union']=round(volumes['shared']+volumes['reference_only']+volumes['candidate_only'],7)
    return {'status':'success','comparison_3d':{'status':'success','method':'source_frame_boolean_volume',
        'alignment':{'mode':'source_frame','transform_applied':False},'units':{'length':'mm','volume':'mm^3'},
        'volumes':volumes,'kernel':'OpenCascade','approximation_used':False}}


def receipt_path(key):
    if not isinstance(key,str) or not key or len(key)>256:raise ValueError('Nonempty bounded retry key required')
    return Path.cwd()/'.luomu-solid/requests'/ (hashlib.sha256(key.encode()).hexdigest()+'.json')


def run_status(key):
    file=receipt_path(key)
    if not file.is_file():return {'status':'error','error':'UNKNOWN_RETRY_KEY'}
    record=json.loads(file.read_text(encoding='utf8'))
    if record['phase']=='completed':return record['result']
    if record['phase']=='failed':
        return {'status':'error','error':record.get('error','Build failed'),'execution_uncertain':False}
    return {'status':'error','execution_uncertain':True,'phase':record['phase'],
            'next_action':'Inspect saved request and artifacts; do not execute the request again.'}


def build(source,label,key):
    import build123d as kernel
    source=Path(source).resolve()
    request={'source':str(source),'source_sha256':digest(source),'label':label,'engine_version':ENGINE_VERSION}
    receipt=receipt_path(key)
    if receipt.is_file():
        saved=json.loads(receipt.read_text(encoding='utf8'))
        if saved['request']!=request:return {'status':'error','error':'RETRY_KEY_CONFLICT'}
        if saved['phase']=='completed':
            for path,sha in saved.get('files',{}).items():
                if not Path(path).is_file() or digest(path)!=sha:return {'status':'error','error':'SAVED_ARTIFACT_CHANGED'}
            return saved['result']
        return run_status(key)
    with project_lock():
        project=state();number=len(project['versions'])+1
        slug=re.sub(r'[^A-Za-z0-9_-]','_',str(label))[:50] or 'model'
        version=Path.cwd()/f'v{number}_{slug}'
        if version.exists():raise ValueError('Version destination already exists')
        record={'phase':'started','request':request,'pid':os.getpid(),'key':key}
        save(receipt,record)
        try:
            version.mkdir();program=version/'script.py';program.write_bytes(source.read_bytes())
            captured=[];identities=set()
            def capture(shape,*args,**kwargs):
                if not isinstance(shape,kernel.Shape):
                    shape=getattr(shape,'part',shape)
                if not isinstance(shape,kernel.Shape):raise ValueError('show_object requires a build123d shape')
                if id(shape) in identities:raise ValueError('Duplicate object capture; copy instances explicitly')
                identities.add(id(shape));captured.append(shape)
            namespace={name:value for name,value in vars(kernel).items() if not name.startswith('_')}
            namespace.update(show_object=capture,show_compound=lambda shapes,**kw:[capture(s) for s in shapes],
                             __name__='__luomu_model__',__file__=str(program))
            with redirect_stdout(sys.stderr):
                exec(compile(program.read_bytes(),str(program),'exec'),namespace)
            if not captured and isinstance(namespace.get('result'),kernel.Shape):capture(namespace['result'])
            if not captured:raise ValueError('Model must capture at least one shape')
            shape=captured[0] if len(captured)==1 else kernel.Compound(children=captured)
            source_metrics=metrics(shape)
            if not source_metrics['is_valid']:raise ValueError('Model is not a valid closed solid')
            target=version/'output.step';kernel.export_step(shape,str(target))
            restored=load_shape(target);actual=metrics(restored);mesh=mesh_validation(restored)
            if not actual['is_valid'] or not mesh['passed']:raise ValueError('Saved STEP failed native or mesh validation')
            if abs(actual['volume']-source_metrics['volume'])>max(1e-5,abs(source_metrics['volume'])*1e-8):
                raise ValueError('STEP round-trip volume differs')
            if source_metrics['solid_count']!=actual['solid_count']:raise ValueError('STEP solid count differs')
            result={'status':'success','command':'run','version':number,'label':label,'metrics':actual,
                'outputs':{'step':str(target.relative_to(Path.cwd())),'script':str(program.relative_to(Path.cwd()))},
                'artifact_created':True,'validation':{'is_valid':True,'mesh_manifold':mesh,
                    'step_round_trip':{'status':'pass','before':source_metrics,'after':actual}}}
            project['versions'].append({'version':number,'label':label,'path':str(version.relative_to(Path.cwd()))})
            save(state_file(),project)
            record.update(phase='completed',result=result,files={str(p):digest(p) for p in (target,program)})
            save(receipt,record);return result
        except Exception as error:
            record.update(phase='failed',error=str(error));save(receipt,record)
            return {'status':'error','error':str(error),'execution_uncertain':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='operation',required=True)
    p=sub.add_parser('init');p.add_argument('--name',required=True)
    p=sub.add_parser('run');p.add_argument('source',nargs='?');p.add_argument('--label');p.add_argument('--idempotency-key',required=True);p.add_argument('--status',action='store_true')
    for command in ('measure','inspect','render'):
        p=sub.add_parser(command);p.add_argument('source');p.add_argument('--features',action='store_true');p.add_argument('--summary',action='store_true');p.add_argument('--limit',type=int,default=30);p.add_argument('--view',default='all')
    p=sub.add_parser('check-spec');p.add_argument('source');p.add_argument('spec')
    p=sub.add_parser('diff');p.add_argument('reference');p.add_argument('candidate')
    sub.add_parser('context')
    args=parser.parse_args()
    try:
        if args.operation=='init':
            if any(Path.cwd().iterdir()):raise ValueError('Initialize requires an empty project')
            save(state_file(),{'schema_version':1,'name':args.name,'engine':'luomu-cad','versions':[]})
            data={'status':'success','project':args.name}
        elif args.operation=='run':
            if args.status:data=run_status(args.idempotency_key)
            elif not args.source or not args.label:raise ValueError('Source and label required')
            else:data=build(args.source,args.label,args.idempotency_key)
        elif args.operation=='context':data={'status':'success','project':state()}
        elif args.operation=='measure':data=measurements(args.source,args.features)
        elif args.operation=='inspect':
            shape=load_shape(args.source);data={'status':'success','metrics':metrics(shape),
                'validation':mesh_validation(shape),'face_ids':[f'face_{i+1}' for i in range(min(args.limit,len(shape.faces())))]}
        elif args.operation=='check-spec':data=check_features(args.source,json.loads(Path(args.spec).read_text(encoding='utf8')))
        elif args.operation=='diff':data=compare(args.reference,args.candidate)
        else:
            from .solid_render import render
            import uuid
            data=render(args.source,Path.cwd()/'luomu-render'/uuid.uuid4().hex)
        print(json.dumps(data,ensure_ascii=True,allow_nan=False))
        return 0 if data.get('status')=='success' else 1
    except Exception as error:
        print(json.dumps({'status':'error','error':str(error),'error_type':type(error).__name__}))
        return 1


if __name__=='__main__':
    raise SystemExit(main())
