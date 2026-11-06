"""Transactional file jobs; retries return committed artifacts, never repeat writes."""
import copy
from pathlib import Path
import ezdxf

from .storage import ROOT, Journal, atomic_json, workspace_lock, inside
from .plan import validate_spec, new_document, draw_groups, measured_check
from .qa import file_hash, snapshots, audit_dxf, prepare_chinese_font, render_dxf


class Jobs:
    def __init__(self,root=None):
        self.root=Path(root or ROOT/"outputs").resolve()
        self.journal=Journal(self.root/"_jobs")

    def result(self,job_id):
        return self.journal.get(job_id)

    def pdf_inventory(self,job_id,source,calibration,font_map=None,page=0):
        from .pdf_source import extract_pdf
        source=Path(source).resolve()
        source_hash=file_hash(source)
        result=extract_pdf(source,page=page,calibration=calibration,font_map=font_map)
        request={'operation':'pdf_inventory','source_hash':source_hash,'page':page,
                 'calibration':calibration,'font_map':font_map or {},'inventory':result['inventory']}
        with workspace_lock(self.root):
            fresh,old=self.journal.begin(job_id,request)
            if not fresh:
                self.check_artifacts(old);return old
            directory=inside(job_id,self.root);directory.mkdir(parents=True,exist_ok=True)
            if (directory/'source-inventory.json').exists():raise ValueError('Existing source inventory must not be overwritten')
            atomic_json(directory/'source-inventory.json',result['inventory'])
            atomic_json(directory/'extraction-report.json',{k:v for k,v in result.items() if k!='inventory'})
            result['job_id']=job_id
            result['artifacts']={key:{'path':str(directory/name),'sha256':file_hash(directory/name)} for key,name in
                [('inventory','source-inventory.json'),('report','extraction-report.json')]}
            self.journal.set(job_id,{'status':'completed','result':result})
            return result

    def redraw(self,job_id,source,inventory):
        import sys
        from .reference_build import build
        source=Path(source).resolve()
        source_hash=file_hash(source)
        if source_hash!=inventory.get('source_sha256'):raise ValueError('SOURCE_HASH_MISMATCH')
        # Bundle-owned verifier; it compares source expectations, not generated ones.
        candidates=[ROOT,Path(__file__).resolve().parents[2],Path(__file__).resolve().parents[1]]
        bundle=next((p for p in candidates if (p/'scripts/redraw_delivery.py').is_file()),None)
        if bundle is None:raise ValueError('Complete Skill bundle with redraw verifier required')
        script_dir=str(bundle/'scripts')
        if script_dir not in sys.path:sys.path.insert(0,script_dir)
        from redraw_delivery import audit_reference
        doc,mapping=build(inventory)
        with workspace_lock(self.root):
            fresh,old=self.journal.begin(job_id,{'operation':'source_redraw','source_hash':source_hash,'inventory':inventory})
            if not fresh:
                self.check_artifacts(old);return old
            directory=inside(job_id,self.root);directory.mkdir(parents=True,exist_ok=True)
            path=directory/'redraw.dxf'
            if path.exists():raise ValueError('Existing redraw must not be overwritten')
            doc.saveas(path)
            check=audit_reference(path,inventory,mapping,source)
            atomic_json(directory/'source-inventory.json',inventory)
            atomic_json(directory/'mapping.json',{'reference_map':mapping})
            atomic_json(directory/'source-check.json',check)
            result={'ok':check['checks_passed'],'job_id':job_id,'reference_check':check,
                'complete_redraw_accepted':False,'next_step':'Review original and saved DXF at matching scale/background, then run the complete redraw gate',
                'artifacts':{key:{'path':str(directory/name),'sha256':file_hash(directory/name)} for key,name in
                    [('dxf','redraw.dxf'),('inventory','source-inventory.json'),('mapping','mapping.json'),('check','source-check.json')]}}
            self.journal.set(job_id,{'status':'completed' if result['ok'] else 'failed','result':result})
            return result

    def curved_walls(self,job_id,spec):
        from .curved_walls import draw,verify
        doc,normalized,owners,expected=draw(spec)
        with workspace_lock(self.root):
            fresh,old=self.journal.begin(job_id,{'operation':'curved_walls','spec':normalized})
            if not fresh:
                self.check_artifacts(old);return old
            directory=inside(job_id,self.root);directory.mkdir(parents=True,exist_ok=True)
            path=directory/'curved-walls.dxf'
            if path.exists():raise ValueError('Existing curve artifact must not be overwritten')
            doc.saveas(path)
            check=verify(path,expected)
            result={'ok':check['ok'],'job_id':job_id,'owners':owners,'readback':check,
                    'artifacts':{'dxf':{'path':str(path),'sha256':file_hash(path)}},
                    'scope':'Circular walls and measured arc-length voids; no inferred door/window assembly'}
            atomic_json(directory/'spec.json',normalized)
            self.journal.set(job_id,{'status':'completed' if result['ok'] else 'failed','result':result})
            return result

    def export_pdf(self,job_id,source,paper_mm,window_mm,scale,margin_mm=10):
        from .pdf_export import render_pdf
        source=inside(source,self.root);before=file_hash(source)
        request={'operation':'export_pdf','source':str(source),'sha256':before,'paper_mm':paper_mm,
                 'window_mm':window_mm,'scale':scale,'margin_mm':margin_mm}
        with workspace_lock(self.root):
            # Build bytes before journal start, so parameter errors are safely correctable.
            data,settings=render_pdf(source,paper_mm,window_mm,scale,margin_mm)
            if file_hash(source)!=before:raise ValueError('SOURCE_CHANGED_DURING_EXPORT')
            fresh,old=self.journal.begin(job_id,request)
            if not fresh:
                self.check_artifacts(old);return old
            directory=inside(job_id,self.root);directory.mkdir(parents=True,exist_ok=True)
            path=directory/'drawing.pdf'
            with path.open('xb') as stream:stream.write(data)
            result={'ok':True,'job_id':job_id,'source_sha256':before,'settings':settings,
                    'artifacts':{'pdf':{'path':str(path),'sha256':file_hash(path)}}}
            atomic_json(directory/'manifest.json',result)
            self.journal.set(job_id,{'status':'completed','result':result})
            return result

    def check_artifacts(self,result):
        for artifact in result["artifacts"].values():
            path=inside(artifact["path"],self.root)
            if not path.is_file() or file_hash(path)!=artifact["sha256"]:
                raise ValueError("ARTIFACT_CHANGED: inspect the existing job before replay")

    def publish(self,job_id,doc,spec,owners,areas,extra=None):
        directory=self.root/job_id
        directory.mkdir(parents=True,exist_ok=True)
        path=directory/"plan.dxf"
        doc.saveas(path)
        font=prepare_chinese_font(path)
        qa=audit_dxf(path)
        geometry=measured_check(path,spec,owners)
        qa["measured_geometry"]=geometry
        preview=render_dxf(path,directory/"preview.png")
        atomic_json(directory/"spec.json",spec)
        atomic_json(directory/"qa.json",qa)
        result={"ok":qa["ok"] and geometry["ok"],"target":"offline","job_id":job_id,
            "delivery_scope":{"kind":spec.get('deliverable','geometry_plan'),
                              "furniture_count":len(spec.get('furniture',[])),
                              "full_construction_delivery_accepted":False},
            "revision":file_hash(path),"owners":owners,"room_areas_m2":areas,"font":font,"preview":preview,
            "artifacts":{key:{"path":str(directory/name),"sha256":file_hash(directory/name)} for key,name in
                (("dxf","plan.dxf"),("spec","spec.json"),("qa","qa.json"),("preview","preview.png"))},
            "acceptance":{"geometry":"PASS" if qa["ok"] and geometry["ok"] else "FAIL","visual":"pending","professional_design":"not_reviewed"},**(extra or {})}
        atomic_json(directory/"manifest.json",result)
        self.journal.set(job_id,{"status":"completed" if result["ok"] else "failed","result":result})
        return result

    def generate(self,job_id,spec):
        spec=validate_spec(spec)
        with workspace_lock(self.root):
            fresh,old=self.journal.begin(job_id,{"operation":"generate","spec":spec})
            if not fresh:
                self.check_artifacts(old)
                return old
            doc=new_document()
            owners,areas=draw_groups(doc,spec)
            return self.publish(job_id,doc,spec,owners,areas)

    def patch(self,job_id,source_job,expected_revision,opening_id,changes):
        allowed={"width","height","sill","offset","hand","tag","swing_side","dimension_offset","tag_at"}
        if not changes or set(changes)-allowed:
            raise ValueError("Opening patch only supports: "+", ".join(sorted(allowed)))
        if job_id==source_job:
            raise ValueError("Patch requires a new job id")
        with workspace_lock(self.root):
            previous=self.journal.get(source_job)
            if not previous or previous.get("status")!="completed":
                raise ValueError("Source job has not completed")
            source=previous["result"]
            if source["revision"]!=expected_revision:
                raise ValueError("STALE_REVISION: inspect source manifest")
            self.check_artifacts(source)
            spec=__import__('json').loads(Path(source["artifacts"]["spec"]["path"]).read_text(encoding="utf-8"))
            target=next((o for o in spec["openings"] if o["id"]==opening_id),None)
            if target is None:
                raise ValueError("Opening id does not exist")
            target.update(changes)
            spec=validate_spec(spec)
            fresh,old=self.journal.begin(job_id,{"operation":"patch","source":source_job,"revision":expected_revision,"opening":opening_id,"changes":changes})
            if not fresh:
                self.check_artifacts(old)
                return old
            groups={"opening:"+opening_id,"wall:"+target["wall"],"schedules"}
            if isinstance(spec.get('chains'),dict) and 'openings' in spec['chains'].get('levels',[]):
                groups.add('overall-dim')
            doc=ezdxf.readfile(source["artifacts"]["dxf"]["path"])
            before=snapshots(source["artifacts"]["dxf"]["path"])
            removed={h for g in groups for h in source["owners"].get(g,[])}
            for h in removed:
                entity=doc.entitydb.get(h)
                if entity is None:
                    raise ValueError("Owned entity missing; refusing to guess")
                doc.modelspace().delete_entity(entity)
            created,areas=draw_groups(doc,spec,groups)
            owners={g:hs for g,hs in source["owners"].items() if g not in groups}
            owners.update(created)
            result=self.publish(job_id,doc,spec,owners,areas,{"source_job":source_job,"modified_groups":sorted(groups)})
            after=snapshots(result["artifacts"]["dxf"]["path"])
            changed=[h for h,v in before.items() if h not in removed and after.get(h)!=v]
            if changed:
                self.journal.set(job_id,{"status":"failed","error":"UNRELATED_ENTITY_CHANGED","handles":changed})
                raise RuntimeError("UNRELATED_ENTITY_CHANGED: generated copy withheld from acceptance")
            result["unrelated_entities_unchanged"]=True
            atomic_json(self.root/job_id/"manifest.json",result)
            self.journal.set(job_id,{"result":result})
            return result
