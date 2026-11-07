import copy
from types import SimpleNamespace

import pytest

from luomu_cad.cad import CAD
from luomu_cad.performance import assess_interaction


def evidence():
    return {'document_path': '/exercise/current.dwg', 'document_token': 'current-token',
            'change': 'one reversible setting', 'operation': 'pan',
            'before': 'slow', 'after': 'tested same operation', 'command_seconds': [.01, .02]}


def test_fast_native_commands_do_not_establish_interaction_recovery():
    result = assess_interaction(evidence())
    assert not result['interaction_recovery_accepted'] and not result['root_cause_verified']


@pytest.mark.parametrize('fault', ['still_slow', 'other_document', 'old_token', 'other_operation', 'native_timing', 'no_details'])
def test_false_or_unbound_interaction_observation_is_not_accepted(fault):
    record = evidence()
    observation = {'method': 'user_feedback', 'resolved': True,
                   'document_path': record['document_path'], 'document_token': record['document_token'],
                   'operation': 'pan', 'details': 'Same pan operation is smooth after the change'}
    if fault == 'still_slow': observation['resolved'] = False
    if fault == 'other_document': observation['document_path'] = '/exercise/old.dwg'
    if fault == 'old_token': observation['document_token'] = 'stale-token'
    if fault == 'other_operation': observation['operation'] = 'regen'
    if fault == 'native_timing': observation['method'] = 'native_command'
    if fault == 'no_details': observation['details'] = ''
    record['interaction_observation'] = observation
    assert not assess_interaction(record)['interaction_recovery_accepted']


def test_same_document_user_feedback_can_confirm_only_observed_operation():
    record = evidence()
    record['interaction_observation'] = {'method': 'user_feedback', 'resolved': True,
        **{k: record[k] for k in ('document_path', 'document_token', 'operation')},
        'details': 'Same pan operation is now smooth'}
    result = assess_interaction(record)
    assert result['interaction_recovery_accepted'] and not result['root_cause_verified']


def test_invalid_timings_are_rejected():
    record = evidence(); record['command_seconds'] = [float('nan')]
    with pytest.raises(ValueError): assess_interaction(record)


def test_snapshot_is_read_only_and_reports_unavailable_variables(tmp_path, monkeypatch):
    calls = []
    def get(name):
        calls.append(name)
        if name == 'GFXDX12': raise ValueError('not supported by this release')
        return '' if name == 'CMDNAMES' else 0
    doc = SimpleNamespace(FullName='/exercise/current.dwg', Saved=False,
                          ModelSpace=SimpleNamespace(Count=12), GetVariable=get)
    cad = CAD(tmp_path)
    cad.bound_token = 'current-token'
    monkeypatch.setattr(cad, 'state', lambda token: doc if token == 'current-token' else None)
    before = copy.copy(doc.__dict__)
    result = cad.performance_snapshot('current-token')
    assert result['modelspace_objects'] == 12 and not result['saved']
    assert not result['settings_changed'] and not result['interaction_recovery_accepted']
    assert 'GFXDX12' in result['unavailable'] and doc.__dict__ == before
    assert len(calls) == len(set(calls))  # No full scan or repeated setting probes.
