"""Read-only verification of a project standards basis bound to a saved drawing."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from luomu_cad.standards import review_basis


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('drawing',type=Path)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--catalogue',type=Path,help='Optional source-verified project catalogue with the same schema')
    args=parser.parse_args()
    inputs={args.drawing.resolve(),args.manifest.resolve()}
    if args.catalogue:inputs.add(args.catalogue.resolve())
    if args.report.resolve() in inputs:
        raise ValueError('Report cannot overwrite an input')
    manifest=json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    try:
        library=json.loads(args.catalogue.read_text(encoding='utf-8-sig')) if args.catalogue else None
        result=review_basis(manifest,args.drawing,args.manifest.parent,library)
    except (ValueError,KeyError,TypeError,OSError) as exc:
        result={'basis_record_accepted':False,'errors':['INVALID_STANDARDS_BASIS:'+str(exc)],
                'standards_compliance_certified':False,'engineering_approval':False}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result['basis_record_accepted'] else 1


if __name__=='__main__':raise SystemExit(main())
