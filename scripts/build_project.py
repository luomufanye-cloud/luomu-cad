"""Build or verify a source-linked room atlas; revisions always create a new bundle."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from luomu_cad.shared_project import build, review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['build', 'review'])
    parser.add_argument('--spec', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--requirements', type=Path)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    requirements = json.loads(args.requirements.read_text(encoding='utf-8-sig')) if args.requirements else None
    if args.operation == 'build':
        if not args.spec:
            parser.error('build requires --spec')
        result = build(json.loads(args.spec.read_text(encoding='utf-8-sig')), args.output, args.previous, requirements, args.source)
    else:
        result = review(args.output, requirements, args.source)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
