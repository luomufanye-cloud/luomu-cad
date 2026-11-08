"""Functional contracts for Luomu CAD's newly authored component implementation."""
import json
import math
from pathlib import Path
import shutil
import subprocess

import pytest
from shapely.geometry import Polygon
from luomu_cad.component_library import catalogue, furniture_geometry
from luomu_cad.components import build

ROOT=Path(__file__).resolve().parents[1]


def test_all_catalogue_entries_have_native_finite_geometry_and_chinese_names():
    rows=catalogue()['furniture']
    assert len(rows)==len({r['key'] for r in rows})==317
    total=0
    for row in rows:
        assert any('\u4e00'<=c<='\u9fff' for c in row['name'])
        geometry=furniture_geometry(row)
        assert geometry['entities']
        for entity in geometry['entities']:
            def visit(value):
                if isinstance(value,(list,tuple)):
                    for v in value:visit(v)
                elif isinstance(value,(float,int)) and not isinstance(value,bool):assert math.isfinite(value)
            for value in entity.values():visit(value)
        total+=len(geometry['entities'])
    assert total>5000


def test_component_generation_does_not_require_node(monkeypatch,tmp_path):
    monkeypatch.setenv('PATH','')
    report=build({'units':'mm','nodes':[],'walls':[],'openings':[],
        'furniture':[{'id':'bed','key':'bed18'}]},tmp_path)
    assert report['geometry_passed']


@pytest.mark.parametrize('key',['lSofa','uSofa'])
def test_corner_sofa_has_a_concave_footprint(key):
    item=next(r for r in catalogue()['furniture'] if r['key']==key)
    entities=furniture_geometry(item)['entities']
    count=6 if key=='lSofa' else 8
    boundary=Polygon([r['start'] for r in entities[:count]])
    assert boundary.is_valid and boundary.area < item['w']*item['d']*.9


def test_free_outline_uses_user_vertices_without_inventing_a_default_box():
    result=furniture_geometry({'key':'freeExtrude','opt':{'shape':'extrude','outline':'0,0|500,0|0,300'}})
    assert len(result['entities'])==3
    assert {tuple(r['start']) for r in result['entities']}=={(0,0),(500,0),(0,300)}


def test_curved_seat_presets_and_custom_mirroring():
    variants=['bendSofa_serpentine','bendSofa_roundL','bendSofa_crescent']
    signatures={json.dumps(furniture_geometry({'key':key})['entities'],sort_keys=True) for key in variants}
    assert len(signatures)==3
    original=furniture_geometry({'key':'bendSofa','opt':{'path':'0,0,400|500,300,500|1000,0,400'}})
    mirrored=furniture_geometry({'key':'bendSofa','opt':{'path':'0,0,400|500,300,500|1000,0,400','flip':True}})
    assert original['entities']!=mirrored['entities']
    assert any(r['type']=='bezier' for r in original['entities'])


def test_cabinet_column_configuration_changes_native_geometry():
    door=furniture_geometry({'key':'cabWardrobe','cab':{'cols':['door','door'],'ws':[400,800]}})
    drawers=furniture_geometry({'key':'cabWardrobe','cab':{'cols':['drawer','hang','glass'],'ws':[400,400,400]}})
    assert door['entities']!=drawers['entities']
    with pytest.raises(ValueError):
        furniture_geometry({'key':'cabWardrobe','cab':{'cols':['door'],'ws':[1,2]}})


def test_kitchen_features_have_separate_controls_and_fit_checks():
    bare=furniture_geometry({'key':'counter','kit':{'sink':False,'hob':False,'wall':False}})
    fitted=furniture_geometry({'key':'counter','kit':{
        'sink':{'leg':0,'at':650,'w':650,'bowls':2},
        'hob':{'leg':0,'at':1800,'w':600,'burners':4}}})
    assert len(fitted['entities'])>len(bare['entities'])+20
    assert any(e['type']=='ellipse_arc' for e in fitted['entities'])
    corner=furniture_geometry({'key':'lCounter','kit':{'sink':{'leg':1,'at':700,'w':600}}})
    assert corner['entities']
    with pytest.raises(ValueError,match='does not fit'):
        furniture_geometry({'key':'counter','kit':{'sink':{'at':0,'w':600}}})


def test_node_compatibility_catalogue_matches_python():
    node=shutil.which('node')
    if not node:pytest.skip('Node compatibility CLI is optional')
    result=subprocess.check_output([node,str(ROOT/'scripts/house_components.mjs'),'catalog'],encoding='utf8')
    assert json.loads(result)==catalogue()
