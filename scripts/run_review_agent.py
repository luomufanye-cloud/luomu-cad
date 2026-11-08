"""Run an isolated native CLI CAD reviewer; final delivery still requires actual-file gates."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from luomu_cad.review_runner import run, inspect_packet


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect-packet',type=Path)
    parser.add_argument('--packet',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--codex-home',type=Path)
    parser.add_argument('--project-root',type=Path)
    parser.add_argument('--timeout-seconds',type=float,default=240)
    args=parser.parse_args()
    if args.inspect_packet:
        if args.packet or args.output or args.codex_home or args.project_root:
            parser.error('--inspect-packet is a separate read-only mode')
        print(json.dumps(inspect_packet(args.inspect_packet),ensure_ascii=False))
        return 0
    if not args.packet or not args.output or not args.codex_home:
        parser.error('--packet, --output and --codex-home are required to run a reviewer')
    result=run(args.packet,args.output,args.codex_home,args.project_root,args.timeout_seconds)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['independent_review_ready'] else 1


if __name__=='__main__':raise SystemExit(main())
