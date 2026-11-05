"""Original simulated pipe-root section exercises; never a construction detail.

All dimensions are explicit training inputs, not manufacturer dimensions.
Checks measure saved geometry, and do not assess sealing, material or compliance.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import ezdxf
from luomu_cad.qa import render_dxf, file_hash
from luomu_cad.storage import ROOT, atomic_json


def draw(path, variant):
    doc = ezdxf.new('R2013')
    doc.units = 4
    m = doc.modelspace()
    for layer, color in [('SLAB', 8), ('BASE', 9), ('FINISH', 3), ('PIPE', 7), ('SEAL', 6), ('DETAIL', 1), ('NOTE', 7)]:
        doc.layers.add(layer, color=color)
    def line(layer, a, b):
        m.add_line(a, b, dxfattribs={'layer': layer})
    finish = 80 if variant in {'raised_finish', 'raised_finish_fixed'} else 50
    bond = 80 if variant == 'raised_finish_fixed' else 50
    # x=+/-55: outside faces of a fictitious 110mm pipe; z=0: slab top.
    line('SLAB', (-300, -120), (300, -120))
    for side in [-1, 1]:
        x = side * 55
        line('SLAB', (x, 0), (side * 300, 0))
        line('BASE', (x, 20), (side * 300, 20))
        line('FINISH', (x, finish), (side * 300, finish))
        line('PIPE', (x, -120), (x, 150))
        if variant != 'missing_seal':
            line('SEAL', (x, 0), (x + side * 12, 0))
        # DETAIL is a zero-thickness continuity teaching path, not a film thickness.
        bottom = 25 if variant == 'gap' and side == 1 else 20
        line('DETAIL', (x, bottom), (x, 20 + bond))
        line('DETAIL', (x, 20), (x + side * 180, 20))
    labels = ['SIMULATED PIPE ROOT SECTION - mm', 'Inputs: OD110 / slab120 / base20; finish and bond vary', 'DETAIL path has no film thickness; SEAL is an interface marker', 'No project adoption, water test, bonding or structural approval', variant]
    for i, label in enumerate(labels):
        m.add_text(label, dxfattribs={'height': 7, 'layer': 'NOTE', 'insert': (-300, 205 - i * 14)})
    doc.saveas(path)


def measure(path):
    doc = ezdxf.readfile(path)
    issues = []
    if doc.units != 4:
        issues.append('drawing units are not mm')
    lines = {}
    for e in doc.modelspace().query('LINE'):
        a, b = tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]
        lines.setdefault(e.dxf.layer, []).append((a, b))
    finish_z = max(a[1] for a, b in lines['FINISH'])
    measured = []
    for side in [-1, 1]:
        x = side * 55
        vertical = [(a, b) for a, b in lines['DETAIL'] if abs(a[0] - x) < 1e-6 and abs(b[0] - x) < 1e-6]
        horizontal = [(a, b) for a, b in lines['DETAIL'] if abs(a[1] - 20) < 1e-6 and abs(b[1] - 20) < 1e-6 and a[0] == x]
        if len(vertical) != 1 or len(horizontal) != 1:
            issues.append(f'missing detail path at {x}')
            continue
        a, b = vertical[0]
        if a != horizontal[0][0]:
            issues.append(f'detail discontinuity at {x}')
        if max(a[1], b[1]) <= finish_z:
            issues.append(f'detail termination buried by simulated finish at {x}')
        seals = [(a, b) for a, b in lines.get('SEAL', []) if a == (x, 0)]
        if len(seals) != 1:
            issues.append(f'no sealing-interface marker at {x}')
        measured.append({'pipe_face_x_mm': x, 'detail_top_mm': max(a[1], b[1]), 'finish_mm': finish_z, 'spread_mm': abs(horizontal[0][1][0] - x)})
    return {'ok': not issues, 'issues': issues, 'measurements': measured, 'engineering_approval': False, 'scope': 'saved LINE geometry and explicit simulated datums only'}


def main():
    output = ROOT / 'runtime/training/pipe-penetration'
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    expected = {'normal': True, 'gap': False, 'missing_seal': False, 'raised_finish': False, 'raised_finish_fixed': True}
    for name, passes in expected.items():
        path = output / f'{name}.dxf'
        draw(path, name)
        check = measure(path)
        assert check['ok'] == passes, (name, check)
        results[name] = {**check, 'sha256': file_hash(path)}
        if name in {'normal', 'raised_finish'}:
            results[name]['preview'] = render_dxf(path, output / f'{name}.png')
    atomic_json(output / 'results.json', results)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
