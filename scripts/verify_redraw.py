"""Read-only checks of a source-derived redraw contract; not visual acceptance."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import ezdxf
from ezdxf.lldxf.tagwriter import TagCollector


def fingerprint(entity):
    tags = TagCollector.dxftags(entity)
    payload = [(t.code, str(t.value)) for t in tags]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


def fingerprints(doc):
    result = {e.dxf.handle: fingerprint(e) for e in doc.modelspace()}
    for name in ('layers', 'styles', 'dimstyles'):
        for e in getattr(doc, name):
            result[f'{name}:{e.dxf.name}'] = fingerprint(e)
    for block in doc.blocks:
        if not block.name.startswith('*'):
            payload = [fingerprint(e) for e in block]
            payload.insert(0, fingerprint(block.block))
            result[f'block:{block.name}'] = hashlib.sha256(json.dumps(payload).encode()).hexdigest()
    return result


def number(value, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Expected a finite number')
    if positive and value <= 0:
        raise ValueError('Expected a positive number')
    return value


def point(value):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError('Expected a 3D point')
    return [number(v) for v in value]


def audit(path, contract):
    if not isinstance(contract, dict) or not str(contract.get('source', '')).strip():
        raise ValueError('A source-derived contract is required')
    if set(contract) - {'source', 'units', 'dimensions', 'texts', 'preserve'}:
        raise ValueError('Unknown contract field')
    if not isinstance(contract.get('dimensions'), list) or not isinstance(contract.get('texts'), list):
        raise ValueError('Explicit dimension and text inventories are required')
    if not isinstance(contract.get('units'), int) or isinstance(contract['units'], bool):
        raise ValueError('Explicit drawing units are required')
    doc = ezdxf.readfile(path)
    model = doc.modelspace()
    by_handle = {e.dxf.handle: e for e in model}
    errors = []
    if doc.units != contract['units']:
        errors.append('UNITS_MISMATCH')
    used = set()
    for spec in contract['dimensions']:
        required = {'handle', 'start', 'end', 'measurement', 'tolerance', 'dimlfac'}
        if not isinstance(spec, dict) or set(spec) != required:
            raise ValueError('Dimension requires handle, endpoints, measurement, tolerance and dimlfac')
        start, end = point(spec['start']), point(spec['end'])
        tolerance = number(spec['tolerance'], positive=True)
        expected = number(spec['measurement'], positive=True)
        scale = number(spec['dimlfac'])
        handle = spec['handle']
        if not isinstance(handle, str) or handle in used:
            raise ValueError('Each expected dimension needs a unique handle')
        used.add(handle)
        entity = by_handle.get(handle)
        if entity is None or entity.dxftype() != 'DIMENSION':
            errors.append(f'NATIVE_DIMENSION_MISSING:{handle}')
            continue
        if entity.dxf.dimtype & 7 not in (0, 1):
            errors.append(f'DIMENSION_TYPE_UNSUPPORTED:{handle}')
            continue
        actual_start = tuple(entity.dxf.defpoint2)
        actual_end = tuple(entity.dxf.defpoint3)
        endpoints_ok = (
            math.dist(start, actual_start) <= tolerance and math.dist(end, actual_end) <= tolerance
        ) or (
            math.dist(end, actual_start) <= tolerance and math.dist(start, actual_end) <= tolerance
        )
        if not endpoints_ok:
            errors.append(f'DIMENSION_ENDPOINTS:{handle}')
        if abs(float(entity.get_measurement()) - expected) > tolerance:
            errors.append(f'DIMENSION_MEASUREMENT:{handle}')
        if entity.dxf.get('text', '') not in ('', '<>'):
            errors.append(f'DIMENSION_TEXT_OVERRIDE:{handle}')
        actual_scale = entity.override().get('dimlfac', 1)
        if not math.isclose(float(actual_scale), scale, rel_tol=0, abs_tol=1e-9):
            errors.append(f'DIMENSION_SCALE:{handle}')
        if not entity.dxf.get('geometry') or entity.dxf.geometry not in doc.blocks:
            errors.append(f'DIMENSION_DISPLAY_MISSING:{handle}')
    texts = Counter(e.dxf.text if e.dxftype() == 'TEXT' else e.plain_text()
                    for e in model if e.dxftype() in ('TEXT', 'MTEXT'))
    if any(not isinstance(t, str) or not t for t in contract['texts']):
        raise ValueError('Text inventory entries must be nonempty strings')
    for text, count in Counter(contract['texts']).items():
        if texts[text] < count:
            errors.append(f'TEXT_MISSING:{text}')
    preserve = contract.get('preserve', {})
    if not isinstance(preserve, dict):
        raise ValueError('preserve must be a fingerprint mapping')
    current = fingerprints(doc) if preserve else {}
    for key, value in preserve.items():
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError('Invalid baseline fingerprint')
        if current.get(key) != value:
            errors.append(f'OUTSIDE_SCOPE_CHANGED:{key}')
    return {'checks_passed': not errors, 'errors': errors,
            'entity_types': dict(Counter(e.dxftype() for e in model)),
            'source': contract['source'], 'reference_visual_review': 'not_performed',
            'engineering_review': 'not_performed', 'complete_redraw_accepted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('drawing', type=Path)
    parser.add_argument('contract', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.resolve() in {args.drawing.resolve(), args.contract.resolve()}:
        raise ValueError('Report must not overwrite either input')
    result = audit(args.drawing, json.loads(args.contract.read_text(encoding='utf-8-sig')))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
