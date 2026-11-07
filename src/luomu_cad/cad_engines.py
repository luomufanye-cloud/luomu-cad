"""Thin adapters over upstream CAD kernels, with actual exported-file readback.

Model scripts are reviewed local Python code and execute with normal OS rights.
Optional kernels are installed in a separate interpreter, not imported at startup.
"""
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import runpy
import tempfile


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect_step(path):
    import cadquery as cq

    model = cq.importers.importStep(str(path)).val()
    solids = model.Solids()
    box = model.BoundingBox()
    return {'valid': model.isValid() and bool(solids), 'solid_count': len(solids),
            'volume_mm3': sum(s.Volume() for s in solids),
            'bbox_mm': [box.xlen, box.ylen, box.zlen]}


def inspect_ifc(path):
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.shape
    import ifcopenshell.validate

    model = ifcopenshell.open(str(path))
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(model, logger)
    issues = [str(s['message']) for s in logger.statements if s.get('level') == 'error']
    elements = []
    settings = ifcopenshell.geom.settings()
    for product in model.by_type('IfcElement'):
        if not product.Representation:
            continue
        try:
            shape = ifcopenshell.geom.create_shape(settings, product)
            geometry = shape.geometry
            volume = ifcopenshell.util.shape.get_volume(geometry)
            if not math.isfinite(volume) or volume <= 0:
                issues.append(f'{product.GlobalId}: non-positive volume')
            elements.append({'id': product.GlobalId, 'name': product.Name, 'class': product.is_a(),
                             'net_volume_m3': volume})
        except Exception as error:
            issues.append(f'{product.GlobalId}: {error}')
    voids = [{'host': r.RelatingBuildingElement.GlobalId, 'opening': r.RelatedOpeningElement.GlobalId}
             for r in model.by_type('IfcRelVoidsElement')]
    fills = [{'opening': r.RelatingOpeningElement.GlobalId, 'filling': r.RelatedBuildingElement.GlobalId}
             for r in model.by_type('IfcRelFillsElement')]
    for opening in model.by_type('IfcOpeningElement'):
        if len(opening.VoidsElements) != 1:
            issues.append(f'{opening.GlobalId}: opening needs exactly one host')
    return {'schema': model.schema, 'valid': bool(elements) and not issues,
            'elements': elements, 'voids': voids, 'fills': fills, 'issues': issues}


def check_contract(measurements, contract):
    """Explicit intervals from an independent source, no inferred default sizes."""
    failures = []
    for key, bounds in contract.items():
        value = measurements.get(key)
        if key not in {'solid_count', 'volume_mm3', 'bbox_mm'}:
            raise ValueError('Unsupported STEP contract measurement: ' + key)
        values = value if isinstance(value, list) else [value]
        intervals = bounds if key == 'bbox_mm' else [bounds]
        if len(values) != len(intervals):
            raise ValueError('Contract shape does not match measurement')
        for measured, interval in zip(values, intervals):
            if len(interval) != 2 or any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in interval) or interval[0] > interval[1]:
                raise ValueError('Finite ordered measurement intervals required')
            if measured is None or not interval[0] <= measured <= interval[1]:
                failures.append({'measurement': key, 'actual': measured, 'expected_interval': interval})
    return failures


def build(engine, script, output, contract=None):
    """Run a reviewed script defining result, export, reopen, and record hashes.

    Existing matching outputs are verified and reused. Other outputs are refused.
    Native CAD operations are outside this offline adapter.
    """
    if engine not in {'cadquery', 'ifcopenshell'}:
        raise ValueError('Unknown CAD engine')
    script, output = Path(script).resolve(), Path(output).resolve()
    contract = contract or {}
    if engine == 'ifcopenshell' and contract:
        raise ValueError('STEP interval contracts apply to CadQuery only')
    request = {'engine': engine, 'source_sha256': digest(script), 'contract': contract,
               'engine_version': importlib.metadata.version(engine)}
    if output.exists():
        report = json.loads((output / 'report.json').read_text(encoding='utf-8'))
        if report['request'] != request or any(digest(output / name) != sha for name, sha in report['artifacts'].items()):
            raise ValueError('Existing output differs; choose a fresh output directory')
        return report
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cad-build-', dir=output.parent) as temporary:
        stage = Path(temporary)
        namespace = runpy.run_path(str(script))
        if 'result' not in namespace:
            raise ValueError('Model script must define result')
        result = namespace['result']
        if engine == 'cadquery':
            import cadquery as cq

            if isinstance(result, cq.Workplane):
                result = result.val()
            if not isinstance(result, cq.Shape) or not result.isValid() or not result.Solids():
                raise ValueError('result must be a valid CadQuery solid or compound')
            cq.exporters.export(result, str(stage / 'model.step'))
            # Orthographic views retain geometry for visual comparison, with no auto-repair.
            for name, direction in {'front': (0, -1, 0), 'top': (0, 0, 1), 'right': (1, 0, 0)}.items():
                cq.exporters.export(result, str(stage / f'{name}.svg'),
                                    opt={'projectionDir': direction, 'showAxes': False})
            measurements = inspect_step(stage / 'model.step')
            failures = check_contract(measurements, contract)
        else:
            import ifcopenshell

            if not isinstance(result, ifcopenshell.file):
                raise ValueError('result must be an ifcopenshell.file')
            result.write(str(stage / 'model.ifc'))
            measurements = inspect_ifc(stage / 'model.ifc')
            failures = measurements['issues']
        # Persist the editable program alongside the exchange geometry.
        (stage / 'model.py').write_bytes(script.read_bytes())
        report = {'request': request, 'measurements': measurements, 'failures': failures,
                  'geometry_passed': measurements['valid'] and not failures,
                  'source_fidelity_verified': False, 'engineering_approval': False,
                  'artifacts': {p.name: digest(p) for p in stage.iterdir()}}
        (stage / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        # Atomic rename on the same volume. A concurrent producer cannot be overwritten.
        os.rename(stage, output)
    return report
