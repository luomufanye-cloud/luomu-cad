"""Customer-bound, fail-closed delivery review of actual saved artifacts.

This module never certifies a profession or authenticates a reviewer's identity.
It verifies evidence bindings and re-runs supported measurements. Visual and
professional observations remain independently supplied review inputs.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
import copy
import hashlib
import json
import math
from pathlib import Path
import re

import ezdxf

from .professional import measure, style_findings
from .qa import audit_dxf
from .storage import digest


SHA = re.compile(r'^[a-f0-9]{64}$')
SCOPES = {'reference_redraw', 'drawing_delivery', 'engineering_delivery'}
FORMATS = {'dxf', 'pdf', 'step', 'stp', 'ifc', 'dwg'}
EXPECTED_FIELDS = {'dxf':{'units','entity_counts','required_layers'},
                   'pdf':{'page_count','paper_mm','lineweights_mm','scale_denominator'},
                   'step':{'measurements'},'stp':{'measurements'},
                   'ifc':{'schema','element_counts','void_count','fill_count','element_volume_m3'},
                   'dwg':set()}


def _text(value):
    return isinstance(value, str) and value.strip() and value.casefold() not in {'pending', 'todo', 'unknown', 'pass', 'ok'}


def _rows(value, name, nonempty=True):
    if not isinstance(value, list) or (nonempty and not value) or any(not isinstance(row, dict) for row in value):
        raise ValueError(name + ' must be a ' + ('nonempty ' if nonempty else '') + 'list of objects')
    return value


def _unique(rows, field='id'):
    identifiers = [row.get(field) for row in rows]
    if any(not _text(value) for value in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError('Distinct nonempty ' + field + ' values required')
    return {row[field]: row for row in rows}


def _number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(name + ' requires a finite ' + ('positive ' if positive else '') + 'number')
    return float(value)


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file(record, base):
    if not isinstance(record, dict) or not _text(record.get('path')) or not SHA.fullmatch(str(record.get('sha256', ''))):
        raise ValueError('File path and lowercase SHA256 required')
    path = (base / record['path']).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise ValueError('File must exist inside the authorized review directory')
    if _hash(path) != record['sha256']:
        raise ValueError('Missing, stale or changed file: ' + record['path'])
    return path


def template(industry_ids, requirements=None):
    """Return an incomplete contract; a generated template is never an acceptance."""
    from .industry import route
    guidance = route(industry_ids)
    return {'schema_version': 1, 'contract_id': '', 'scope': 'drawing_delivery', 'jurisdiction':'CN',
            'industries': list(industry_ids), 'producer_id': '',
            'customer_brief': {'path': '', 'sha256': ''}, 'raw_sources': [],
            'standard_assignments': [], 'artifacts': [],
            'requirements': copy.deepcopy(requirements or []),
            'independent_review': {'path': '', 'sha256': ''},
            'guidance': guidance, 'accepted_for_delivery': False}


def _painted_widths(page, reader, user_unit):
    """Read effective widths at actual path-stroking operators, not idle w tokens."""
    from pypdf.generic import ContentStream

    def multiply(left,right):
        a,b,c,d=left;aa,bb,cc,dd=right
        return (a*aa+c*bb,b*aa+d*bb,a*cc+c*dd,b*cc+d*dd)

    def walk(stream,resources,initial=(1.,0.,0.,1.),initial_width=1.,initial_alpha=1.,depth=0):
        if depth>12:
            raise ValueError('PDF Form nesting exceeds the supported inspection depth')
        transform,width,alpha=initial,initial_width,initial_alpha
        stack=[];has_path=False;result=[]
        for args,op in ContentStream(stream,reader).operations:
            if op==b'q':stack.append((transform,width,alpha))
            elif op==b'Q':
                if not stack:raise ValueError('Unbalanced PDF graphic state')
                transform,width,alpha=stack.pop()
            elif op==b'cm':
                a,b,c,d,_,_=map(float,args);transform=multiply(transform,(a,b,c,d))
            elif op==b'w':
                width=float(args[0])
                if not math.isfinite(width) or width<0:raise ValueError('Invalid PDF stroke width')
            elif op==b'gs':
                settings=resources.get('/ExtGState',{}).get(args[0])
                if settings is not None:
                    settings=settings.get_object()
                    if '/LW' in settings:width=float(settings['/LW'])
                    if '/CA' in settings:alpha=float(settings['/CA'])
            elif op in {b'm',b'l',b'c',b'v',b'y',b're'}:has_path=True
            elif op in {b'S',b's',b'B',b'B*',b'b',b'b*'}:
                if has_path and alpha>0:
                    a,b,c,d=transform;sx,sy=math.hypot(a,b),math.hypot(c,d)
                    if (not math.isclose(sx,sy,rel_tol=1e-5,abs_tol=1e-8)
                            or abs(a*c+b*d)>1e-5*max(sx*sy,1e-8)):
                        raise ValueError('Nonuniform PDF painted stroke needs a dedicated physical-width adapter')
                    physical=width*sx*user_unit*25.4/72
                    if not math.isfinite(physical) or physical<0:raise ValueError('Invalid PDF painted stroke width')
                    result.append(physical)
                has_path=False
            elif op in {b'f',b'f*',b'F',b'n'}:has_path=False
            elif op==b'Do':
                target=resources.get('/XObject',{}).get(args[0])
                if target is not None:
                    target=target.get_object()
                    if target.get('/Subtype')=='/Form':
                        a,b,c,d,_,_=map(float,target.get('/Matrix',[1,0,0,1,0,0]))
                        result.extend(walk(target,target.get('/Resources',resources),
                            multiply(transform,(a,b,c,d)),width,alpha,depth+1))
        if stack:raise ValueError('Unbalanced PDF graphic state')
        return result

    return walk(page.get_contents(),page.get('/Resources',{}))


def _pdf(path, expected):
    from pypdf import PdfReader
    import pypdfium2 as pdfium
    from PIL import ImageChops, Image
    reader = PdfReader(path)
    if reader.is_encrypted:
        raise ValueError('Encrypted PDF cannot be accepted without authorized readable content')
    count = expected.get('page_count')
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError('Expected PDF page_count is required')
    if len(reader.pages) != count:
        raise ValueError('PDF page count differs from the customer contract')
    paper = expected.get('paper_mm')
    if not isinstance(paper, list) or len(paper) != 2:
        raise ValueError('Expected PDF paper_mm=[width,height] required')
    paper = [_number(v, 'paper size', True) for v in paper]
    pdf = pdfium.PdfDocument(path)
    pages = []
    try:
        for index, page in enumerate(reader.pages):
            user_unit = _number(float(page.get('/UserUnit', 1)), 'PDF UserUnit', True)
            actual = [float(page.mediabox.width)*25.4/72*user_unit,
                      float(page.mediabox.height)*25.4/72*user_unit]
            if any(abs(a-b) > .05 for a,b in zip(actual, paper)):
                raise ValueError('PDF paper size differs on page ' + str(index+1))
            native = pdf[index]
            bitmap = None
            try:
                # Render from PDF data, independently of any producer PNG or report.
                scale = min(1.25, 1800/max(native.get_size()))
                bitmap = native.render(scale=scale)
                image = bitmap.to_pil().convert('RGB')
                extrema = image.convert('L').getextrema()
                diff = ImageChops.difference(image, Image.new('RGB', image.size, 'white')).convert('L')
                ink = sum(count for value, count in enumerate(diff.histogram()) if value > 12)
                if extrema[1]-extrema[0] < 8 or ink < 25:
                    raise ValueError('PDF page is blank or has no usable drawing content: ' + str(index+1))
            finally:
                if bitmap is not None:
                    bitmap.close()
                native.close()
            widths = _painted_widths(page,reader,user_unit)
            for target in expected.get('lineweights_mm', []):
                target = _number(target, 'paper lineweight', True)
                if not any(abs(value-target) <= .003 for value in widths):
                    raise ValueError('Expected physical lineweight absent: ' + str(target))
            pages.append({'page':index+1,'paper_mm':actual,'rendered_ink_pixels':ink,
                          'lineweights_mm':sorted(set(round(v,5) for v in widths))})
    finally:
        pdf.close()
    return {'format':'pdf','reopened':True,'pages':pages}


def _dimension_display_value(entity, dimension, overrides):
    """Parse one supported automatic display using ezdxf's control decoding.

    Dimension.get_measurement() is in WCS length units, or degrees for types
    2/5. The installed renderer uses R, %%c (plain_text -> Ø), and ° for the
    ordinary radial/diametric/decimal-degree displays. We do not strip arbitrary
    symbols or accept either reflex angle to make a bad cache appear correct.
    """
    kind=dimension.dimtype
    if kind not in {0,1,2,3,4,5}:
        raise ValueError('Native dimension type needs a dedicated display adapter')
    if any(overrides.get(key,0) for key in ('dimtol','dimlim','dimalt')):
        raise ValueError('Tolerance, limits or alternate units need a dedicated dimension-display adapter')
    if overrides.get('dimrnd',0):
        raise ValueError('Rounded dimension increments need an explicit precision adapter')
    angular=kind in {2,5}
    if angular and overrides.get('dimaunit',0)!=0:
        raise ValueError('Only automatic decimal-degree angular display is currently supported')
    if not angular and overrides.get('dimlunit',2)!=2:
        raise ValueError('Nondecimal length display needs its own verified unit adapter')
    raw=entity.dxf.text
    if re.search(r'\\[SPsp]',raw):
        raise ValueError('Stacked or multiline dimensions need a dedicated display adapter')
    plain=entity.plain_text().strip()
    separator=overrides.get_decimal_separator()
    if separator not in {'.',','}:
        raise ValueError('Unsupported dimension decimal separator')
    number=r'[+-]?(?:\d+(?:'+re.escape(separator)+r'\d*)?|'+re.escape(separator)+r'\d+)'
    prefix={0:'',1:'',2:'',3:r'[Øø⌀]',4:'R',5:''}[kind]
    suffix='°' if angular else ''
    match=re.fullmatch(prefix+r'\s*('+number+r')\s*'+suffix,plain)
    if match is None:
        raise ValueError('Native automatic dimension symbol/unit/display format is unsupported or inconsistent with its type')
    value=float(match[1].replace(separator,'.'))
    if not math.isfinite(value):raise ValueError('Invalid native dimension display value')
    decimals=overrides.get('dimadec',2) if angular else overrides.get('dimdec',2)
    if angular and decimals==-1:decimals=overrides.get('dimdec',2)
    if isinstance(decimals,bool) or not isinstance(decimals,int) or not 0<=decimals<=8:
        raise ValueError('Dimension precision needs an explicit supported decimal definition')
    tolerance=10**(-decimals)/2+1e-7
    return value,plain,tolerance


def _native_dimensions(doc):
    from ezdxf.math import Matrix44,Vec3
    result=[];visited=0

    def visit(layout, transform, ancestry=(), names=()):
        nonlocal visited
        for entity in layout:
            visited+=1
            if visited>100000 or len(names)>16:
                raise ValueError('Native INSERT inspection limit exceeded')
            if entity.dxftype()=='INSERT':
                block=entity.block();name=entity.dxf.name.casefold()
                if block is None or block.block.is_xref or name in names:
                    raise ValueError('Unresolved, cyclic or externally referenced INSERT cannot be accepted')
                combined=Matrix44.chain(entity.matrix44(),transform)
                axes=[combined.transform_direction(Vec3(axis)) for axis in [(1,0,0),(0,1,0),(0,0,1)]]
                lengths=[a.magnitude for a in axes]
                if (any(not math.isfinite(v) or v<=0 for v in lengths)
                        or not all(math.isclose(lengths[0],v,rel_tol=1e-8,abs_tol=1e-8) for v in lengths)
                        or any(abs(axes[a].dot(axes[b]))>1e-7*lengths[a]*lengths[b] for a,b in [(0,1),(0,2),(1,2)])):
                    raise ValueError('Nonuniform or sheared INSERT needs a dedicated native-dimension adapter')
                visit(block,combined,(*ancestry,entity.dxf.handle),(*names,name))
                continue
            if entity.dxftype()!='DIMENSION':continue
            value=entity.get_measurement()
            if not isinstance(value,(float,int)) or not math.isfinite(value):
                raise ValueError('Unsupported or invalid native dimension measurement')
            scale=transform.transform_direction(Vec3(1,0,0)).magnitude
            if entity.dimtype not in {2,5}:
                value*=scale
            overrides=entity.override()
            if entity.dxf.get('text','<>') not in ('','<>') or overrides.get('dimlfac',1)!=1:
                raise ValueError('Native dimension text/factor override requires a dedicated approved adapter')
            block_name=entity.dxf.get('geometry','')
            if block_name not in doc.blocks:raise ValueError('Native dimension has no display block')
            texts=[e for e in doc.blocks[block_name] if e.dxftype() in {'TEXT','MTEXT'}]
            if len(texts)!=1:
                raise ValueError('Ordinary native dimensions need one automatic display text; composite display needs a dedicated adapter')
            shown,plain,tolerance=_dimension_display_value(texts[0],entity,overrides)
            if abs(shown-value)>tolerance:
                raise ValueError('Native dimension display does not match transformed measured geometry: '+ '/'.join((*ancestry,entity.dxf.handle)))
            result.append({'handle':entity.dxf.handle,'instance_path':list(ancestry),
                           'dimtype':entity.dimtype,'unit':'degrees' if entity.dimtype in {2,5} else 'drawing_units',
                           'measured':float(value),'display':[shown],'display_text':plain,'world_scale':scale})
    for layout in doc.layouts:
        visit(layout,Matrix44(),(layout.name,))
    return result


def _dxf(path, expected):
    doc = ezdxf.readfile(path)
    units = expected.get('units')
    if isinstance(units, bool) or not isinstance(units,int) or doc.units != units:
        raise ValueError('Native DXF units differ or are unspecified')
    entities = list(doc.modelspace())
    if not entities:
        raise ValueError('Empty modelspace cannot be accepted')
    audit = doc.audit()
    if audit.errors or audit.fixes:
        raise ValueError('DXF needs structural repairs')
    basic = audit_dxf(path)
    # audit_dxf has an explicit-mm default; a customer's declared native units
    # can differ, while its structural/geometry findings still apply unchanged.
    basic_findings = [finding for finding in basic['findings'] if finding['kind'] != 'units_not_mm']
    if basic_findings:
        raise ValueError('DXF structural/geometry/annotation problems: ' + json.dumps(basic_findings))
    # Native dimension definitions alone do not prove their display is current.
    dimensions=_native_dimensions(doc)
    counts=dict(Counter(e.dxftype() for e in entities))
    if 'entity_counts' in expected:
        declared=expected['entity_counts']
        if (not isinstance(declared,dict) or any(isinstance(v,bool) or not isinstance(v,int) or v<0 for v in declared.values())
                or declared!=counts):
            raise ValueError('DXF native entity counts differ from customer expectations')
    if 'required_layers' in expected:
        if not isinstance(expected['required_layers'],list) or any(not isinstance(v,str) or v not in doc.layers for v in expected['required_layers']):
            raise ValueError('DXF required layers are missing or invalid')
    return {'format':'dxf','reopened':True,'units':doc.units,'entity_types':dict(Counter(e.dxftype() for e in entities)),
            'dimension_readback':dimensions},doc


def _ifc_expectations(actual,expected):
    if not expected:
        raise ValueError('IFC delivery needs explicit customer schema/geometry expectations')
    if 'schema' in expected and actual.get('schema')!=expected['schema']:
        raise ValueError('IFC schema differs from the customer contract')
    if 'element_counts' in expected:
        counts=expected['element_counts']
        if not isinstance(counts,dict) or not counts:
            raise ValueError('IFC element_counts must identify classes and exact counts')
        measured=Counter(row['class'] for row in actual['elements'])
        for key,value in counts.items():
            if isinstance(value,bool) or not isinstance(value,int) or value<0 or measured.get(key,0)!=value:
                raise ValueError('IFC represented element count differs: '+str(key))
    for key,source in [('void_count','voids'),('fill_count','fills')]:
        if key in expected:
            bounds=expected[key]
            if not isinstance(bounds,list) or len(bounds)!=2:
                raise ValueError('IFC relation counts need explicit [min,max] intervals')
            lo,hi=[_number(v,key) for v in bounds]
            if lo>hi or not lo<=len(actual[source])<=hi:
                raise ValueError('IFC relation count differs: '+key)
    if 'element_volume_m3' in expected:
        volumes=expected['element_volume_m3']
        if not isinstance(volumes,dict) or not volumes:
            raise ValueError('IFC element_volume_m3 must map GlobalIds to intervals')
        measured={row['id']:row['net_volume_m3'] for row in actual['elements']}
        for key,bounds in volumes.items():
            if not isinstance(bounds,list) or len(bounds)!=2:
                raise ValueError('IFC volumes need explicit [min,max] intervals')
            lo,hi=[_number(v,'IFC volume') for v in bounds]
            if lo>hi or key not in measured or not lo<=measured[key]<=hi:
                raise ValueError('IFC element volume differs: '+str(key))


def _image(path):
    from PIL import Image
    with Image.open(path) as image:
        image.load()
        if min(image.size) < 32:
            raise ValueError('Review image is too small to inspect')
        lo,hi=image.convert('L').getextrema()
        if hi-lo < 8:
            raise ValueError('Review image is blank')
        return {'width':image.width,'height':image.height}


def _pdf_correspondence(pdf_path, dxf_path, check, expected):
    """Re-render the reopened DXF, then compare the actual delivered PDF page.

    This adapter applies to a single-page export using the declared project
    window/scale. Other plotting systems require their own measured adapter;
    a nonblank but unrelated PDF is never accepted as a matching export.
    """
    import pypdfium2 as pdfium
    from PIL import ImageChops
    from .pdf_export import render_pdf
    if expected.get('page_count') != 1:
        raise ValueError('DXF/PDF correspondence currently needs a single-page sheet')
    scale = _number(check.get('scale'), 'PDF model scale', True)
    window = check.get('window_mm')
    if not isinstance(window,list) or len(window) != 4:
        raise ValueError('Correspondence needs the source model window')
    margin = _number(check.get('margin_mm',10), 'PDF margin')
    data,settings = render_pdf(dxf_path, expected['paper_mm'], window, scale, margin)
    candidate = pdfium.PdfDocument(pdf_path)
    reference = pdfium.PdfDocument(data)
    images=[]
    try:
        for document in (candidate,reference):
            page=document[0];bitmap=None
            try:
                bitmap=page.render(scale=3)
                images.append(bitmap.to_pil().convert('RGB').copy())
            finally:
                if bitmap is not None:bitmap.close()
                page.close()
    finally:
        candidate.close();reference.close()
    if images[0].size != images[1].size:
        return {'passed':False,'reason':'rendered page sizes differ'}
    diff=ImageChops.difference(*images).convert('L')
    changed=sum(n for value,n in enumerate(diff.histogram()) if value>8)
    fraction=changed/(images[0].width*images[0].height)
    # Fixed adapter tolerance, not a producer-selected threshold that can hide differences.
    return {'passed':fraction<=.00001,'changed_pixels':changed,'changed_fraction':fraction,
            'method':'actual PDF raster versus freshly exported reopened DXF at declared physical settings',
            'settings':settings}


def _brief(contract, base):
    path = _file(contract.get('customer_brief'),base)
    brief = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(brief,dict) or brief.get('schema_version') != 1:
        raise ValueError('Customer requirement inventory must be structured schema_version=1 JSON')
    if contract.get('scope') not in SCOPES or brief.get('scope') != contract.get('scope'):
        raise ValueError('Contract scope must match the original customer inventory')
    if not _text(brief.get('jurisdiction')) or contract.get('jurisdiction') != brief['jurisdiction']:
        raise ValueError('Contract jurisdiction must match the explicit original customer inventory')
    if not isinstance(brief.get('industries'),list) or not brief['industries'] or set(brief['industries']) != set(contract.get('industries',[])):
        raise ValueError('Industry selection differs from the original customer inventory')
    original = _unique(_rows(brief.get('requirements'),'customer requirements'))
    requested = _unique(_rows(contract.get('requirements'),'contract requirements'))
    if set(original) != set(requested):
        raise ValueError('Customer requirement IDs were omitted, added or replaced')
    for rid, requirement in original.items():
        if not _text(requirement.get('description')) or requirement.get('industry_id') not in brief['industries']:
            raise ValueError('Original requirement needs description and its declared industry')
        if not _text(requirement.get('source_locator')):
            raise ValueError('Original requirements need source page/object/brief locations')
        checks = _unique(_rows(requirement.get('checks'),'source measurement expectations'))
        actual = requested[rid]
        if (actual.get('industry_id') != requirement['industry_id'] or
                actual.get('description') != requirement['description'] or
                digest(actual.get('checks')) != digest(list(checks.values()))):
            raise ValueError('Customer requirement or expected measurements were weakened: '+rid)
    sheets = _unique(_rows(brief.get('required_sheets'),'customer sheet/format inventory'),'sheet_id')
    for sheet in sheets.values():
        if sheet.get('industry_id') not in brief['industries'] or not _text(sheet.get('drawing_type')):
            raise ValueError('Each required sheet needs an industry and qualified drawing type')
        if not isinstance(sheet.get('formats'),list) or not sheet['formats'] or set(sheet['formats'])-FORMATS:
            raise ValueError('Each sheet needs explicit supported delivery formats')
        if not isinstance(sheet.get('expected'),dict) or set(sheet['expected']) != set(sheet['formats']):
            raise ValueError('Customer sheets must fix readback expectations for every requested format')
    if ({row['industry_id'] for row in original.values()} != set(brief['industries'])
            or {row['industry_id'] for row in sheets.values()} != set(brief['industries'])):
        raise ValueError('Every declared industry needs actual customer requirements and corresponding sheets')
    return path,brief,original,requested,sheets


def review(contract:dict, base:Path):
    """Inspect a complete customer-bound delivery contract without altering CAD.

    accepted_for_delivery applies only to the exact contractual scope and files.
    Reviewer identities and professional credentials are declarations, not
    cryptographically authenticated or substitutes for statutory approval.
    """
    base = Path(base).resolve()
    findings = []
    artifact_results = []
    requirement_results = []
    tracked = {}

    def fail(code, **details):
        findings.append({'code':code,**details})

    result = {'schema_version':1,'accepted_for_delivery':False,'scope':contract.get('scope') if isinstance(contract,dict) else None,
              'findings':findings,'artifacts':artifact_results,'per_requirement':requirement_results,
              'engineering_approval':False,'recognition_accuracy_proven':False,
              'reviewer_identity_authenticated':False,
              'limits':'Evidence integrity and supported actual-file checks; not statutory approval or authentication of source interpretation/reviewer identity'}
    try:
        if not isinstance(contract,dict) or contract.get('schema_version') != 1 or not _text(contract.get('contract_id')):
            raise ValueError('Delivery contract needs schema_version=1 and contract_id')
        if not _text(contract.get('producer_id')):
            raise ValueError('Producer ID required to separate production and review')
        brief_path,brief,original,requested,sheets = _brief(contract,base)
        tracked[brief_path] = contract['customer_brief']['sha256']
        from .industry import catalogue, get_profile, validate_assignments
        profiles = {iid:get_profile(iid) for iid in brief['industries']}
        standards = {row['id']:row for row in catalogue()['standards']}
        for sheet in sheets.values():
            known = {row['id'] if isinstance(row,dict) else row for row in profiles[sheet['industry_id']]['drawing_types']}
            if sheet['drawing_type'] not in known:
                raise ValueError('Drawing type belongs to another industry or is unknown: '+sheet['drawing_type'])
        assignments = _rows(contract.get('standard_assignments'),'standards assignments')
        standard_check = validate_assignments(brief['industries'],assignments,jurisdiction=brief['jurisdiction'])
        result['standard_isolation'] = standard_check
        if not standard_check.get('ok'):
            fail('STANDARD_ASSIGNMENT_REJECTED', details=standard_check)
        covered_industries = set()
        for item in assignments:
            iid = item.get('industry_id')
            if iid not in brief['industries']:
                raise ValueError('Standard assigned outside selected industries')
            covered_industries.add(iid)
            if not _text(item.get('applicability_basis')):
                raise ValueError('Standard applicability basis must be explicit')
            decision = item.get('review_scope')
            if contract['scope'] == 'reference_redraw':
                if decision != 'reference_only':
                    raise ValueError('Reference reproduction cannot claim normative compliance')
            else:
                if decision != 'reviewed_clauses':
                    raise ValueError('Drawing/engineering delivery requires reviewed applicable clauses')
                standard = standards.get(item.get('standard_id'))
                if standard is None:
                    raise ValueError('Adopted standard must have verified registry metadata')
                version = item.get('version_evidence',{})
                if (version.get('number') != standard['number'] or version.get('source_url') != standard['source_url']
                        or version.get('status') != 'current'):
                    raise ValueError('Adopted standard version must match its verified registry source')
                checked = date.fromisoformat(version.get('checked_on',''))
                if checked > date.today() or checked < date.fromisoformat(standard.get('checked_on',catalogue()['checked_on'])):
                    raise ValueError('Adopted standard version evidence is stale or future-dated')
                clauses = _rows(item.get('clause_reviews'),'reviewed standard clauses')
                for clause in clauses:
                    if not _text(clause.get('locator')) or not _text(clause.get('interpretation')) or not clause.get('requirement_ids') or set(clause['requirement_ids'])-original.keys():
                        raise ValueError('Reviewed clauses must map actual customer requirements')
                    if any(original[rid]['industry_id'] != iid for rid in clause['requirement_ids']):
                        raise ValueError('Standard clauses cannot map requirements from another industry')
                    check_ids = {check['id'] for rid in clause['requirement_ids'] for check in original[rid]['checks']}
                    if not isinstance(clause.get('check_ids'),list) or not clause['check_ids'] or set(clause['check_ids'])-check_ids:
                        raise ValueError('Reviewed clauses must name executable customer check IDs')
                if {row['locator'] for row in clauses} != set(item.get('clauses', [])):
                    raise ValueError('Reviewed clause locators differ from the adopted standard assignment')
                standard_source = _file(item.get('source_evidence'),base)
                tracked[standard_source] = item['source_evidence']['sha256']
                claim = item.get('clause_evidence',{})
                if claim.get('source_sha256') != item['source_evidence']['sha256'] or claim.get('review_sha256') != item.get('evidence',{}).get('sha256'):
                    raise ValueError('Clause evidence is not bound to the actual source and review files')
            evidence = _file(item.get('evidence'),base)
            tracked[evidence] = item['evidence']['sha256']
            if evidence.stat().st_size < 10:
                raise ValueError('Standards decision evidence is empty')
        if covered_industries != set(brief['industries']):
            raise ValueError('Every selected industry needs its own applicable standards decision')
        for source in _rows(brief.get('raw_sources',[]),'raw sources',False):
            path = _file(source,base);tracked[path] = source['sha256']
        artifacts = _unique(_rows(contract.get('artifacts'),'delivery artifacts'))
        docs = {};paths = {};by_sheet = {};metadata = {}
        for aid,artifact in artifacts.items():
            entry = {'id':aid,'passed':False}
            artifact_results.append(entry)
            try:
                path = _file(artifact,base);tracked[path]=artifact['sha256'];paths[aid]=path
                fmt = artifact.get('format')
                if fmt not in FORMATS or path.suffix.lower().lstrip('.') != fmt:
                    raise ValueError('Explicit format must match the real file extension')
                sid = artifact.get('sheet_id')
                if sid not in sheets:
                    raise ValueError('Artifact is not in the customer sheet inventory')
                wanted = sheets[sid]
                if artifact.get('industry_id') != wanted['industry_id'] or artifact.get('drawing_type') != wanted['drawing_type'] or fmt not in wanted['formats']:
                    raise ValueError('Artifact industry/drawing type/format differs from the customer sheet')
                by_sheet.setdefault(sid,[]).append(fmt)
                expected = artifact.get('expected')
                if not isinstance(expected,dict):
                    raise ValueError('Artifact-specific readback expectations required')
                if set(expected)-EXPECTED_FIELDS[fmt]:
                    raise ValueError('Unsupported artifact expectations need a verified adapter: '+', '.join(sorted(set(expected)-EXPECTED_FIELDS[fmt])))
                if digest(expected) != digest(wanted['expected'][fmt]):
                    raise ValueError('Artifact readback expectations were weakened from the customer brief')
                if fmt == 'dxf':
                    data,docs[aid] = _dxf(path,expected)
                elif fmt == 'pdf':
                    data = _pdf(path,expected)
                elif fmt in {'step','stp'}:
                    from .cad_engines import inspect_step,check_contract
                    data=inspect_step(path)
                    if not data['valid'] or not expected.get('measurements') or check_contract(data,expected['measurements']):
                        raise ValueError('STEP kernel geometry/explicit dimensions failed')
                    data['reopened']=True
                elif fmt == 'ifc':
                    from .cad_engines import inspect_ifc
                    data=inspect_ifc(path)
                    if not data['valid']:
                        raise ValueError('IFC schema/native geometry/opening relations failed')
                    _ifc_expectations(data,expected)
                    data['reopened']=True
                else:
                    # A producer-authored JSON log cannot authenticate an actual AutoCAD reopen.
                    raise ValueError('DWG_LIVE_MCP_REVALIDATION_REQUIRED: offline receipt alone is not acceptance')
                metadata[aid]=data;entry.update(passed=True,actual=data)
            except Exception as error:
                entry['error']=str(error);fail('ARTIFACT_READBACK_FAILED',artifact_id=aid,error=str(error))
        for sid,sheet in sheets.items():
            if Counter(by_sheet.get(sid,[])) != Counter(sheet['formats']):
                fail('CUSTOMER_SHEET_FORMAT_MISSING_OR_DUPLICATED',sheet_id=sid,required=sheet['formats'],actual=by_sheet.get(sid,[]))
        review_path = _file(contract.get('independent_review'),base)
        tracked[review_path] = contract['independent_review']['sha256']
        independent = json.loads(review_path.read_text(encoding='utf-8-sig'))
        reviewer = independent.get('reviewer_id')
        if not _text(reviewer) or reviewer == contract['producer_id']:
            raise ValueError('Independent reviewer must differ from the producer')
        if independent.get('schema_version') != 1 or independent.get('contract_id') != contract['contract_id'] or independent.get('scope') != contract['scope']:
            raise ValueError('Independent review belongs to another contract or scope')
        if independent.get('customer_brief_sha256') != contract['customer_brief']['sha256']:
            raise ValueError('Independent review used a different customer brief')
        if independent.get('artifact_sha256') != {key:value['sha256'] for key,value in artifacts.items()}:
            raise ValueError('Independent review is stale for current delivery files')
        if independent.get('unresolved') != []:
            raise ValueError('Independent review still has unresolved findings')
        if independent.get('requirement_inventory_checked') is not True or not _text(independent.get('inventory_observation')):
            raise ValueError('Independent reviewer must check source requirement inventory completeness')
        observations = _unique(_rows(independent.get('requirements'),'independent requirement reviews'),'requirement_id')
        if set(observations) != set(original):
            raise ValueError('Independent review omitted customer requirements')
        referenced_artifacts = set()
        correspondences=set()
        for rid,requirement in requested.items():
            row={'id':rid,'passed':False,'checks':[]};requirement_results.append(row)
            start=len(findings)
            references=requirement.get('artifact_ids')
            if not isinstance(references,list) or not references or len(set(references))!=len(references) or set(references)-artifacts.keys():
                fail('REQUIREMENT_ARTIFACTS_REQUIRED',requirement_id=rid);continue
            referenced_artifacts.update(references)
            if any(artifacts[aid]['industry_id'] != requirement['industry_id'] for aid in references):
                fail('REQUIREMENT_INDUSTRY_CROSSOVER',requirement_id=rid)
            for check in requirement['checks']:
                checked={'id':check['id'],'passed':False};row['checks'].append(checked)
                aid=check.get('artifact_id')
                try:
                    if aid not in references or aid not in metadata:
                        raise ValueError('Check must inspect a successfully reopened requirement artifact')
                    if not _text(check.get('source_locator')):
                        raise ValueError('Check needs its independent source location')
                    kind=check.get('kind')
                    common={'id','kind','artifact_id','source_locator'}
                    extra={'dxf_measure':{'measurement'},'dxf_style':{'style'},'pdf_delivery':set(),
                        'pdf_dxf_correspondence':{'source_artifact_id','window_mm','scale','margin_mm'},'kernel_geometry':set()}
                    if kind not in extra or set(check)-(common|extra[kind]):
                        raise ValueError('Unsupported delivery check fields need an actual adapter')
                    if kind == 'dxf_measure':
                        if aid not in docs:
                            raise ValueError('Native DXF measurement requires a DXF artifact')
                        measurement=check['measurement']
                        geometry={'kind','handles','tolerance'}
                        fields={'count':{'kind','handles','range','types'},'dimension':{'kind','handles','range'},
                            'text':{'kind','handles','expected'},'contour':geometry|{'expected_points'},
                            'distance':geometry|{'other_handles','range'},'length':geometry|{'range'},
                            'closed':geometry|{'expected'},'area':geometry|{'range'},
                            'angle':geometry|{'expected','angle_tolerance'}}
                        if not isinstance(measurement,dict) or measurement.get('kind') not in fields or set(measurement)-fields[measurement['kind']]:
                            raise ValueError('Unsupported native measurement fields need an executed adapter')
                        actual=measure(docs[aid],check['measurement'])
                        checked.update(actual=actual,passed=actual['passed'])
                    elif kind == 'dxf_style':
                        if aid not in docs:
                            raise ValueError('DXF style measurement requires a DXF artifact')
                        rules=check['style']
                        if not isinstance(rules,dict) or set(rules)-{'basis','layers','building_base_mm'}:
                            raise ValueError('Unsupported style requirement fields')
                        for layer in rules.get('layers',{}).values():
                            if not isinstance(layer,dict) or set(layer)-{'lineweight_mm','linetypes','polyline_width'}:
                                raise ValueError('Unsupported layer-style requirement fields')
                        actual=style_findings(docs[aid],check['style'])
                        checked.update(actual=actual,passed=not actual['errors'])
                    elif kind == 'pdf_delivery':
                        if metadata[aid].get('format') != 'pdf':
                            raise ValueError('Paper review requires a real PDF')
                        checked.update(actual=metadata[aid],passed=True)
                    elif kind == 'pdf_dxf_correspondence':
                        source_id=check.get('source_artifact_id')
                        if metadata[aid].get('format') != 'pdf' or source_id not in references or source_id not in docs:
                            raise ValueError('PDF correspondence requires both its real PDF and reopened source DXF in the requirement')
                        if artifacts[aid]['sheet_id'] != artifacts[source_id]['sheet_id']:
                            raise ValueError('PDF and DXF must belong to the same customer sheet')
                        if ('scale_denominator' in artifacts[aid]['expected']
                                and artifacts[aid]['expected']['scale_denominator']!=check.get('scale')):
                            raise ValueError('PDF physical scale check differs from the customer scale denominator')
                        actual=_pdf_correspondence(paths[aid],paths[source_id],check,artifacts[aid]['expected'])
                        checked.update(actual=actual,passed=actual['passed'])
                        if actual['passed']:correspondences.add((source_id,aid))
                    elif kind == 'kernel_geometry':
                        if paths[aid].suffix.lower() not in {'.step','.stp','.ifc'}:
                            raise ValueError('Kernel geometry check requires STEP or IFC')
                        checked.update(actual=metadata[aid],passed=True)
                    else:
                        raise ValueError('Unsupported delivery check; add and test an actual adapter: '+str(kind))
                    if not checked['passed']:
                        fail('CUSTOMER_MEASUREMENT_FAILED',requirement_id=rid,check_id=check['id'])
                except Exception as error:
                    checked['error']=str(error);fail('CUSTOMER_CHECK_NOT_EXECUTED',requirement_id=rid,check_id=check['id'],error=str(error))
            observation=observations[rid]
            if observation.get('verdict') != 'accepted' or not _text(observation.get('finding')):
                fail('INDEPENDENT_REQUIREMENT_NOT_ACCEPTED',requirement_id=rid)
            seen=set()
            for evidence in _rows(observation.get('observations'),'independent artifact observations'):
                aid=evidence.get('artifact_id')
                if aid not in references or not all(_text(evidence.get(key)) for key in ('locator','source_locator','finding')):
                    fail('INDEPENDENT_OBSERVATION_UNBOUND',requirement_id=rid);continue
                seen.add(aid)
                if artifacts[aid]['format'] in {'pdf','dxf'}:
                    preview=_file(evidence.get('preview'),base);tracked[preview]=evidence['preview']['sha256'];_image(preview)
                if evidence.get('artifact_sha256') != artifacts[aid]['sha256']:
                    fail('INDEPENDENT_OBSERVATION_STALE',requirement_id=rid,artifact_id=aid)
            if seen != set(references):
                fail('INDEPENDENT_ARTIFACT_OBSERVATION_MISSING',requirement_id=rid)
            row['passed']=len(findings)==start
        if referenced_artifacts != artifacts.keys():
            fail('UNREVIEWED_DELIVERY_ARTIFACTS',artifact_ids=sorted(artifacts.keys()-referenced_artifacts))
        for sid,sheet in sheets.items():
            if {'dxf','pdf'} <= set(sheet['formats']):
                native=next((aid for aid,row in artifacts.items() if row.get('sheet_id')==sid and row.get('format')=='dxf'),None)
                paper=next((aid for aid,row in artifacts.items() if row.get('sheet_id')==sid and row.get('format')=='pdf'),None)
                if (native,paper) not in correspondences:
                    fail('PDF_DXF_CORRESPONDENCE_NOT_VERIFIED',sheet_id=sid)
        for aid,artifact in artifacts.items():
            if artifact.get('format')=='pdf' and 'scale_denominator' in artifact.get('expected',{}):
                if not any(paper==aid for _,paper in correspondences):
                    fail('PDF_PHYSICAL_SCALE_NOT_VERIFIED',artifact_id=aid)
        if contract['scope'] == 'engineering_delivery':
            fail('PROFESSIONAL_ENGINEERING_AUTHORITY_REQUIRED',reason='This tool cannot authenticate professional signatures, design calculations or statutory approval')
        for path,expected_hash in tracked.items():
            if _hash(path) != expected_hash:
                fail('INPUT_CHANGED_DURING_REVIEW',path=str(path))
        result['independent_reviewer_id']=reviewer
        result['evidence_files_checked']=len(tracked)
        result['accepted_for_delivery']=not findings and bool(requirement_results) and all(r['passed'] for r in requirement_results)
    except Exception as error:
        fail('DELIVERY_CONTRACT_INVALID',error=str(error))
    return result
