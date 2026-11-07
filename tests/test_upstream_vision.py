"""Opt-in integration checks for the upstream packages used in the skill.

Set LUOMU_CAD_TEST_VISION=1 after installing the vision extra.
OCR downloads upstream models on first use. No model responses are mocked.
"""
import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

pytestmark = pytest.mark.skipif(
    os.environ.get('LUOMU_CAD_TEST_VISION') != '1',
    reason='Opt-in upstream vision inference and model downloads',
)


@pytest.fixture(scope='module')
def ocr_engine(tmp_path_factory):
    from rapidocr import RapidOCR
    model_dir = os.environ.get('LUOMU_CAD_VISION_MODELS')
    if model_dir is None:
        model_dir = str(tmp_path_factory.mktemp('ocr-models'))
    return RapidOCR(params={
        'Global.model_root_dir': model_dir,
        'EngineConfig.onnxruntime.intra_op_num_threads': 4,
        'EngineConfig.onnxruntime.inter_op_num_threads': 1,
    })


@pytest.mark.parametrize('rotation', [0, 180])
def test_real_upstream_ocr_text_and_pixel_boxes(ocr_engine, rotation):
    from matplotlib.font_manager import findfont
    image = Image.new('RGB', (750, 270), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(findfont('DejaVu Sans'), 32)
    expected = ['CAD 3600', 'DN50', 'R150', '900 mm', 'LEVEL -0.050']
    for index, text in enumerate(expected):
        draw.text((30, 10 + index * 50), text, fill='black', font=font)
    result = ocr_engine(image.rotate(rotation)).to_json()
    assert result, 'No text returned by the actual upstream model'
    assert {line['txt'].replace(' ', '') for line in result} == {
        line.replace(' ', '') for line in expected}
    for line in result:
        assert 0 <= line['score'] <= 1
        assert len(line['box']) == 4
        assert all(0 <= x <= image.width and 0 <= y <= image.height for x, y in line['box'])


def test_official_qwen_zoom_returns_local_image_and_reports_invalid_box(tmp_path):
    from qwen_agent.llm.schema import Message, ContentItem
    from qwen_agent.tools.image_zoom_in_qwen3vl import ImageZoomInToolQwen3VL
    source = tmp_path / 'source.png'
    image = Image.new('RGB', (400, 300), 'white')
    ImageDraw.Draw(image).rectangle((110, 85, 290, 215), fill='blue')
    image.save(source)
    tool = ImageZoomInToolQwen3VL({'work_dir': str(tmp_path / 'zoom')})
    messages = [Message(role='user', content=[ContentItem(image=str(source))])]
    result = tool.call({'bbox_2d': [250, 250, 750, 750], 'label': 'region', 'img_idx': 0},
                       messages=messages)
    output = Path(result[0].image)
    assert output.is_file()
    with Image.open(output) as crop:
        assert crop.width % 32 == 0 and crop.height % 32 == 0
        assert crop.getpixel((crop.width // 2, crop.height // 2)) == (0, 0, 255)
        assert crop.getpixel((0, 0)) == (255, 255, 255)
    invalid = tool.call({'bbox_2d': [500, 500, 500, 500], 'label': 'empty', 'img_idx': 0},
                        messages=messages)
    assert invalid[0].image is None and 'Error' in invalid[0].text


def test_anthropic_pdfium_render_example(tmp_path):
    import pypdfium2 as pdfium
    from pypdf import PdfWriter
    source = tmp_path / 'page.pdf'
    writer = PdfWriter()
    writer.add_blank_page(width=400, height=300)
    writer.write(source)
    pdf = pdfium.PdfDocument(source)
    page = pdf[0]
    bitmap = page.render(scale=2.0, rotation=0)
    try:
        image = bitmap.to_pil()
        assert image.size == (800, 600)
        assert image.convert('RGB').getpixel((100, 100)) == (255, 255, 255)
    finally:
        bitmap.close()
        page.close()
        pdf.close()
