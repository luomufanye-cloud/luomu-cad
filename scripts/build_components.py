"""Discover or build Luomu CAD parametric wall-bound components."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from luomu_cad.components import catalogue, build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['catalogue', 'build'])
    parser.add_argument('--query', default='')
    parser.add_argument('--spec', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.operation == 'catalogue':
        result = catalogue(args.query)
    else:
        if not args.spec or not args.output:
            parser.error('build requires --spec and --output')
        result = build(json.loads(args.spec.read_text(encoding='utf-8-sig')), args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
