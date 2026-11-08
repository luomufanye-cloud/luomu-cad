"""Luomu CAD's standalone solid workflow entry point."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src' if (ROOT/'src').is_dir() else ROOT))
from luomu_cad.solid_engine import main

if __name__=='__main__':
    raise SystemExit(main())
