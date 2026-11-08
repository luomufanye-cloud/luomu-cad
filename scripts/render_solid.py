"""Render saved STEP geometry in the separate solid runtime, without OpenGL."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src' if (ROOT / 'src').is_dir() else ROOT))
from luomu_cad.solid_render import render

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(render(args.source, args.output)))
