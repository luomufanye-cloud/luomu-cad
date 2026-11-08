"""Fixed durable reviewer worker. Not a general command execution interface."""
import argparse
from pathlib import Path
import sys

bundle = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(bundle))
sys.path.insert(0, str(bundle/'src'))
from luomu_cad.review_jobs import worker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', required=True, type=Path)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--nonce', required=True)
    args = parser.parse_args()
    result = worker(args.job, args.base, args.nonce)
    return 0 if result['independent_review_ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
