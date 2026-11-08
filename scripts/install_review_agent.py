"""Install project-scoped CAD review agents; no model, permission or global config changes."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from luomu_cad.reviewer_install import install, verify


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', required=True, type=Path)
    parser.add_argument('--bundle-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--host', choices=['auto','codex','claude','t3'], default='auto')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    result = verify(args.project_root, args.host) if args.verify else install(args.bundle_root, args.project_root, args.host)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
