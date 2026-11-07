"""Score semantic polygons against separately reviewed source annotations."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from luomu_cad.scene_benchmark import evaluate, file_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('prediction', type=Path)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--iou-threshold', type=float, default=.5)
    args = parser.parse_args()
    if args.report.resolve() in {p.resolve() for p in (args.reference, args.prediction, args.source)}:
        raise ValueError('Report must not overwrite an input')
    reference = json.loads(args.reference.read_text(encoding='utf-8-sig'))
    prediction = json.loads(args.prediction.read_text(encoding='utf-8-sig'))
    if reference.get('source_sha256') != file_hash(args.source):
        raise ValueError('Reference does not belong to the supplied source')
    result = evaluate(reference, prediction, args.iou_threshold)
    result.update(reference_sha256=file_hash(args.reference), prediction_sha256=file_hash(args.prediction))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(args.report), 'classes': result['classes']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
