"""Read-only checks of a source-derived redraw contract; not visual acceptance."""
import argparse
from collections import Counter
import hashlib
import json
import math
import re
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

import ezdxf
from ezdxf.lldxf.tagwriter import TagCollector
from luomu_cad.annotations import text_style_findings


def fingerprint(entity):
    tags = TagCollector.dxftags(entity)
    payload = [(t.code, str(t.value)) for t in tags]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


def fingerprints(doc):
    result = {e.dxf.handle: fingerprint(e) for e in doc.modelspace()}
    for name in ('layers', 'styles', 'dimstyles', 'linetypes'):
        for e in getattr(doc, name):
            result[f'{name}:{e.dxf.name}'] = fingerprint(e)
    for block in doc.blocks:
        if not block.name.upper().startswith(('*MODEL_SPACE', '*PAPER_SPACE')):
            payload = [fingerprint(e) for e in block]
            payload.insert(0, fingerprint(block.block))
            result[f'block:{block.name}'] = hashlib.sha256(json.dumps(payload).encode()).hexdigest()
    for layout in doc.layouts:
        if layout.name != 'Model':
            for e in layout:
                result[f'layout:{layout.name}:{e.dxf.handle}'] = fingerprint(e)
    for name in ('$INSUNITS', '$LTSCALE', '$PSLTSCALE', '$MEASUREMENT'):
        result[f'header:{name}'] = hashlib.sha256(str(doc.header.get(name)).encode()).hexdigest()
    return result


