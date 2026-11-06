"""Read-only DXF evidence inventory. No semantic guessing or drawing repair."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import ezdxf
from ezdxf import bbox, transform, units
from ezdxf.math import Matrix44


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Expected a finite number')
    return float(value)


def inventory(path, box_mm=None, unit_mm=None, unit_reason='', max_entities=20000, max_depth=16):
    """Inventory modelspace, retaining paths through nested INSERTs in WCS millimeters.

    Bounding boxes select candidates, not exact intersections or engineering semantics.
    Unsupported content remains visible in issues instead of silently disappearing.
    """
    path = Path(path)
    if path.suffix.lower() != '.dxf' or path.stat().st_size > 50_000_000:
        raise ValueError('Expected a DXF of at most 50 MB')
    if not isinstance(max_entities, int) or not 1 <= max_entities <= 100000:
        raise ValueError('max_entities must be 1..100000')
    if not isinstance(max_depth, int) or not 1 <= max_depth <= 32:
        raise ValueError('max_depth must be 1..32')
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    doc = ezdxf.readfile(path)
    declared = int(doc.units)
    if unit_mm is not None:
        factor = finite(unit_mm)
        if factor <= 0 or not isinstance(unit_reason, str) or not unit_reason.strip():
            raise ValueError('Unit override requires a positive factor and an evidence reason')
        basis = 'explicit_override'
    else:
        if declared == 0:
            raise ValueError('Unitless DXF: provide unit_mm and unit_reason from scale evidence')
        factor = units.conversion_factor(declared, units.MM)
        basis = 'INSUNITS declaration; cross-check against reference dimensions'
    box = None if box_mm is None else [finite(v) for v in box_mm]
    if box is not None and (len(box) != 4 or box[0] >= box[2] or box[1] >= box[3]):
        raise ValueError('box_mm requires xmin,ymin,xmax,ymax in WCS millimeters')
    rows, blocks, issues = [], [], []
    count = 0
    to_mm = Matrix44.scale(factor)
    supported = {'LINE', 'POINT', 'LWPOLYLINE', 'POLYLINE', 'CIRCLE', 'ARC',
                 'ELLIPSE', 'SPLINE', 'SOLID', 'TRACE', '3DFACE', 'TEXT', 'MTEXT', 'ATTRIB', 'ATTDEF'}

    def issue(identifier, message):
        issues.append({'id': identifier, 'message': message})

    def walk(entity, parent_matrix, inherited_layer, ancestry, stack, source_handle=None):
        nonlocal count
        count += 1
        if count > max_entities:
            raise ValueError('Entity budget exceeded; no complete inventory produced')
        handle = source_handle or entity.dxf.handle or 'unhandled'
        identifier = '/'.join([*ancestry, handle])
        layer = entity.dxf.get('layer', '0')
        effective = inherited_layer if layer == '0' else layer
        kind = entity.dxftype()
        if kind == 'INSERT':
            name = entity.dxf.name
            if name.casefold() in stack or len(stack) >= max_depth:
                issue(identifier, 'Cyclic or over-depth block reference')
                return
            definition = entity.block()
            if definition is None or definition.block.is_xref:
                issue(identifier, 'Missing or external block; not loaded')
                return
            if entity.dxf.get('row_count', 1) * entity.dxf.get('column_count', 1) > max_entities:
                raise ValueError('MINSERT budget exceeded')
            instances = entity.multi_insert() if entity.mcount > 1 else [entity]
            for index, instance in enumerate(instances):
                instance_id = identifier + (f'@{index}' if entity.mcount > 1 else '')
                matrix = instance.matrix44() @ parent_matrix
                first_row = len(rows)
                record = {'id': instance_id, 'name': name, 'source_handle': handle,
                          'layer': effective, 'block_units': int(definition.units),
                          'matrix_to_wcs_mm': list(matrix @ to_mm),
                          'semantic_class': 'unclassified', 'selected': False}
                blocks.append(record)
                for child in definition:
                    walk(child, matrix, effective, [instance_id], (*stack, name.casefold()))
                # Attached attributes already use the INSERT parent's coordinates.
                for attribute_index, attribute in enumerate(instance.attribs):
                    walk(attribute, parent_matrix, effective, [instance_id, 'attribute'], stack,
                         entity.attribs[attribute_index].dxf.handle)
                record['selected'] = any(r['selected'] is not False for r in rows[first_row:])
                if len(rows) == first_row:
                    issue(instance_id, 'No inventory leaves in block; inspect empty/unsupported definition')
            return
        row = {'id': identifier, 'source_handle': handle, 'type': kind,
               'layer': effective, 'declared_layer': layer, 'selected': None,
               'bounds_mm': None, 'semantic_class': 'unclassified'}
        rows.append(row)
        if kind in {'TEXT', 'MTEXT', 'ATTRIB', 'ATTDEF'}:
            row['text'] = entity.text if kind == 'MTEXT' else entity.dxf.text
            row['bounds_quality'] = 'approximate_text_metrics'
        else:
            row['bounds_quality'] = 'geometry_candidate_not_exact_intersection'
        if kind not in supported:
            issue(identifier, f'{kind} requires a separate semantic/geometry reader')
            return
        try:
            log, copies = transform.copies([entity], parent_matrix @ to_mm)
            if log or not copies:
                issue(identifier, 'Transformation incomplete: ' + '; '.join(log.messages()))
                return
            extent = bbox.extents(copies)
            if not extent.has_data:
                issue(identifier, 'No supported bounds')
                return
            low, high = extent.extmin, extent.extmax
            bounds = [finite(low.x), finite(low.y), finite(high.x), finite(high.y)]
            row['bounds_mm'] = bounds
            row['transformed_types'] = [e.dxftype() for e in copies]
            row['selected'] = box is None or not (bounds[2] < box[0] or bounds[0] > box[2]
                                                   or bounds[3] < box[1] or bounds[1] > box[3])
        except Exception as exc:
            issue(identifier, 'Geometry read failed: ' + str(exc))

    for entity in doc.modelspace():
        walk(entity, Matrix44(), '0', [], ())
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    if after != before:
        raise ValueError('Source changed during inventory; discard mixed evidence')
    selected = [r for r in rows if r['selected'] is True]
    if not selected:
        issue('modelspace', 'No supported selected entities; empty selection is not successful coverage')
    return {'ok': not issues, 'source_sha256': before, 'source_unchanged': True,
            'coordinate_system': 'WCS X-right Y-up; millimeters; no origin relocation',
            'unit': {'declared': declared, 'mm_per_unit': factor, 'basis': basis, 'reason': unit_reason},
            'box_mm': box, 'blocks': blocks, 'entities': rows, 'issues': issues,
            'selected_count': len(selected), 'engineering_classification': False,
            'selection_is_bbox_candidate': True, 'cad_contacted': False}


def check_dimension_chains(features, chains):
    """Check explicitly identified axis/face/opening coordinates, never nearest-line guesses."""
    if not features or not chains:
        raise ValueError('Nonempty features and dimension chains are required')
    if len(features) > 10000 or len(chains) > 256:
        raise ValueError('Feature/chain budget exceeded')
    indexed = {}
    for feature in features:
        key = feature['id']
        if not isinstance(key, str) or not key or key in indexed:
            raise ValueError('Feature IDs must be unique nonempty strings')
        if feature['kind'] not in {'axis', 'face', 'opening'} or feature['axis'] not in {'x', 'y'}:
            raise ValueError('Feature requires kind axis/face/opening and coordinate axis x/y')
        indexed[key] = {**feature, 'coordinate_mm': finite(feature['coordinate_mm'])}
    findings, measurements, constraints, seen = [], [], {}, set()
    for chain in chains:
        key = chain['id']
        if not isinstance(key, str) or not key or key in seen:
            raise ValueError('Chain IDs must be unique nonempty strings')
        seen.add(key)
        ids, segments = chain['features'], [finite(v) for v in chain['segments_mm']]
        if len(ids) > 128:
            raise ValueError('Split long chains into at most 128 declared features')
        tolerance = finite(chain['tolerance_mm'])
        if len(ids) != len(segments) + 1 or len(ids) < 2 or len(set(ids)) != len(ids):
            raise ValueError('Chain needs distinct features and one value per adjacent segment')
        if tolerance < 0 or any(v <= 0 for v in segments):
            raise ValueError('Tolerance must be nonnegative and lengths positive')
        kind, axis = chain['kind'], chain['axis']
        if kind not in {'axis', 'face', 'opening'} or axis not in {'x', 'y'}:
            raise ValueError('Invalid chain kind or coordinate axis')
        if any(i not in indexed for i in ids):
            findings.append({'chain': key, 'error': 'missing_feature'})
            continue
        nodes = [indexed[i] for i in ids]
        if any(n['kind'] != kind or n['axis'] != axis for n in nodes):
            findings.append({'chain': key, 'error': 'semantic_reference_mismatch'})
            continue
        differences = [b['coordinate_mm']-a['coordinate_mm'] for a, b in zip(nodes, nodes[1:])]
        if not (all(v > 0 for v in differences) or all(v < 0 for v in differences)):
            findings.append({'chain': key, 'error': 'non_monotonic_chain'})
        for i, (actual, expected) in enumerate(zip(differences, segments)):
            error = abs(abs(actual)-expected)
            measurements.append({'chain': key, 'segment': i, 'actual_mm': abs(actual),
                                 'expected_mm': expected, 'error_mm': error})
            if error > tolerance:
                findings.append({'chain': key, 'segment': i, 'error': 'length_mismatch'})
        # Every endpoint pair is a constraint, including cumulative totals.
        # Compare each independent declaration; never average conflicting values.
        for start in range(len(ids)-1):
            for end in range(start+1, len(ids)):
                pair = tuple(sorted((ids[start], ids[end])))
                value = sum(segments[start:end])
                for old in constraints.get(pair, []):
                    if abs(value-old['value']) > tolerance+old['tolerance']:
                        findings.append({'chain': key, 'other_chain': old['chain'],
                                         'features': list(pair), 'error': 'source_dimension_conflict'})
                constraints.setdefault(pair, []).append({'chain': key, 'value': value, 'tolerance': tolerance})
    return {'ok': not findings, 'findings': findings, 'measurements': measurements,
            'scope': 'declared feature coordinates only; pair with saved-DXF readback and visual comparison',
            'geometry_modified': False}
