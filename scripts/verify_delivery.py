"""Create a delivery contract template or review actual customer-bound files."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from luomu_cad.delivery import review,template


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['template','review'])
    parser.add_argument('--industry',action='append',default=[])
    parser.add_argument('--contract',type=Path)
    parser.add_argument('--base',type=Path)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if args.operation=='template':
        result=template(args.industry)
    else:
        if not args.contract or not args.base:
            parser.error('review requires --contract and --base')
        contract=json.loads(args.contract.read_text(encoding='utf-8-sig'))
        result=review(contract,args.base)
    text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
    if args.report:
        if args.report.exists():
            parser.error('Report already exists; choose a fresh path')
        args.report.parent.mkdir(parents=True,exist_ok=True)
        with args.report.open('x',encoding='utf8') as stream:stream.write(text+'\n')
    print(text)
    return 0 if args.operation=='template' or result['accepted_for_delivery'] else 1


if __name__=='__main__':
    raise SystemExit(main())
