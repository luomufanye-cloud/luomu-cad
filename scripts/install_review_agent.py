"""Install project-scoped CAD review agents; no model, permission or global config changes."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from luomu_cad.reviewer_install import install, verify, install_codex_home, verify_codex_home


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--project-root', type=Path)
    scope.add_argument('--codex-home', type=Path, help='Explicit opt-in: install a personal role under this CODEX_HOME/agents')
    parser.add_argument('--bundle-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--host', choices=['auto','codex','claude','t3'], default='auto')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.codex_home:
        if args.host not in {'auto', 'codex', 't3'}:
            parser.error('--codex-home installs the Codex personal role, not a Claude role')
        result = verify_codex_home(args.codex_home) if args.verify else install_codex_home(args.bundle_root, args.codex_home)
    else:
        result = verify(args.project_root, args.host) if args.verify else install(args.bundle_root, args.project_root, args.host)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
