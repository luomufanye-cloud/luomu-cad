"""Original wall/opening exercise using documented IfcOpenShell public APIs.

Geometry arguments are metres. IFC project storage units are explicitly millimetres.
"""
import numpy as np
import ifcopenshell.api

api = ifcopenshell.api.run
result = api('project.create_file', version='IFC4')
project = api('root.create_entity', result, ifc_class='IfcProject', name='Opening exercise')
api('unit.assign_unit', result, units=[
    api('unit.add_si_unit', result, unit_type='LENGTHUNIT', prefix='MILLI'),
    api('unit.add_si_unit', result, unit_type='AREAUNIT'),
    api('unit.add_si_unit', result, unit_type='VOLUMEUNIT')])
site = api('root.create_entity', result, ifc_class='IfcSite')
building = api('root.create_entity', result, ifc_class='IfcBuilding')
storey = api('root.create_entity', result, ifc_class='IfcBuildingStorey')
for parent, child in [(project, site), (site, building), (building, storey)]:
    api('aggregate.assign_object', result, products=[child], relating_object=parent)
context = api('context.add_context', result, context_type='Model')
body = api('context.add_context', result, context_type='Model', context_identifier='Body',
           target_view='MODEL_VIEW', parent=context)


def body_element(kind, name, length, thickness, height, location):
    element = api('root.create_entity', result, ifc_class=kind, name=name)
    representation = api('geometry.add_wall_representation', result, context=body,
                         length=length, height=height, thickness=thickness)
    api('geometry.assign_representation', result, product=element, representation=representation)
    matrix = np.identity(4)
    matrix[:3, 3] = location
    api('geometry.edit_object_placement', result, product=element, matrix=matrix)
    return element


wall = body_element('IfcWall', 'host_wall', 5, .2, 3, [0, 0, 0])
opening = body_element('IfcOpeningElement', 'door_opening', .9, .4, 2.1, [1, -.1, 0])
door = body_element('IfcDoor', 'door_leaf_envelope', .9, .04, 2.1, [1, .08, 0])
api('feature.add_feature', result, feature=opening, element=wall)
api('feature.add_filling', result, opening=opening, element=door)
api('spatial.assign_container', result, products=[wall, door], relating_structure=storey)
