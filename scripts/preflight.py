"""Dependency-free capability check; never downloads, starts services or contacts CAD."""
import argparse
import importlib.util
import json
import platform
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ['SKILL.md', 'scripts/entry.py', 'src/luomu_cad/server.py',
            'examples/two-room.json', 'references/usage.md', 'pyproject.toml', 'uv.lock',
            'src/luomu_cad/professional.py', 'references/professional-profiles.json',
            'scripts/verify_professional.py','agents/luomu-cad-reviewer.md',
            'scripts/install_review_agent.py','scripts/verify_delivery.py',
            'src/luomu_cad/delivery.py','src/luomu_cad/industry.py','references/industry-delivery.json',
            'src/luomu_cad/review_runner.py','src/luomu_cad/review_codebuddy.py','src/luomu_cad/cad_access.py','src/luomu_cad/review_evidence_server.py',
            'src/luomu_cad/review_jobs.py','src/luomu_cad/native_delivery.py',
            'src/luomu_cad/native_correspondence.py','src/luomu_cad/pdf_strokes.py',
            'scripts/run_review_agent.py','scripts/review_evidence_server.py',
            'scripts/review_job_worker.py','references/review-agent-jobs.md']
MODULES = ['mcp', 'ezdxf', 'shapely', 'ortools', 'matplotlib', 'PIL', 'scrapling', 'protego']


def runtime_identity(root):
    """Report the actual import, without substituting the working tree on sys.path."""
    import hashlib
    import importlib
    result={'skill_root':str(Path(root).resolve()),'source_version':None,'runtime_version':None,
            'runtime_module':None,'checker_sha256':None}
    project=Path(root)/'pyproject.toml'
    if project.is_file():result['source_version']=tomllib.loads(project.read_text(encoding='utf-8'))['project']['version']
    checker=Path(root)/'scripts/verify_redraw.py'
    if checker.is_file():result['checker_sha256']=hashlib.sha256(checker.read_bytes()).hexdigest()
    try:
        module=importlib.import_module('luomu_cad')
        result.update(runtime_version=module.__version__,runtime_module=str(Path(module.__file__).resolve()))
    except ImportError:pass
    result['versions_match']=result['source_version'] is not None and result['source_version']==result['runtime_version']
    return result


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
    parser.add_argument('--require-version', help='Fail unless both Skill and imported runtime have this version')
    args = parser.parse_args()
    result = inspect_environment(ROOT)
    result['identity']=runtime_identity(ROOT)
    ok = result['reference_ready']
    if args.mode != 'reference':
        ok = ok and result['offline_runtime_ready']
    if args.mode == 'live':
        ok = ok and result['live_platform_supported']
    if args.require_version:
        ok = ok and result['identity']['source_version']==args.require_version and result['identity']['runtime_version']==args.require_version
    result.update(ok=ok, requested_mode=args.mode)
    if not result['package_complete']:
        result['next_action'] = 'Use the complete Skill package; required resources are missing.'
    elif args.require_version and (result['identity']['source_version']!=args.require_version or result['identity']['runtime_version']!=args.require_version):
        result['next_action'] = 'Version mismatch: update the selected Skill environment and reload its MCP process before file tasks.'
    elif args.mode == 'live' and not result['live_platform_supported']:
        result['next_action'] = 'Live AutoCAD requires local Windows; do not start retries in this environment.'
    elif args.mode != 'reference' and not result['offline_runtime_ready']:
        result['next_action'] = 'Prepare Python 3.11/3.12 and locked dependencies as documented; reference reading remains available.'
    else:
        result['next_action'] = 'Read the task-specific reference; live connection still requires a separate authorized MCP check.'
    # ASCII JSON survives mixed Windows console/subprocess code pages intact.
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
