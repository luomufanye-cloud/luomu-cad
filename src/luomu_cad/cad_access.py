"""Cooperative CAD task ownership and comparison of recorded review states.

This module never connects to CAD. OS locks coordinate participating servers;
they do not lock the AutoCAD UI or unrelated adapters. Caller-supplied task
permissions record authorization, rather than authenticate it.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import re
import threading
import uuid

from .storage import Journal, atomic_json, digest, now, workspace_lock

PERMISSIONS={'edit','open','save','close','export'}
PASSIVE={'versions','list_documents','performance_snapshot'}
ACTIONS={
    'start':'open','new_document':'open','open_document':'open','activate_document':'open',
    'save_as':'save','close_document':'close','mutate':'edit','configure_text_style':'edit',
    'connect':None,'read':None,'native_facts':None,'native_entity_data':None,
    'presentation_snapshot':None,'delivery_snapshot':None,'preview':None,
}


def _permissions(value,defaults=None):
    if not isinstance(value,dict) or set(value)-PERMISSIONS or any(type(v) is not bool for v in value.values()):
        raise ValueError('permissions requires edit/open/save/close/export booleans')
    return {key:value.get(key,(defaults or {}).get(key,False)) for key in sorted(PERMISSIONS)}


class CadAccess:
    def __init__(self,root):
        self.root=Path(root).resolve()
        self._lock=threading.RLock()
        self._lease=None
        self._owner=None

    def _record(self,status):
        atomic_json(self.root/'owner.json',{**self._owner,'status':status,'updated':now()})

    def _require(self,task_id):
        if self._owner is None or self._owner['task_id']!=task_id:
            raise ValueError('CAD_TASK_OWNER_MISMATCH: only this service own task may amend or release')

    def claim(self,task_id,permissions,authorization_source):
        Journal(self.root).path(task_id)  # Shared ASCII identifier validation.
        if not isinstance(authorization_source,str) or not authorization_source.strip():
            raise ValueError('Original task or latest user authorization reference required')
        request={'task_id':task_id,'permissions':_permissions(permissions),
                 'authorization_source':authorization_source}
        with self._lock:
            if self._owner is not None:
                if self._owner['request_hash']!=digest(request):
                    raise ValueError('CAD_TASK_CONFLICT: release the previous task or explicitly amend authorization')
                return self.status()
            lease=workspace_lock(self.root)
            lease.__enter__()  # Fails before any owner record or CAD action changes.
            self._lease=lease
            self._owner={**request,'request_hash':digest(request),'revision':1,
                         'service_id':uuid.uuid4().hex,'pid':os.getpid(),'claimed_at':now(),
                         'authorization_history':[{'revision':1,**request}]}
            try:self._record('claimed')
            except BaseException:
                self._owner=None;self._lease=None;lease.__exit__(None,None,None)
                raise
            return self.status()

    def amend(self,task_id,permissions,authorization_source,expected_revision):
        with self._lock:
            self._require(task_id)
            if type(expected_revision) is not int or expected_revision!=self._owner['revision']:
                raise ValueError('CAD_AUTHORIZATION_STALE: re-read current revision before amendment')
            if not isinstance(authorization_source,str) or not authorization_source.strip():
                raise ValueError('Latest user authorization reference required')
            request={'task_id':task_id,'permissions':_permissions(permissions,self._owner['permissions']),
                     'authorization_source':authorization_source}
            previous=self._owner
            revision=expected_revision+1
            self._owner={**previous,**request,'request_hash':digest(request),'revision':revision,
                         'authorization_history':previous['authorization_history']+[{'revision':revision,**request}]}
            try:self._record('claimed')
            except BaseException:self._owner=previous;raise
            return self.status()

    def release(self,task_id):
        with self._lock:
            self._require(task_id)
            self._record('released')
            lease=self._lease
            self._lease=None;self._owner=None
            lease.__exit__(None,None,None)
            return {'ok':True,'released_task_id':task_id,'cad_changed':False,
                    'saved_or_closed_document':False}

    def status(self):
        with self._lock:
            if self._owner is not None:
                return {'ok':True,'busy':True,'owned_by_this_service':True,'owner':copy.deepcopy(self._owner),
                        'coordination_scope':'participating MCP servers only','cad_contacted':False}
            try:
                with workspace_lock(self.root):pass
            except RuntimeError:
                try:owner=json.loads((self.root/'owner.json').read_text(encoding='utf8'))
                except (OSError,ValueError):owner=None
                return {'ok':True,'busy':True,'owned_by_this_service':False,'owner':owner,
                        'owner_record_is_identity_proof':False,'cad_contacted':False}
            # A leftover record never means a dead process still owns CAD.
            return {'ok':True,'busy':False,'owned_by_this_service':False,'owner':None,'cad_contacted':False}

    def _authorize(self,permission):
        if self._owner is not None and permission and not self._owner['permissions'][permission]:
            raise ValueError('CAD_TASK_ACTION_NOT_AUTHORIZED: '+permission+
                             '; retain the task boundary or amend from an actual new user instruction')

    @contextmanager
    def guard(self,method):
        if method in PASSIVE:
            yield
            return
        if method not in ACTIONS:raise ValueError('CAD_ACTION_NOT_CLASSIFIED: '+method)
        with self._lock:
            self._authorize(ACTIONS[method])
            if self._lease is not None:
                yield
            else:
                # Existing callers keep per-call behavior, but cannot interrupt
                # a task with an explicit long-lived cooperative claim.
                with workspace_lock(self.root):yield

    @contextmanager
    def file_export(self):
        # Offline export does not compete for the shared CAD application.
        with self._lock:
            self._authorize('export')
            yield


def compare_states(recorded,current):
    """Compare supplied state facts; never claim a fresh live CAD observation."""
    allowed={'document_id','snapshot_sha256','entity_count','saved','dbmod'}
    for state in (recorded,current):
        if not isinstance(state,dict) or set(state)-allowed:
            raise ValueError('Use explicit document_id/entity_count/snapshot_sha256/saved/dbmod state fields')
        if not isinstance(state.get('document_id'),str) or not state['document_id'].strip():
            raise ValueError('Unambiguous document identity required')
        if type(state.get('entity_count')) is not int or state['entity_count']<0:
            raise ValueError('Actual nonnegative entity_count required')
        if 'saved' in state and type(state['saved']) is not bool:raise ValueError('saved must be boolean')
        if 'dbmod' in state and (type(state['dbmod']) is not int or state['dbmod']<0):raise ValueError('dbmod must be nonnegative integer')
        if 'snapshot_sha256' in state and not re.fullmatch('[a-f0-9]{64}',str(state['snapshot_sha256'])):
            raise ValueError('snapshot_sha256 must identify actual raw snapshot content')
    differences=[key for key in sorted(allowed) if key in recorded and key in current and recorded[key]!=current[key]]
    strong=all('snapshot_sha256' in state for state in (recorded,current))
    status='stale' if differences else 'matching_recorded_state' if strong else 'insufficient_evidence'
    return {'ok':True,'status':status,'changed_fields':differences,
            'needs_new_snapshot_and_review':status!='matching_recorded_state',
            'counter_equality_proves_freshness':False,'strong_snapshot_comparison':strong,
            'live_cad_verified':False,'live_recheck_required':True,'accepted_for_delivery':False}
