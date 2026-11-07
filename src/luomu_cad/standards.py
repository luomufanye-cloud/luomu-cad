"""Traceable standards selection and delivery evidence, not an engineering certifier."""
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from .storage import ROOT

LAYERS={'drawing','design','construction_acceptance','data_delivery'}


def catalogue():
    candidates=[ROOT,Path(__file__).resolve().parents[2],Path(__file__).resolve().parents[1]]
    path=next((p/'references/standards-catalogue.json' for p in candidates
               if (p/'references/standards-catalogue.json').is_file()),None)
    if path is None:raise ValueError('Complete Skill standards catalogue required')
    value=json.loads(path.read_text(encoding='utf-8'))
    validate_catalogue(value)
    return value


def text(value):
    return isinstance(value,str) and value.strip().casefold() not in {
        '', 'unknown','pending','tbd','todo','待确认','待核实','未确认','待补充'}


def day(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise ValueError('ISO calendar date required')
    return date.fromisoformat(value)


def https(value):
    if not isinstance(value,str):return False
    url=urlsplit(value)
    return url.scheme=='https' and bool(url.hostname) and not url.username and not url.password


def validate_catalogue(value):
    if value.get('schema_version')!=1:raise ValueError('Unsupported standards catalogue schema')
    day(value.get('checked_on'))
    rows=value.get('standards')
    if not isinstance(rows,list) or not rows:raise ValueError('Nonempty standards index required')
    ids=set()
    for row in rows:
        if not text(row.get('id')) or row['id'] in ids:raise ValueError('Distinct standard IDs required')
        ids.add(row['id'])
        if any(not text(row.get(k)) for k in ('number','title','jurisdiction','evidence_level','status_observed')):
            raise ValueError('Standard identity and evidence level required')
        if row.get('layer') not in LAYERS or not https(row.get('source_url')):
            raise ValueError('Identified standard layer and public source required')
        if not isinstance(row.get('disciplines'),list) or not row['disciplines']:
            raise ValueError('Standard discipline tags required')
        day(row.get('checked_on'))
        if row.get('effective_on'):day(row['effective_on'])
        if row.get('project_recheck_required') is not True:
            raise ValueError('A standards index cannot create permanent project defaults')
    for row in rows:
        if row.get('superseded_by') and row['superseded_by'] not in ids:raise ValueError('Unknown replacement standard')
    routes=value.get('routes')
    if not isinstance(routes,list) or not routes:raise ValueError('Discipline routes required')
    if len({r.get('id') for r in routes})!=len(routes):raise ValueError('Distinct discipline route IDs required')
    for route in routes:
        if not text(route.get('id')) or not text(route.get('additional_review')):
            raise ValueError('Route identity and explicit remaining scope required')
        if not isinstance(route.get('candidate_ids'),list) or set(route['candidate_ids'])-ids:
            raise ValueError('Route refers to unknown standards')
    return value


def route(discipline,jurisdiction='CN'):
    value=catalogue()
    selected=next((r for r in value['routes'] if r['id']==discipline),None)
    if selected is None:raise ValueError('Unknown discipline; add a source-verified project route, do not substitute another industry')
    records=[r for r in value['standards'] if (r['id'] in selected['candidate_ids'] or 'general' in r['disciplines'])
             and (r['jurisdiction']==jurisdiction or r['jurisdiction'].endswith('_contract')
                  or (jurisdiction.startswith('CN-') and r['jurisdiction']=='CN'))]
    return {'route':selected,'standards':records,'catalogue_checked_on':value['checked_on'],
            'auto_apply':False,'engineering_approval':False,
            'limits':'Candidate discovery only; verify issuer, edition, effective date, local requirements and project applicability before adoption'}


def _artifact(artifact,directory,drawing_hash):
    if not isinstance(artifact,dict) or artifact.get('drawing_sha256')!=drawing_hash:return False
    name=artifact.get('path')
    if not text(name):return False
    path=(Path(directory)/name).resolve()
    if not path.is_relative_to(Path(directory).resolve()) or not path.is_file():return False
    return hashlib.sha256(path.read_bytes()).hexdigest()==artifact.get('sha256')


def review_basis(manifest,drawing,directory,library=None):
    """Check record completeness/current-artifact binding; never certify clauses.

    Source interpretation and truth of asserted measurements require independent
    review. A reference-only record cannot claim current-standard compliance.
    """
    if not isinstance(manifest,dict):
        return {'basis_record_accepted':False,'errors':['STANDARDS_BASIS_REQUIRED'],
                'standards_compliance_certified':False,'engineering_approval':False}
    if manifest.get('schema_version')!=1:raise ValueError('Standards manifest schema_version=1 required')
    library=validate_catalogue(library) if library is not None else catalogue()
    known={r['id']:r for r in library['standards']}
    project=manifest.get('project',{})
    if not isinstance(project,dict):raise ValueError('Project context must be an object')
    for key in ('jurisdiction','discipline','stage','delivery_scope'):
        if not text(project.get(key)):raise ValueError('Missing project.'+key)
    reviewed=day(manifest.get('reviewed_on'))
    if not text(manifest.get('reviewer')):raise ValueError('Identified standards reviewer required')
    mode=manifest.get('scope')
    if mode not in {'reference_only','drawing_review','engineering_review'}:raise ValueError('Explicit standards review scope required')
    reference_only=mode=='reference_only'
    if manifest.get('compliance_claim') is not (not reference_only):
        raise ValueError('Reference reproduction and normative review claims must remain separate')
    digest=hashlib.sha256(Path(drawing).read_bytes()).hexdigest()
    errors=[];limitations=[]
    if manifest.get('drawing_sha256')!=digest:errors.append('STANDARDS_STALE_DRAWING')
    if manifest.get('unresolved')!=[]:errors.append('STANDARDS_UNRESOLVED')
    layers=manifest.get('layers',{})
    if not isinstance(layers,dict) or set(layers)!=LAYERS:raise ValueError('Declare all four standards layers')
    for name,decision in layers.items():
        if not isinstance(decision,dict) or not text(decision.get('reason')):
            raise ValueError('Layer applicability reason required')
        state=decision.get('status')
        if state not in {'covered','not_applicable','not_assessed'}:raise ValueError('Unknown layer decision')
        if state=='not_assessed':
            limitations.append(name+': '+decision['reason'])
            if not reference_only:errors.append('STANDARDS_LAYER_UNASSESSED:'+name)
    if not reference_only and layers['drawing']['status']!='covered':errors.append('STANDARDS_DRAWING_LAYER_REQUIRED')
    records=manifest.get('standards')
    if not isinstance(records,list) or not records:raise ValueError('Explicit project standards selection required')
    ids=set();covered=set();adopted=0
    for item in records:
        if not isinstance(item,dict):raise ValueError('Standard decisions must be objects')
        sid=item.get('standard_id')
        if not isinstance(sid,str) or sid not in known or sid in ids:raise ValueError('Distinct registered project standard IDs required')
        ids.add(sid);standard=known[sid]
        decision=item.get('applicability')
        if decision not in {'adopted','not_applicable','historical_reference'} or not text(item.get('reason')):
            raise ValueError('Standard applicability decision and source-specific reason required')
        if item.get('number')!=standard['number']:errors.append('STANDARDS_EDITION_MISMATCH:'+sid)
        if decision=='not_applicable':continue
        version=item.get('version_evidence',{})
        if not isinstance(version,dict):raise ValueError('Version evidence must be an object')
        if (not isinstance(version,dict) or version.get('source_kind') not in {'official_issuer','official_catalogue'}
                or not https(version.get('url')) or not text(version.get('locator'))):
            errors.append('STANDARDS_OFFICIAL_VERSION_EVIDENCE:'+sid)
        else:
            checked=day(version.get('checked_on'))
            if checked>reviewed:errors.append('STANDARDS_FUTURE_VERIFICATION:'+sid)
            if checked<day(standard['checked_on']):errors.append('STANDARDS_VERSION_RECHECK:'+sid)
        if decision=='historical_reference':
            if not reference_only:errors.append('STANDARDS_HISTORICAL_ADOPTION:'+sid)
            limitations.append(sid+': historical reproduction only')
            continue
        adopted+=1;covered.add(standard['layer'])
        if standard.get('superseded_by') or standard['status_observed'] in {'replacement_reported','withdrawn','draft','planned'}:
            errors.append('STANDARDS_REPLACED:'+sid)
        if version.get('status')!='current':errors.append('STANDARDS_STATUS_UNVERIFIED:'+sid)
        effective=version.get('effective_on')
        if not effective:errors.append('STANDARDS_EFFECTIVE_DATE_REQUIRED:'+sid)
        else:
            if day(effective)>reviewed:errors.append('STANDARDS_NOT_EFFECTIVE:'+sid)
            if standard.get('effective_on') and effective!=standard['effective_on']:
                errors.append('STANDARDS_EFFECTIVE_DATE_MISMATCH:'+sid)
        jurisdiction=standard['jurisdiction']
        if jurisdiction.endswith('_contract'):
            if not text(item.get('contract_adoption')):errors.append('STANDARDS_CONTRACT_ADOPTION:'+sid)
        elif project['jurisdiction'].split('/')[0]!=jurisdiction:
            errors.append('STANDARDS_JURISDICTION:'+sid)
        if ('general' not in standard['disciplines'] and project['discipline'] not in standard['disciplines']
                and not text(item.get('related_discipline_basis'))):
            errors.append('STANDARDS_DISCIPLINE:'+sid)
        read=item.get('read_level')
        if read not in {'metadata','clauses'}:raise ValueError('Explicit metadata/clauses read level required')
        checks=item.get('checks')
        if not isinstance(checks,list):raise ValueError('Explicit clause/check inventory required')
        if not reference_only and (read!='clauses' or not checks):errors.append('STANDARDS_CLAUSE_REVIEW_REQUIRED:'+sid)
        passed=0
        for check in checks:
            if not isinstance(check,dict):raise ValueError('Clause checks must be objects')
            if any(not text(check.get(k)) for k in ('clause','requirement','result')):
                raise ValueError('Clause locator, scoped requirement and result required')
            outcome=check['result']
            if outcome not in {'pass','fail','not_checked','not_applicable'}:raise ValueError('Unknown standards check result')
            if outcome=='not_applicable':
                if not text(check.get('reason')):raise ValueError('Clause exclusion reason required')
                continue
            if outcome=='pass':
                passed+=1
                if read!='clauses':errors.append('STANDARDS_METADATA_NOT_COMPLIANCE:'+sid)
                if not _artifact(check.get('evidence'),directory,digest):errors.append('STANDARDS_CHECK_EVIDENCE:'+sid)
            else:errors.append('STANDARDS_CHECK_'+outcome.upper()+':'+sid)
        if not reference_only and not passed:errors.append('STANDARDS_NO_APPLICABLE_CHECK:'+sid)
    if not reference_only and not adopted:errors.append('STANDARDS_ADOPTION_REQUIRED')
    for name,decision in layers.items():
        if decision['status']=='covered' and name not in covered:errors.append('STANDARDS_LAYER_WITHOUT_BASIS:'+name)
    if reference_only:limitations.append('Current-standard technical compliance is not assessed; preserve source and report discrepancies without redesign')
    return {'basis_record_accepted':not errors,'errors':list(dict.fromkeys(errors)),
            'scope':mode,'supported_claim':'reference_fidelity_only' if reference_only else 'declared_checks_with_evidence',
            'drawing_sha256':digest,'standards_considered':len(records),'limitations':limitations,
            'standards_compliance_certified':False,'engineering_approval':False,
            'limits':'Checks record identity, applicability declarations, editions and evidence binding; does not prove source authenticity, clause interpretation, full-code coverage or professional approval'}
