"""Read-only ActiveX inspection, called exclusively inside the CAD MCP worker."""


def capture(document, retry, max_entities=20000):
    if type(max_entities) is not int or not 1 <= max_entities <= 100000:
        raise ValueError('max_entities must be 1..100000')
    issues = []

    def read(obj, name, identifier):
        try:
            value = retry(lambda: getattr(obj, name), timeout=2)
            if isinstance(value, tuple):
                value = list(value)
            return value
        except Exception as exc:
            issues.append({'id': identifier, 'property': name, 'error': str(exc)})
            return None

    layers = []
    table = retry(lambda: document.Layers)
    for index in range(retry(lambda: int(table.Count))):
        layer = retry(lambda: table.Item(index))
        identifier = str(read(layer, 'Name', 'layer'))
        layers.append({name: read(layer, name, identifier) for name in ('Name', 'Lineweight', 'Linetype', 'Color', 'LayerOn', 'Freeze', 'Plottable')})
    count = 0
    blocks = {}

    def entities(collection, depth=0):
        nonlocal count
        if depth > 16:
            raise ValueError('Presentation snapshot block depth exceeded')
        rows = []
        for index in range(retry(lambda: int(collection.Count))):
            count += 1
            if count > max_entities:
                raise ValueError('Presentation snapshot entity budget exceeded')
            entity = retry(lambda: collection.Item(index))
            handle = str(read(entity, 'Handle', 'entity'))
            row = {name: read(entity, name, handle) for name in ('Handle', 'ObjectName', 'Layer', 'Lineweight', 'Linetype', 'LinetypeScale', 'Color')}
            if row['ObjectName'] == 'AcDbPolyline':
                coordinates = read(entity, 'Coordinates', handle)
                row['ConstantWidth'] = read(entity, 'ConstantWidth', handle)
                row['VertexWidths'] = []
                if coordinates is not None:
                    for vertex in range(len(coordinates) // 2):
                        try:
                            row['VertexWidths'].append(list(retry(lambda: entity.GetWidth(vertex), timeout=2)))
                        except Exception as exc:
                            issues.append({'id': handle, 'property': 'GetWidth', 'error': str(exc)})
            elif row['ObjectName'] in {'AcDb2dPolyline', 'AcDb3dPolyline', 'AcDbPolygonMesh', 'AcDbPolyFaceMesh'}:
                issues.append({'id': handle, 'property': 'width', 'error': 'Legacy/3D polyline width inspection requires dedicated reader'})
            if row['ObjectName'] in {'AcDbBlockReference', 'AcDbMInsertBlock'}:
                for name in ('Name', 'XScaleFactor', 'YScaleFactor', 'ZScaleFactor'):
                    row[name] = read(entity, name, handle)
                name = row['Name']
                if name and name not in blocks:
                    blocks[name] = []  # cycle guard retains the reference explicitly
                    definition = retry(lambda: document.Blocks.Item(name))
                    if read(definition, 'IsXRef', name):
                        issues.append({'id': handle, 'property': 'block', 'error': 'External reference requires its own review'})
                    else:
                        blocks[name] = entities(definition, depth + 1)
                if read(entity, 'HasAttributes', handle):
                    issues.append({'id': handle, 'property': 'attributes', 'error': 'Attached attribute style requires dedicated reader'})
            rows.append(row)
        return rows

    variables = {}
    for name in ('INSUNITS', 'LWDISPLAY', 'LWDEFAULT', 'CELWEIGHT', 'PLINEWID', 'LTSCALE', 'PSLTSCALE', 'PSTYLEMODE'):
        try:
            variables[name] = retry(lambda: document.GetVariable(name), timeout=2)
        except Exception as exc:
            issues.append({'id': 'document', 'property': name, 'error': str(exc)})
    model = entities(retry(lambda: document.ModelSpace))
    return {'layers': layers, 'variables': variables, 'model': model, 'blocks': blocks,
            'issues': issues, 'properties_complete': not issues, 'settings_changed': False,
            'geometry_checked': False, 'native_plot_checked': False}
