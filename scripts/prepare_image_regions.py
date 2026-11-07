"""Create portable, source-linked image views for model inspection."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile

from PIL import Image, ImageOps


def tile_boxes(width, height, tile_size, overlap):
    """Cover every source pixel, with shared context between adjacent tiles."""
    step = tile_size - overlap
    for top in range(0, height, step):
        for left in range(0, width, step):
            yield [left, top, min(left + tile_size, width), min(top + tile_size, height)]
            if left + tile_size >= width:
                break
        if top + tile_size >= height:
            break


def atomic_write(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.pending-', delete=False) as pending:
        pending.write(data)
        pending_path = Path(pending.name)
    os.replace(pending_path, path)


def save_png(path, image):
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    data = buffer.getvalue()
    atomic_write(path, data)
    return hashlib.sha256(data).hexdigest()


def prepare(source, output, regions=None, tile_size=1024, overlap=128, zoom=2, frame=0):
    for name, value, minimum in [('tile_size', tile_size, 1), ('overlap', overlap, 0),
                                  ('zoom', zoom, 1), ('frame', frame, 0)]:
        if type(value) is not int or value < minimum:
            raise ValueError(f'{name} must be an integer >= {minimum}')
    if overlap >= tile_size or zoom > 4:
        raise ValueError('Require overlap < tile_size and zoom <= 4')
    source = Path(source).resolve(strict=True)
    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    with Image.open(io.BytesIO(source_bytes)) as original:
        if frame >= getattr(original, 'n_frames', 1):
            raise ValueError('Requested frame is outside the image')
        original.seek(frame)
        stored_size = list(original.size)
        orientation = original.getexif().get(274, 1)
        oriented = ImageOps.exif_transpose(original).convert('RGBA')
        # Make transparent line drawings visible on a declared white background.
        image = Image.new('RGBA', oriented.size, 'white')
        image.alpha_composite(oriented)
        image = image.convert('RGB')
    width, height = image.size
    if regions is None:
        regions = [{'id': f'region-{index:04d}', 'box': box}
                   for index, box in enumerate(tile_boxes(width, height, tile_size, overlap))]
    if not isinstance(regions, list) or not regions:
        raise ValueError('Regions must be a nonempty array')
    identifiers = set()
    for region in regions:
        if not isinstance(region, dict):
            raise ValueError('Each region must be an object')
        identifier = region.get('id')
        if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', identifier):
            raise ValueError('Region id must contain 1-64 letters, numbers, hyphens or underscores')
        if identifier.casefold() in identifiers:
            raise ValueError('Region ids must be unique, ignoring case')
        identifiers.add(identifier.casefold())
        box = region.get('box')
        if not isinstance(box, list) or len(box) != 4 or any(type(value) is not int for value in box):
            raise ValueError(f'{identifier}: box must contain four integers')
        left, top, right, bottom = box
        if not (0 <= left < right <= width and 0 <= top < bottom <= height):
            raise ValueError(f'{identifier}: box outside oriented image {width}x{height}')
    settings = {'schema_version': 1, 'source_sha256': source_hash, 'frame': frame,
                'regions': regions, 'zoom': zoom, 'background_rgb': [255, 255, 255]}
    fingerprint = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
    bundle = Path(output).resolve() / fingerprint
    bundle.mkdir(parents=True, exist_ok=True)
    overview = image.copy()
    overview.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    overview_hash = save_png(bundle / 'overview.png', overview)
    prepared = []
    for index, region in enumerate(regions):
        left, top, right, bottom = region['box']
        crop = image.crop((left, top, right, bottom))
        scale = min(zoom, max(1, 2048 // max(crop.size)))
        native_name = f'crop-{index:04d}.png'
        view_name = f'view-{index:04d}.png'
        native_hash = save_png(bundle / native_name, crop)
        view_hash = save_png(bundle / view_name, crop.resize(
            (crop.width * scale, crop.height * scale), Image.Resampling.NEAREST))
        prepared.append({'id': region['id'], 'box': region['box'], 'native_size': list(crop.size),
                         'native_path': native_name, 'native_sha256': native_hash,
                         'view_path': view_name, 'view_sha256': view_hash, 'view_scale': scale,
                         'view_to_source': {'scale_x': 1 / scale, 'scale_y': 1 / scale,
                                            'offset_x': left, 'offset_y': top}})
    manifest = {'schema_version': 1, 'source_sha256': source_hash, 'frame': frame,
                'stored_size': stored_size, 'source_exif_orientation': orientation,
                'oriented_size': [width, height], 'background_rgb': [255, 255, 255],
                'coordinate_space': 'EXIF-oriented source pixels; origin top-left; x right; y down',
                'overview': {'path': 'overview.png', 'sha256': overview_hash,
                             'size': list(overview.size),
                             'view_to_source': {'scale_x': width / overview.width,
                                                'scale_y': height / overview.height,
                                                'offset_x': 0, 'offset_y': 0}},
                'regions': prepared}
    manifest_path = bundle / 'regions.json'
    atomic_write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf8'))
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--regions', type=Path, help='Optional JSON array of id/box regions')
    parser.add_argument('--tile-size', type=int, default=1024)
    parser.add_argument('--overlap', type=int, default=128)
    parser.add_argument('--zoom', type=int, default=2)
    parser.add_argument('--frame', type=int, default=0)
    args = parser.parse_args()
    try:
        regions = json.loads(args.regions.read_text(encoding='utf-8-sig')) if args.regions else None
        path = prepare(args.source, args.output, regions, args.tile_size, args.overlap, args.zoom, args.frame)
    except (OSError, ValueError) as error:
        parser.exit(2, f'{error}\n')
    print(json.dumps({'manifest': str(path)}, ensure_ascii=True))


if __name__ == '__main__':
    main()
