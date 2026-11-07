"""Execute a reviewed local parametric model with an installed upstream kernel."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from luomu_cad.cad_engines import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('engine', choices=['cadquery', 'ifcopenshell'])
    parser.add_argument('script', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--contract', type=Path)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding='utf-8-sig')) if args.contract else {}
    result = build(args.engine, args.script, args.output, contract)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['geometry_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
