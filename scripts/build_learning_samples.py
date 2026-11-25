"""Build, verify or preview the original learning sample drawings in examples/."""
import argparse
import json
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from luomu_cad.learning_samples import SAMPLES, build, canonical
from luomu_cad.qa import audit_dxf, render_dxf

INDEX = 'learning-samples.json'


def _text(path):
    return Path(path).read_text(encoding='utf-8').replace('\r\n', '\n')


def check(directory):
    """Regenerate into a temporary folder and compare with the committed files."""
    directory = Path(directory)
    with tempfile.TemporaryDirectory(prefix='luomu-learning-') as temporary:
        build(temporary)
        names = [name for name, _ in SAMPLES] + [INDEX]
        compare = lambda name: (canonical if name.endswith('.dxf') else _text)
        stale = [name for name in names if not (directory / name).is_file()
                 or compare(name)(directory / name) != compare(name)(Path(temporary) / name)]
    audits = {name: audit_dxf(directory / name)['checks_status'] for name, _ in SAMPLES if (directory / name).is_file()}
    return {'ok': not stale and all(v == 'PASS' for v in audits.values()), 'stale': stale, 'audits': audits}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['build', 'check', 'preview'])
    parser.add_argument('--output', type=Path, default=ROOT / 'examples',
                        help='build: DXF/JSON folder (default examples/); preview: PNG folder')
    args = parser.parse_args()
    if args.operation == 'build':
        index = build(args.output)
        result = {'ok': True, 'samples': [s['file'] for s in index['samples']], 'output': str(args.output)}
    elif args.operation == 'check':
        result = check(ROOT / 'examples')
    else:
        args.output.mkdir(parents=True, exist_ok=True)
        result = {'ok': True, 'previews': [render_dxf(ROOT / 'examples' / name, args.output / (name[:-4] + '.png'))['path']
                                            for name, _ in SAMPLES],
                  'note': 'Offline ezdxf rendering; some CJK glyphs (for example 图) may be filled solid by the renderer.'}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
