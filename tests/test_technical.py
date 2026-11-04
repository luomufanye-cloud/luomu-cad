import copy
import pytest
from luomu_cad.technical import TechnicalLibrary,validate_card,check_sequence,check_applicability,check_connections


@pytest.fixture
def water():return TechnicalLibrary().get('wet-area-waterproof-interfaces')


def test_construction_sequence_detects_omitted_or_late_node_reinforcement(water):
    good=[step['id'] for step in water['procedure']]
    assert check_sequence(water,good)['ok']
    assert not check_sequence(water,[s for s in good if s!='reinforce'])['ok']
    wrong=good.copy()
    a,b=wrong.index('reinforce'),wrong.index('coat')
    wrong[a],wrong[b]=wrong[b],wrong[a]
    assert not check_sequence(water,wrong)['ok']


def test_scoped_parameter_is_retained_but_not_transferred_to_other_product(water):
    assert water['parameters'][0]['value']=='9:24'
    context={'jurisdiction':'CN','product':'Yuhong G103','substrate':'verified mortar','project_design':'provided','manufacturer_revision_confirmed':True}
    answer=check_applicability(water,context)
    assert answer['ok'] and not answer['auto_apply'] and not answer['engineering_approval']
    assert not check_applicability(water,{**context,'product':'different waterproof system'})['ok']
    assert not check_applicability(water,{**context,'manufacturer_revision_confirmed':False})['ok']
    assert not check_applicability(water,{})['ok']


@pytest.mark.parametrize('change',['global','no_locator','no_scope','no_conditions','fake_mastery'])
def test_untraceable_or_unscoped_engineering_knowledge_rejected(water,change):
    if change=='global':water['parameters'][0]['adoption']='global_default'
    elif change=='no_locator':water['parameters'][0]['source_locator']=''
    elif change=='no_scope':water['applicability'].pop('system_or_product')
    elif change=='no_conditions':water['parameters'][0]['conditions']={}
    else:water['status']='project_checked'
    with pytest.raises(ValueError):validate_card(water)


def test_tns_downstream_training_detects_unintended_n_pe_connection():
    card=TechnicalLibrary().get('earthing-system-topology')
    context={'earthing_scheme':'TN-S','scope':'training_downstream_of_split'}
    edges=[['N','load.N'],['PE','load.PE']]
    assert check_connections(card,edges,context)['ok']
    bad=check_connections(card,edges+[['load.N','load.PE']],context)
    assert not bad['ok'] and bad['exercise_only'] and not bad['engineering_approval']
    assert not check_connections(card,[['N','load.N']],context)['ok']
    with pytest.raises(ValueError):check_connections(card,edges,{'earthing_scheme':'TN-C','scope':'training_downstream_of_split'})
    with pytest.raises(ValueError):check_connections(card,edges,{'earthing_scheme':'TN-S','scope':'source_bonding_point'})


@pytest.mark.parametrize('placeholder',[' MISSING ','unknown','UNCONFIRMED','pending','TBD','待核实','待确认','未确认','缺失','待补充','  ',[],{}])
def test_explicit_unresolved_project_inputs_are_not_treated_as_provided(water,placeholder):
    context={'jurisdiction':'CN','product':'Yuhong G103','substrate':'verified mortar','project_design':'provided','manufacturer_revision_confirmed':True}
    good=check_applicability(water,context)
    assert good['ok'] and not good['engineering_approval']
    unresolved=check_applicability(water,{**context,'substrate':placeholder})
    assert not unresolved['ok'] and 'substrate' in unresolved['missing_inputs']
    assert check_applicability(water,{**context,'substrate':0})['ok']  # Presence check does not validate engineering meaning.
