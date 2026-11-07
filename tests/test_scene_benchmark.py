import copy

import pytest

from luomu_cad.scene_benchmark import evaluate


def fixture_scene():
    return {'schema': 'cad-scene/1', 'source_sha256': 'a' * 64,
            'coordinates': {'units': 'pixel', 'y_axis': 'down', 'width': 100, 'height': 100},
            'annotation': {'reviewer': 'Original synthetic test fixture', 'method': 'Explicit coordinates'},
            'objects': [{'id': 'wall', 'label': 'wall', 'polygon': [[0, 0], [100, 0], [100, 10], [0, 10]]},
                        {'id': 'door', 'label': 'door', 'polygon': [[10, 0], [20, 0], [20, 10], [10, 10]]}],
            'relations': [{'type': 'hosted_by', 'from': 'door', 'to': 'wall'}]}


def test_identity_and_input_immutability():
    scene = fixture_scene()
    before = copy.deepcopy(scene)
    result = evaluate(scene, scene)
    assert result['classes']['door'] == {'tp': 1, 'fp': 0, 'fn': 0, 'precision': 1, 'recall': 1}
    assert result['correct_relations'] == 1
    assert all(m['boundary_hausdorff'] == 0 for m in result['matches'])
    assert scene == before


def test_wrong_label_is_not_hidden_by_geometry():
    truth = fixture_scene()
    prediction = copy.deepcopy(truth)
    prediction['objects'][1]['label'] = 'window'
    result = evaluate(truth, prediction)
    assert len(result['misclassified']) == 1
    assert result['classes']['door']['fn'] == 1
    assert result['classes']['window']['fp'] == 1


def test_missing_door_and_relation():
    truth = fixture_scene()
    prediction = copy.deepcopy(truth)
    prediction['objects'].pop()
    prediction['relations'] = []
    result = evaluate(truth, prediction)
    assert result['missed'] == ['door']
    assert result['missing_relations'] == [['hosted_by', 'door', 'wall']]


def test_duplicate_and_wrong_host():
    truth = fixture_scene()
    prediction = copy.deepcopy(truth)
    duplicate = {**prediction['objects'][1], 'id': 'extra_door'}
    prediction['objects'].append(duplicate)
    prediction['relations'] = [{'type': 'hosted_by', 'from': 'wall', 'to': 'door'}]
    result = evaluate(truth, prediction)
    assert len(result['extra']) == 1
    assert result['classes']['door']['fp'] == 1
    assert len(result['extra_relations']) == 1


def test_coordinate_shift_measured():
    truth = fixture_scene()
    prediction = copy.deepcopy(truth)
    prediction['objects'][1]['polygon'] = [[x + 1, y] for x, y in truth['objects'][1]['polygon']]
    result = evaluate(truth, prediction)
    door = next(m for m in result['matches'] if m['reference'] == 'door')
    assert door['centroid_error'] == pytest.approx(1)
    assert door['boundary_hausdorff'] == pytest.approx(1)


@pytest.mark.parametrize('change', ['source', 'coordinates', 'duplicate', 'self_cross', 'unknown_relation', 'nan', 'annotation'])
def test_invalid_input_fails(change):
    truth = fixture_scene()
    prediction = copy.deepcopy(truth)
    if change == 'source': prediction['source_sha256'] = 'b' * 64
    if change == 'coordinates': prediction['coordinates']['y_axis'] = 'up'
    if change == 'duplicate': prediction['objects'][1]['id'] = 'wall'
    if change == 'self_cross': prediction['objects'][1]['polygon'] = [[0, 0], [10, 10], [0, 10], [10, 0]]
    if change == 'unknown_relation': prediction['relations'][0]['from'] = 'absent'
    if change == 'nan': prediction['objects'][0]['polygon'][0][0] = float('nan')
    if change == 'annotation': truth['annotation'] = {}
    with pytest.raises(ValueError): evaluate(truth, prediction)


def test_empty_prediction_reports_all_missed():
    truth = fixture_scene()
    prediction = {**truth, 'objects': [], 'relations': []}
    result = evaluate(truth, prediction)
    assert len(result['missed']) == 2
    assert result['classes']['wall']['recall'] == 0