def compare_patch(baseline, drawing, baseline_sha256, allowed_changes=(), allowed_additions=()):
    """Compare a saved latest baseline; every exception is an explicit key."""
    if Path(baseline).samefile(drawing):
        raise ValueError('BASELINE_IS_OUTPUT: preserve a separate pre-edit baseline')
    expected = hashlib.sha256(Path(baseline).read_bytes()).hexdigest()
    if baseline_sha256 != expected:
        raise ValueError('BASELINE_HASH_MISMATCH: do not use a stale or replaced baseline')
    before = fingerprints(ezdxf.readfile(baseline))
    after = fingerprints(ezdxf.readfile(drawing))
    changes, additions = set(allowed_changes), set(allowed_additions)
    if changes - before.keys():
        raise ValueError('Allowed changes must identify existing baseline objects/resources')
    if additions & before.keys() or additions - after.keys():
        raise ValueError('Allowed additions must identify actual new objects/resources')
    errors = []
    for key in sorted(before.keys() - changes):
        if after.get(key) != before[key]:
            errors.append(f'OUTSIDE_SCOPE_CHANGED:{key}')
    for key in sorted(after.keys() - before.keys() - additions):
        errors.append(f'UNEXPECTED_ADDITION:{key}')
    return {'checks_passed': not errors, 'errors': errors,
            'baseline_sha256': expected,
            'changed_keys': sorted(k for k in before if after.get(k) != before[k]),
            'added_keys': sorted(after.keys() - before.keys()),
            'scope': 'Saved entities, layout entities, tables, block definitions and selected headers; not reference fidelity'}


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
    if not isinstance(contract, dict) or not isinstance(contract.get('source'), str) or not contract['source'].strip():
        raise ValueError('A source-derived contract is required')
    if set(contract) - {'source', 'units', 'dimensions', 'texts', 'preserve',
                        'dimensions_absent_reason', 'texts_absent_reason', 'expected_handles', 'text_entities'}:
        raise ValueError('Unknown contract field')
    if not isinstance(contract.get('dimensions'), list) or not isinstance(contract.get('texts'), list):
        raise ValueError('Explicit dimension and text inventories are required')
    if not isinstance(contract.get('units'), int) or isinstance(contract['units'], bool):
        raise ValueError('Explicit drawing units are required')
    for name in ('dimensions', 'texts'):
        reason = contract.get(name + '_absent_reason')
        if not contract[name] and (not isinstance(reason, str) or not reason.strip()):
            raise ValueError(f'Empty {name} inventory requires an explicit reference-based absence reason')
    doc = ezdxf.readfile(path)
    model = doc.modelspace()
    by_handle = {e.dxf.handle: e for e in model}
    errors = []
    if doc.units != contract['units']:
        errors.append('UNITS_MISMATCH')
    if 'expected_handles' in contract:
        inventory = contract['expected_handles']
        if not isinstance(inventory, list) or any(not isinstance(v, str) or not v for v in inventory) or len(inventory) != len(set(inventory)):
            raise ValueError('expected_handles requires unique nonempty handles')
        errors.extend(f'UNEXPECTED_ENTITY:{v}' for v in sorted(by_handle.keys() - set(inventory)))
        errors.extend(f'EXPECTED_ENTITY_MISSING:{v}' for v in sorted(set(inventory) - by_handle.keys()))
    used = set()
    for spec in contract['dimensions']:
        required = {'handle', 'start', 'end', 'measurement', 'tolerance', 'dimlfac'}
        if not isinstance(spec, dict) or required - spec.keys() or spec.keys() - required - {'style', 'display_text'}:
            raise ValueError('Dimension requires handle, endpoints, measurement, tolerance and dimlfac')
        start, end = point(spec['start']), point(spec['end'])
        tolerance = number(spec['tolerance'], positive=True)
        expected = number(spec['measurement'], positive=True)
        scale = number(spec['dimlfac'])
        handle = spec['handle']
        if not isinstance(handle, str) or not handle or handle in used:
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
        style = spec.get('style', {})
        numeric_style = {'dimtxt', 'dimasz', 'dimdec', 'dimtad', 'dimexo', 'dimexe',
                         'dimdle', 'dimscale', 'dimgap', 'dimlwd', 'dimlwe',
                         'dimsd1', 'dimsd2', 'dimse1', 'dimse2', 'dimfxl', 'dimfxlon'}
        if not isinstance(style, dict) or style.keys() - numeric_style:
            raise ValueError('Unsupported dimension style field')
        for key, value in style.items():
            number(value)
            actual = entity.override().get(key)
            if not isinstance(actual, (int, float)) or not math.isclose(actual, value, rel_tol=0, abs_tol=1e-9):
                errors.append(f'DIMENSION_STYLE:{handle}:{key}')
        if not entity.dxf.get('geometry') or entity.dxf.geometry not in doc.blocks:
            errors.append(f'DIMENSION_DISPLAY_MISSING:{handle}')
        elif not list(doc.blocks[entity.dxf.geometry]):
            errors.append(f'DIMENSION_DISPLAY_EMPTY:{handle}')
        elif 'display_text' in spec:
            if not isinstance(spec['display_text'], str) or not spec['display_text']:
                raise ValueError('display_text requires the expected formatted dimension string')
            display = [e.dxf.text if e.dxftype() == 'TEXT' else e.plain_text()
                       for e in doc.blocks[entity.dxf.geometry] if e.dxftype() in ('TEXT', 'MTEXT')]
            if spec['display_text'] not in display:
                errors.append(f'DIMENSION_DISPLAY_TEXT:{handle}')
    texts = Counter(e.dxf.text if e.dxftype() == 'TEXT' else e.plain_text()
                    for e in model if e.dxftype() in ('TEXT', 'MTEXT'))
    if any(not isinstance(t, str) or not t for t in contract['texts']):
        raise ValueError('Text inventory entries must be nonempty strings')
    for text, count in Counter(contract['texts']).items():
        if texts[text] < count:
            errors.append(f'TEXT_MISSING:{text}')
    detailed_texts = contract.get('text_entities', [])
    if not isinstance(detailed_texts, list):
        raise ValueError('text_entities must be a list')
    for spec in detailed_texts:
        required = {'handle', 'text', 'at', 'height', 'rotation', 'tolerance'}
        if not isinstance(spec, dict) or set(spec) != required:
            raise ValueError('Text checks require handle/text/at/height/rotation/tolerance')
        position = point(spec['at'])
        height = number(spec['height'], positive=True)
        rotation = number(spec['rotation'])
        tolerance = number(spec['tolerance'], positive=True)
        if not isinstance(spec['handle'], str) or not isinstance(spec['text'], str):
            raise ValueError('Text handle and content must be strings')
        entity = by_handle.get(spec['handle'])
        if entity is None or entity.dxftype() != 'TEXT':
            errors.append(f'TEXT_ENTITY_UNSUPPORTED_OR_MISSING:{spec["handle"]}')
            continue
        if entity.dxf.text != spec['text']:
            errors.append(f'TEXT_CONTENT:{spec["handle"]}')
        actual_position = list(entity.dxf.insert)
        if not all(math.isfinite(v) for v in actual_position) or math.dist(position, actual_position) > tolerance:
            errors.append(f'TEXT_POSITION:{spec["handle"]}')
        if not math.isfinite(entity.dxf.height) or abs(entity.dxf.height - height) > tolerance:
            errors.append(f'TEXT_HEIGHT:{spec["handle"]}')
        difference = abs((entity.dxf.rotation - rotation + 180) % 360 - 180)
        if not math.isfinite(difference) or difference > 1e-6:
            errors.append(f'TEXT_ROTATION:{spec["handle"]}')
    preserve = contract.get('preserve', {})
    if not isinstance(preserve, dict):
        raise ValueError('preserve must be a fingerprint mapping')
    current = fingerprints(doc) if preserve else {}
    for key, value in preserve.items():
        if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
            raise ValueError('Invalid baseline fingerprint')
        if current.get(key) != value:
            errors.append(f'OUTSIDE_SCOPE_CHANGED:{key}')
    errors.extend('ANNOTATION:'+f['kind']+':'+f.get('handle','') for f in text_style_findings(doc))
    return {'checks_passed': not errors, 'errors': errors,
            'entity_types': dict(Counter(e.dxftype() for e in model)),
            'source': contract['source'], 'reference_visual_review': 'not_performed',
            'engineering_review': 'not_performed', 'complete_redraw_accepted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('drawing', type=Path)
    parser.add_argument('contract', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--baseline-sha256')
    parser.add_argument('--allow-change', action='append', default=[])
    parser.add_argument('--allow-addition', action='append', default=[])
    parser.add_argument('--reference-inventory',type=Path)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--review',type=Path)
    parser.add_argument('--structural-only',action='store_true',help='Diagnostic checks only; never full redraw acceptance')
    args = parser.parse_args()
    inputs = {args.drawing.resolve(), args.contract.resolve()}
    if args.baseline:
        inputs.add(args.baseline.resolve())
    inputs.update(p.resolve() for p in (args.reference_inventory,args.source,args.review) if p)
    if args.report.resolve() in inputs:
        raise ValueError('Report must not overwrite either input')
    contract=json.loads(args.contract.read_text(encoding='utf-8-sig'))
    if args.reference_inventory and args.source and not args.structural_only:
        from redraw_delivery import audit_reference, review_findings
        inventory=json.loads(args.reference_inventory.read_text(encoding='utf-8-sig'))
        try:
            result=audit_reference(args.drawing,inventory,contract.get('reference_map'),args.source)
            review=json.loads(args.review.read_text(encoding='utf-8-sig')) if args.review else None
            review_errors=review_findings(review,result,inventory,args.review.parent if args.review else args.drawing.parent)
        except (ValueError,KeyError,TypeError) as error:
            result={'checks_passed':False,'errors':['INVALID_REFERENCE_INPUT:'+str(error)],'complete_redraw_accepted':False}
            review_errors=['SOURCE_REVIEW_NOT_COMPLETED']
        result['errors'].extend(review_errors)
        result['checks_passed']=not result['errors']
        result['reference_visual_review']='recorded_for_current_files' if not review_errors else 'incomplete'
        result['complete_redraw_accepted']=result['checks_passed']
        result['engineering_review']='not_performed'
    else:
        result = audit(args.drawing,{k:v for k,v in contract.items() if k!='reference_map'})
        if not args.structural_only:
            result['errors'].append('DELIVERY_REQUIRES_SOURCE_INVENTORY_AND_SOURCE_FILE')
            result['checks_passed']=False
        result['mode']='structural_diagnostic' if args.structural_only else 'incomplete_delivery'
    if args.baseline:
        result['patch'] = compare_patch(args.baseline, args.drawing, args.baseline_sha256,
                                        args.allow_change, args.allow_addition)
        result['checks_passed'] &= result['patch']['checks_passed']
        result['complete_redraw_accepted'] &= result['patch']['checks_passed']
    elif args.baseline_sha256 or args.allow_change or args.allow_addition:
        raise ValueError('Patch options require --baseline')
    from luomu_cad import __version__
    import hashlib
    result['verifier_version']=__version__
    result['checker_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
