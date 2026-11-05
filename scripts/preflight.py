"""Dependency-free capability check; never downloads, starts services or contacts CAD."""
import argparse
import importlib.util
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ['SKILL.md', 'scripts/entry.py', 'src/luomu_cad/server.py',
            'examples/two-room.json', 'references/usage.md', 'pyproject.toml', 'uv.lock']
MODULES = ['mcp', 'ezdxf', 'shapely', 'ortools', 'matplotlib', 'PIL', 'scrapling', 'protego']


def inspect_environment(root, system=None, python_version=None, modules=None):
    system = system or platform.system()
    python_version = python_version or sys.version_info[:2]
    modules = modules if modules is not None else {n: importlib.util.find_spec(n) is not None for n in MODULES}
    missing_files = [name for name in REQUIRED if not (Path(root)/name).is_file()]
    missing_modules = [name for name in MODULES if not modules.get(name)]
    compatible_python = tuple(python_version) in {(3, 11), (3, 12)}
    ready = not missing_files and not missing_modules and compatible_python
    return {'package_complete': not missing_files, 'missing_files': missing_files,
            'platform': system, 'python': '.'.join(map(str, python_version)),
            'compatible_python': compatible_python, 'missing_modules': missing_modules,
            'reference_ready': not missing_files, 'offline_runtime_ready': ready,
            'live_platform_supported': system == 'Windows', 'cad_connection_verified': False,
            'network_accessed': False, 'configuration_changed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['reference', 'offline', 'live'], default='reference')
    args = parser.parse_args()
    result = inspect_environment(ROOT)
    ok = result['reference_ready']
    if args.mode != 'reference':
        ok = ok and result['offline_runtime_ready']
    if args.mode == 'live':
        ok = ok and result['live_platform_supported']
    result.update(ok=ok, requested_mode=args.mode)
    if not result['package_complete']:
        result['next_action'] = 'Use the complete Skill package; required resources are missing.'
    elif args.mode == 'live' and not result['live_platform_supported']:
        result['next_action'] = 'Live AutoCAD requires local Windows; do not start retries in this environment.'
    elif args.mode != 'reference' and not result['offline_runtime_ready']:
        result['next_action'] = 'Prepare Python 3.11/3.12 and locked dependencies as documented; reference reading remains available.'
    else:
        result['next_action'] = 'Read the task-specific reference; live connection still requires a separate authorized MCP check.'
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
