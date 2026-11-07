"""Keep command timing and observed interaction recovery as separate results."""
import math


def assess_interaction(evidence):
    """Assess a caller-supplied before/after observation, never infer UI latency.

    Native command timings may accompany this record but cannot establish the
    user's mouse/keyboard experience. No settings or documents are changed.
    """
    if not isinstance(evidence, dict):
        raise ValueError('Performance evidence must be an object')
    required = ('document_path', 'document_token', 'change', 'operation', 'before', 'after')
    if any(not isinstance(evidence.get(k), str) or not evidence[k].strip() for k in required):
        raise ValueError('Document identity and comparable operation/change/before/after required')
    samples = evidence.get('command_seconds', [])
    if not isinstance(samples, list) or any(isinstance(x, bool) or not isinstance(x, (int, float))
            or not math.isfinite(x) or x < 0 for x in samples):
        raise ValueError('Command timings must be finite nonnegative samples')
    observation = evidence.get('interaction_observation', {})
    accepted = (isinstance(observation, dict)
                and observation.get('method') in ('user_feedback', 'end_to_end_measurement')
                and observation.get('document_path') == evidence['document_path']
                and observation.get('document_token') == evidence['document_token']
                and observation.get('operation') == evidence['operation']
                and isinstance(observation.get('details'), str) and bool(observation['details'].strip())
                and observation.get('resolved') is True)
    return {'interaction_recovery_accepted': bool(accepted),
            'command_seconds': samples, 'root_cause_verified': False,
            'status': 'observed_resolved' if accepted else 'unresolved_or_unmeasured',
            'scope': 'Recorded observation for this document and operation only; not a global CAD performance guarantee'}
