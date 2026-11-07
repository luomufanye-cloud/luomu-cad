"""Create a professional review template or measure a saved DXF against it."""
import argparse
import json
from pathlib import Path
import sys
import ezdxf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from luomu_cad.professional import audit, template


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('drawing', type=Path, nargs='?')
    parser.add_argument('manifest', type=Path, nargs='?')
    parser.add_argument('--profile', action='append')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.resolve() in {p.resolve() for p in (args.drawing, args.manifest) if p}:
        raise ValueError('Report must not overwrite an input')
    if args.profile:
        if args.drawing or args.manifest:
            parser.error('Template mode accepts profiles only')
        result = template(args.profile)
        success = True
    else:
        if not args.drawing or not args.manifest:
            parser.error('Drawing and manifest required')
        try:
            value = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
            if args.report.resolve() == (args.manifest.parent / value.get('source', {}).get('path', '')).resolve():
                raise ValueError('Report must not overwrite source evidence')
            result = audit(args.drawing, value, args.manifest.parent)
        except (ValueError, KeyError, TypeError, OSError, ezdxf.DXFError) as error:
            result = {'technical_checks_passed': False, 'errors': [str(error)],
                      'review_record_complete': False, 'engineering_approval': False}
        success = result['technical_checks_passed'] and result['review_record_complete']
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(args.report), 'success': success}, ensure_ascii=False))
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
