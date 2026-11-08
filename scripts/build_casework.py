"""Create or independently review shared-model cabinet multiview drawings."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from luomu_cad.casework import build, review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['build', 'review'])
    parser.add_argument('--spec', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--drawing', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--requirements', type=Path)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    def read(path):
        return json.loads(path.read_text(encoding='utf-8-sig'))
    requirements = read(args.requirements) if args.requirements else None
    if args.operation == 'build':
        if not args.spec or not args.output:
            parser.error('build requires --spec and --output')
        result = build(read(args.spec), args.output, requirements, args.source)
    else:
        if not args.drawing or not args.manifest:
            parser.error('review requires --drawing and --manifest')
        result = review(args.drawing, read(args.manifest), requirements, args.source)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
