"""Actually painted paths, physical transforms and direction/group equivalence."""
from io import BytesIO
import pytest
from pypdf import PdfWriter,PdfReader
from pypdf.generic import DecodedStreamObject,NameObject
from luomu_cad.pdf_strokes import painted_segments,compare_painted_segments


def paths(commands):
    writer=PdfWriter();page=writer.add_blank_page(width=300,height=200)
    stream=DecodedStreamObject();stream.set_data(commands)
    page[NameObject('/Contents')]=writer._add_object(stream)
    buffer=BytesIO();writer.write(buffer);reader=PdfReader(buffer)
    return painted_segments(reader.pages[0],reader)


def test_actual_ctm_translation_scaling_and_only_painted_widths():
    result=paths(b'q 2 0 0 2 10 20 cm .368503937 w 0 0 m 10 0 l S .01 w Q')
    assert len(result)==1
    geometry,width=result[0]
    assert width==pytest.approx(.26,abs=1e-8)
    assert geometry[1]==pytest.approx((10*25.4/72,20*25.4/72))
    assert geometry[2]==pytest.approx((30*25.4/72,20*25.4/72))


def test_equivalent_direction_and_path_grouping_but_changed_pen_is_rejected():
    expected=paths(b'.368503937 w 0 0 m 10 0 l 20 0 l S')
    actual=paths(b'.368503937 w 20 0 m 10 0 l S 10 0 m 0 0 l S')
    assert compare_painted_segments(actual,expected)['passed']
    wrong=paths(b'.708661417 w 20 0 m 10 0 l S 10 0 m 0 0 l S')
    result=compare_painted_segments(wrong,expected)
    assert not result['passed'] and result['different_segments']==2


def test_nonuniform_physical_pen_is_explicitly_unsupported():
    with pytest.raises(ValueError,match='Nonuniform'):
        paths(b'q 2 0 0 3 0 0 cm 1 w 0 0 m 10 0 l S Q')
