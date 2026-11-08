"""Industry-scoped drawing requirements and standards assignment isolation.

This registry routes work. It cannot certify standard clauses, engineering design,
native-software interoperability or the truth of a client's source interpretation.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from .storage import ROOT


def _resource(name):
    candidates = [ROOT, Path(__file__).resolve().parents[2], Path(__file__).resolve().parents[1]]
    path = next((root/'references'/name for root in candidates if (root/'references'/name).is_file()), None)
    if path is None:
        raise ValueError('Complete Skill industry resource missing: '+name)
    return json.loads(path.read_text(encoding='utf-8'))


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _ids(values, name):
    if not isinstance(values, list) or not values or any(not _text(v) for v in values) or len(set(values)) != len(values):
        raise ValueError(name+' must be a nonempty list of distinct identifiers')
    return values


def catalogue():
    """Resolve dated standards metadata with explicit per-industry allowlists.

    Existing standards stay in their owning catalogue. A general tag never grants
    implicit access: even a shared standard requires an explicit industry allowlist.
    """
    data = _resource('industry-delivery.json')
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported industry registry schema')
    date.fromisoformat(data['checked_on'])
    industries = data.get('industries')
    if not isinstance(industries, list) or not industries:
        raise ValueError('Nonempty industries required')
    industry_ids = _ids([p.get('id') for p in industries], 'industries')
    source = _resource('standards-catalogue.json')
    inherited = {s['id']: s for s in source['standards']}
    additions = data.get('additional_standards', [])
    if not isinstance(additions, list):
        raise ValueError('additional_standards must be a list')
    for row in additions:
        if not isinstance(row, dict) or row.get('id') in inherited:
            raise ValueError('Additional standard IDs must be distinct from existing standards')
        inherited[row['id']] = row
    permissions = data.get('standard_industry_allowlist', {})
    if not isinstance(permissions, dict) or set(permissions)-set(inherited):
        raise ValueError('Allowlist refers to unknown standards')
    standards = []
    for standard_id, allowed in permissions.items():
        _ids(allowed, 'standard industry allowlist')
        if set(allowed)-set(industry_ids):
            raise ValueError('Standard allowlist refers to unknown industry')
        row = copy.deepcopy(inherited[standard_id])
        for key in ('number', 'title', 'source_url', 'evidence_level'):
            if not _text(row.get(key)):
                raise ValueError('Missing standard metadata: '+standard_id+'.'+key)
        url = urlsplit(row['source_url'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError('Public HTTPS standard source required')
        row['industry_ids'] = list(allowed)
        row['automatic_application'] = False
        row['project_clause_review_required'] = True
        standards.append(row)
    known = {s['id']: s for s in standards}
    drawing_ids = set()
    for profile in industries:
        if not _text(profile.get('title')) or not isinstance(profile.get('drawing_types'), list) or not profile['drawing_types']:
            raise ValueError('Each industry needs a title and drawing types')
        _ids(profile.get('standard_ids'), 'profile standard_ids')
        for sid in profile['standard_ids']:
            if sid not in known or profile['id'] not in known[sid]['industry_ids']:
                raise ValueError('Profile uses a standard outside its explicit allowlist')
        for drawing in profile['drawing_types']:
            identifier = drawing.get('id')
            if not _text(identifier) or not identifier.startswith(profile['id']+'.') or identifier in drawing_ids:
                raise ValueError('Distinct industry-qualified drawing IDs required')
            drawing_ids.add(identifier)
            if not _text(drawing.get('title')):
                raise ValueError('Drawing title required')
            _ids(drawing.get('required_checks'), 'drawing required_checks')
        if not profile.get('professional_checks') or not profile.get('scope_limit'):
            raise ValueError('Professional checks and scope limits must be explicit')
    return {**copy.deepcopy(data), 'standards': standards,
            'scope': 'Industry planning and standards assignment, not all-industry engineering certification',
            'auto_apply': False, 'engineering_approval': False,
            'unknown_industry_policy': 'reject_and_add_verified_profile'}


def get_profile(industry_id):
    if not _text(industry_id):
        raise ValueError('Industry ID required')
    value = next((row for row in catalogue()['industries'] if row['id'] == industry_id), None)
    if value is None:
        raise ValueError('Unknown industry: add a verified profile; do not substitute another industry')
    return value


def route(industry_ids, drawing_types=None, jurisdiction='CN'):
    _ids(industry_ids, 'industry_ids')
    if not _text(jurisdiction):
        raise ValueError('Jurisdiction required')
    jurisdiction = {'CN-BJ': 'CN-Beijing', 'CN-11': 'CN-Beijing'}.get(jurisdiction, jurisdiction)
    data = catalogue()
    known = {p['id']: p for p in data['industries']}
    if set(industry_ids)-known.keys():
        raise ValueError('Unknown industry: add a verified profile; no fallback allowed')
    selected = [known[key] for key in industry_ids]
    drawings = {d['id']: {**d, 'industry_id': p['id']} for p in selected for d in p['drawing_types']}
    if drawing_types is not None:
        _ids(drawing_types, 'drawing_types')
        if set(drawing_types)-drawings.keys():
            raise ValueError('Drawing type belongs to an unselected or unknown industry')
        drawings = {key: drawings[key] for key in drawing_types}
    allowed_ids = {sid for p in selected for sid in p['standard_ids']}
    standards = []
    for row in data['standards']:
        if row['id'] not in allowed_ids:
            continue
        area = row.get('jurisdiction', 'CN')
        applicable = area == jurisdiction or (jurisdiction.startswith('CN-') and area == 'CN') or area.endswith('_contract')
        if applicable:
            standards.append(row)
    return {'industry_ids': list(industry_ids), 'jurisdiction': jurisdiction,
            'industries': selected, 'drawing_types': list(drawings.values()),
            'standards': standards, 'auto_apply': False,
            'engineering_approval': False, 'cross_industry_defaults_inherited': False,
            'scope': 'Candidate discovery; select editions, clauses, project requirements and evidence before use'}


def validate_assignments(industry_ids, assignments, jurisdiction='CN'):
    """Reject unknown, cross-industry and unevidenced clause assertions.

    A valid assignment is NOT a compliance result. Project delivery review must
    still open and hash the actual source/evidence, check each adopted clause,
    and validate all customer requirements against the final drawing.
    """
    _ids(industry_ids, 'industry_ids')
    if not _text(jurisdiction):
        raise ValueError('Jurisdiction required')
    jurisdiction = {'CN-BJ': 'CN-Beijing', 'CN-11': 'CN-Beijing'}.get(jurisdiction, jurisdiction)
    data = catalogue()
    profiles = {p['id']: p for p in data['industries']}
    standards = {s['id']: s for s in data['standards']}
    findings = []
    if set(industry_ids)-profiles.keys():
        findings.append({'kind': 'unknown_industry', 'ids': sorted(set(industry_ids)-profiles.keys())})
    if not isinstance(assignments, list) or not assignments:
        return {'ok': False, 'findings': [*findings, {'kind': 'standards_assignments_required'}],
                'standards_compliance_certified': False, 'engineering_approval': False}
    seen = set()
    covered = set()
    for index, assignment in enumerate(assignments):
        if not isinstance(assignment, dict):
            findings.append({'kind': 'assignment_not_object', 'index': index})
            continue
        industry_id, standard_id = assignment.get('industry_id'), assignment.get('standard_id')
        if not isinstance(industry_id, str) or not isinstance(standard_id, str):
            findings.append({'kind': 'assignment_identity_required', 'index': index})
            continue
        key = (industry_id, standard_id)
        if key in seen:
            findings.append({'kind': 'duplicate_standard_assignment', 'index': index})
        seen.add(key)
        if industry_id not in industry_ids or industry_id not in profiles:
            findings.append({'kind': 'unselected_industry_assignment', 'index': index, 'industry_id': industry_id})
            continue
        if standard_id not in standards:
            findings.append({'kind': 'unknown_standard', 'index': index, 'standard_id': standard_id})
            continue
        row = standards[standard_id]
        if industry_id not in row['industry_ids'] or standard_id not in profiles[industry_id]['standard_ids']:
            findings.append({'kind': 'cross_industry_standard', 'index': index,
                             'industry_id': industry_id, 'standard_id': standard_id})
            continue
        covered.add(industry_id)
        area = row.get('jurisdiction', 'CN')
        if not (area == jurisdiction or (jurisdiction.startswith('CN-') and area == 'CN') or area.endswith('_contract')):
            findings.append({'kind': 'cross_jurisdiction_standard', 'index': index,
                             'project_jurisdiction': jurisdiction, 'standard_jurisdiction': area})
        if assignment.get('number', row['number']) != row['number'] or assignment.get('standard_number', row['number']) != row['number']:
            findings.append({'kind': 'standard_edition_identity_mismatch', 'index': index})
        if assignment.get('source_url', row['source_url']) != row['source_url']:
            findings.append({'kind': 'standard_source_identity_mismatch', 'index': index})
        if row.get('superseded_by') or row.get('status_observed') in {'superseded', 'withdrawn', 'catalogue_withdrawn'}:
            findings.append({'kind': 'superseded_standard', 'index': index})
        # A catalogue/announcement cannot substantiate a claimed adopted clause.
        clauses = assignment.get('clauses')
        if assignment.get('claims_compliance') is True or clauses:
            evidence = assignment.get('clause_evidence')
            if (not isinstance(clauses, list) or not clauses or any(not _text(c) for c in clauses)
                    or not isinstance(evidence, dict) or evidence.get('level') != 'project_clause_review'
                    or not _text(evidence.get('source_locator'))
                    or not re.fullmatch('[a-fA-F0-9]{64}', str(evidence.get('source_sha256', '')))
                    or not re.fullmatch('[a-fA-F0-9]{64}', str(evidence.get('review_sha256', '')))):
                findings.append({'kind': 'unevidenced_clause_claim', 'index': index})
        if assignment.get('engineering_approved') is True:
            findings.append({'kind': 'engineering_approval_not_provided_by_registry', 'index': index})
    for missing in sorted(set(industry_ids)-covered):
        findings.append({'kind': 'industry_standard_assignment_missing', 'industry_id': missing})
    for rule in data.get('exclusive_standard_systems', []):
        for industry_id in set(industry_ids).intersection(rule['industry_ids']):
            adopted = {sid for pid, sid in seen if pid == industry_id}
            selected_systems = sum(bool(adopted.intersection(group)) for group in rule['alternatives'])
            if selected_systems > 1:
                findings.append({'kind': 'standard_system_conflict', 'industry_id': industry_id,
                                 'rule_id': rule['id'], 'resolution': rule['on_conflict']})
    return {'ok': not findings, 'findings': findings, 'assigned_industries': sorted(covered),
            'jurisdiction': jurisdiction,
            'scope': 'Industry assignment isolation and record shape only; source truth and adopted clauses need delivery review',
            'standards_compliance_certified': False, 'engineering_approval': False}
