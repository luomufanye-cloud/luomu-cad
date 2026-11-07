"""Independent polygon and relation evaluation inspired by floorplan research.

No perception model is implemented here. Keep annotations outside model inputs.
"""
import hashlib
import math
from collections import Counter
from pathlib import Path

from ortools.sat.python import cp_model
from shapely.geometry import Polygon


def validate_scene(scene):
    if scene.get('schema') != 'cad-scene/1':
        raise ValueError('Expected cad-scene/1')
    source = scene.get('source_sha256', '')
    if len(source) != 64 or any(c not in '0123456789abcdef' for c in source):
        raise ValueError('Source SHA256 required')
    coordinate = scene.get('coordinates', {})
    if coordinate.get('units') not in {'pixel', 'mm'} or coordinate.get('y_axis') not in {'up', 'down'}:
        raise ValueError('Explicit units and Y axis required')
    objects = scene.get('objects')
    if not isinstance(objects, list):
        raise ValueError('objects must be a list')
    shapes = {}
    for item in objects:
        identity = item.get('id')
        if not isinstance(identity, str) or not identity or identity in shapes:
            raise ValueError('Distinct nonempty object IDs required')
        if not isinstance(item.get('label'), str) or not item['label'].strip():
            raise ValueError('Semantic label required')
        points = item.get('polygon', [])
        if len(points) < 3 or any(len(p) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in p) for p in points):
            raise ValueError('Finite 2D polygon vertices required')
        shape = Polygon(points)
        if not shape.is_valid or shape.area <= 0:
            raise ValueError('Polygon must have positive area and no self-intersection')
        shapes[identity] = shape
    seen = set()
    for relation in scene.get('relations', []):
        key = (relation.get('type'), relation.get('from'), relation.get('to'))
        if not isinstance(key[0], str) or not key[0] or key[1] not in shapes or key[2] not in shapes or key in seen:
            raise ValueError('Relations need distinct type/from/to records and existing endpoints')
        seen.add(key)
    return shapes


def evaluate(reference, prediction, iou_threshold=0.5):
    """Match geometrically first so classification errors remain observable."""
    if isinstance(iou_threshold, bool) or not 0 < iou_threshold <= 1:
        raise ValueError('IoU threshold must be in (0, 1]')
    truth_shapes = validate_scene(reference)
    predicted_shapes = validate_scene(prediction)
    for key in ('source_sha256', 'coordinates'):
        if reference[key] != prediction[key]:
            raise ValueError('Source image and coordinate frame must match exactly')
    provenance = reference.get('annotation', {})
    if not provenance.get('reviewer') or not provenance.get('method'):
        raise ValueError('Reference annotation reviewer and method required')
    truth = {o['id']: o for o in reference['objects']}
    predicted = {o['id']: o for o in prediction['objects']}
    model = cp_model.CpModel()
    pairs = []
    # Lexicographic cardinality then overlap. A duplicate cannot match twice.
    cardinality_weight = (min(len(truth), len(predicted)) + 1) * 1000000
    for rid, a in truth_shapes.items():
        for pid, b in predicted_shapes.items():
            overlap = a.intersection(b).area / a.union(b).area
            if overlap >= iou_threshold:
                variable = model.new_bool_var(f'm{len(pairs)}')
                pairs.append((rid, pid, overlap, variable))
    for rid in truth:
        model.add_at_most_one(v for r, p, score, v in pairs if r == rid)
    for pid in predicted:
        model.add_at_most_one(v for r, p, score, v in pairs if p == pid)
    model.maximize(sum((cardinality_weight + round(score * 1000000)) * v for r, p, score, v in pairs))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    solver.parameters.num_search_workers = 1
    status = solver.solve(model)
    if status != cp_model.OPTIMAL:
        raise ValueError('Matching did not reach an optimum within 30 seconds')
    matched = []
    for rid, pid, score, variable in pairs:
        if solver.value(variable):
            a, b = truth_shapes[rid], predicted_shapes[pid]
            matched.append({'reference': rid, 'prediction': pid, 'iou': score,
                            'correct_label': truth[rid]['label'] == predicted[pid]['label'],
                            'centroid_error': a.centroid.distance(b.centroid),
                            'boundary_hausdorff': a.boundary.hausdorff_distance(b.boundary)})
    mapping = {p['prediction']: p['reference'] for p in matched}
    matched_truth = set(mapping.values())
    expected_relations = {(r['type'], r['from'], r['to']) for r in reference.get('relations', [])}
    correct_relations = set()
    extra_relations = []
    for relation in prediction.get('relations', []):
        key = (relation['type'], mapping.get(relation['from']), mapping.get(relation['to']))
        if key in expected_relations:
            correct_relations.add(key)
        else:
            extra_relations.append(relation)
    correct = Counter(truth[p['reference']]['label'] for p in matched if p['correct_label'])
    expected_counts = Counter(o['label'] for o in truth.values())
    predicted_counts = Counter(o['label'] for o in predicted.values())
    classes = {}
    for label in sorted(expected_counts.keys() | predicted_counts.keys()):
        tp = correct[label]
        fp, fn = predicted_counts[label] - tp, expected_counts[label] - tp
        classes[label] = {'tp': tp, 'fp': fp, 'fn': fn,
                          'precision': tp / (tp + fp) if tp + fp else None,
                          'recall': tp / (tp + fn) if tp + fn else None}
    return {'schema': 'cad-scene-evaluation/1', 'source_sha256': reference['source_sha256'],
            'coordinates': reference['coordinates'], 'annotation': provenance,
            'iou_threshold': iou_threshold, 'classes': classes, 'matches': matched,
            'missed': sorted(truth.keys() - matched_truth),
            'extra': sorted(predicted.keys() - mapping.keys()),
            'misclassified': [p for p in matched if not p['correct_label']],
            'missing_relations': [list(r) for r in sorted(expected_relations - correct_relations)],
            'extra_relations': extra_relations, 'correct_relations': len(correct_relations),
            'engineering_approval': False}


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
