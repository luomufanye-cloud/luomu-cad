"""Build or verify a source-linked room atlas.

Default output is DXF only; --export-pdf adds sheet PDFs and the atlas, for an explicit PDF request.
Building into an existing atlas directory revises it in place; --previous <other dir> keeps the
old atlas as a separate version and is only for an explicit request to keep one.
"""
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
    parser.add_argument('--export-pdf', action='store_true', help='also write per-sheet PDFs and atlas.pdf (only when PDF was requested)')
    args = parser.parse_args()
    requirements = json.loads(args.requirements.read_text(encoding='utf-8-sig')) if args.requirements else None
    if args.operation == 'build':
        if not args.spec:
            parser.error('build requires --spec')
        result = build(json.loads(args.spec.read_text(encoding='utf-8-sig')), args.output, args.previous, requirements, args.source,
                       export_pdf=args.export_pdf)
    else:
        result = review(args.output, requirements, args.source)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
