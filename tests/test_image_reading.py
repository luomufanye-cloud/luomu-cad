"""Generated fixtures exercise image preparation without private project images."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageOps
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_image_regions import prepare


def source_image(tmp_path, size=(230, 170)):
    image = Image.new('RGB', size, 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 40, 50), outline='black', width=2)
    draw.ellipse((45, 20, 85, 60), outline='blue', width=2)
    draw.line((0, size[1] - 1, size[0] - 1, 0), fill='red')
    source = tmp_path / '参考 image.png'
    image.save(source)
    return source, image


@pytest.mark.parametrize('size', [(1, 1), (230, 170), (30, 410), (420, 20)])
def test_tiles_cover_source_and_preserve_pixels_and_coordinates(tmp_path, size):
    source, image = source_image(tmp_path, size)
    path = prepare(source, tmp_path / 'reading', tile_size=96, overlap=16)
    manifest = json.loads(path.read_text())
    assert manifest['source_sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    coverage = Image.new('1', size)
    draw = ImageDraw.Draw(coverage)
    for region in manifest['regions']:
        left, top, right, bottom = region['box']
        draw.rectangle((left, top, right - 1, bottom - 1), fill=1)
        crop_path = path.parent / region['native_path']
        assert not Path(region['native_path']).is_absolute()
        assert region['native_sha256'] == hashlib.sha256(crop_path.read_bytes()).hexdigest()
        with Image.open(crop_path) as crop:
            assert ImageChops.difference(crop, image.crop(region['box'])).getbbox() is None
        with Image.open(path.parent / region['view_path']) as view:
            transform = region['view_to_source']
            assert view.width * transform['scale_x'] + transform['offset_x'] == right
            assert view.height * transform['scale_y'] + transform['offset_y'] == bottom
    assert coverage.getextrema() == (1, 1)


def test_selected_regions_repeat_and_changed_inputs_are_isolated(tmp_path):
    source, image = source_image(tmp_path)
    regions = [{'id': 'part', 'box': [10, 15, 85, 70]},
               {'id': 'part-view', 'box': [5, 10, 90, 80]}]
    path = prepare(source, tmp_path / 'out', regions)
    original_manifest = path.read_bytes()
    assert prepare(source, tmp_path / 'out', regions) == path
    assert path.read_bytes() == original_manifest
    image.putpixel((15, 20), (0, 255, 0))
    image.save(source)
    assert prepare(source, tmp_path / 'out', regions) != path
    assert path.read_bytes() == original_manifest
    assert len(list(path.parent.glob('crop-*.png'))) == 2


def test_exif_orientation_transparency_and_frame_selection(tmp_path):
    source = tmp_path / 'rotated.png'
    image = Image.new('RGB', (60, 30), 'red')
    image.putpixel((0, 0), (0, 0, 255))
    exif = Image.Exif()
    exif[274] = 6
    image.save(source, exif=exif)
    path = prepare(source, tmp_path / 'out')
    manifest = json.loads(path.read_text())
    assert manifest['stored_size'] == [60, 30]
    assert manifest['oriented_size'] == [30, 60]
    with Image.open(source) as original, Image.open(path.parent / 'crop-0000.png') as crop:
        assert ImageChops.difference(crop, ImageOps.exif_transpose(original).convert('RGB')).getbbox() is None
    source = tmp_path / 'alpha.png'
    Image.new('RGBA', (10, 10), (0, 0, 0, 0)).save(source)
    path = prepare(source, tmp_path / 'out')
    with Image.open(path.parent / 'crop-0000.png') as crop:
        assert crop.getpixel((0, 0)) == (255, 255, 255)
    source = tmp_path / 'pages.tiff'
    Image.new('RGB', (20, 10), 'red').save(
        source, save_all=True, append_images=[Image.new('RGB', (30, 20), 'blue')])
    path = prepare(source, tmp_path / 'out', frame=1)
    assert json.loads(path.read_text())['oriented_size'] == [30, 20]
    with Image.open(path.parent / 'crop-0000.png') as crop:
        assert crop.getpixel((0, 0)) == (0, 0, 255)


@pytest.mark.parametrize('options', [
    {'overlap': 1024}, {'tile_size': 0}, {'zoom': 5}, {'frame': 5},
    {'regions': []}, {'regions': [{'id': '../escape', 'box': [0, 0, 10, 10]}]},
    {'regions': [{'id': 'a', 'box': [-1, 0, 10, 10]}]},
    {'regions': [{'id': 'a', 'box': [0, 0, True, 10]}]},
    {'regions': [{'id': 'a', 'box': [0, 0, 10, 10]}, {'id': 'A', 'box': [0, 0, 10, 10]}]},
])
def test_invalid_inputs_fail_before_output(tmp_path, options):
    source, _ = source_image(tmp_path)
    output = tmp_path / 'out'
    with pytest.raises(ValueError):
        prepare(source, output, **options)
    assert not output.exists()


def test_cli_with_unicode_and_spaces(tmp_path):
    source, _ = source_image(tmp_path)
    result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] /
                             'scripts' / 'prepare_image_regions.py'), str(source),
                             '--output', str(tmp_path / '识读 output')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    manifest = Path(json.loads(result.stdout)['manifest'])
    assert manifest.exists()
