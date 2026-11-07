"""Read current AutoCAD presentation through a real, read-only stdio MCP session."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from luomu_cad.cli import unpack


async def inspect(args):
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), LUOMU_CAD_ROOT=str(args.report.parent.resolve()),
               LUOMU_CAD_LIVE_WRITES='0')
    params = StdioServerParameters(command=sys.executable, args=['-m', 'luomu_cad.server'], env=env, cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            connected = unpack(await session.call_tool('cad_connect', {'document_name': args.document}))
            if not connected.get('ok'):
                return connected
            return unpack(await session.call_tool('cad_presentation_snapshot', {
                'document_token': connected['document_token'], 'max_entities': args.max_entities}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--document', help='Exact active document name or path, without switching documents')
    parser.add_argument('--max-entities', type=int, default=20000)
    args = parser.parse_args()
    if args.report.suffix.lower() != '.json':
        parser.error('Snapshot report must be JSON')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    result = asyncio.run(inspect(args))
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(args.report), 'ok': result.get('ok'),
                      'properties_complete': result.get('properties_complete'), 'error': result.get('error')}, ensure_ascii=False))
    return 0 if result.get('ok') and result.get('properties_complete') else 1


if __name__ == '__main__':
    raise SystemExit(main())
