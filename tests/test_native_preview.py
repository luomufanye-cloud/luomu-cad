"""Original WMF fixture verifies uniform raster coordinates without AutoCAD."""
import os
import struct
import pytest
from PIL import ImageChops,Image
from luomu_cad.native_preview import render_wmf


@pytest.mark.skipif(os.name!='nt',reason='Windows memory GDI renderer')
def test_wmf_window_mapping_preserves_circle_and_margins(tmp_path):
    def record(fn,*args):return struct.pack('<IH'+'h'*len(args),3+len(args),fn,*args)
    records=[record(0x0103,8),record(0x020b,0,0),record(0x020c,200,500),
             record(0x02fa,0,0,0,0,0),record(0x012d,0),record(0x0418,150,200,50,100),record(0)]
    data=b''.join(records)
    header=struct.pack('<I H hhhh H I',0x9ac6cdd7,0,0,0,500,200,1440,0)
    checksum=0
    for word in struct.unpack('<10H',header):checksum^=word
    standard=struct.pack('<HHHIHIH',1,9,0x300,(18+len(data))//2,1,max(len(r)//2 for r in records),0)
    source=tmp_path/'original.wmf';source.write_bytes(header+struct.pack('<H',checksum)+standard+data)
    output=tmp_path/'circle.png'
    result=render_wmf(source,output,1000)
    assert result['size']==[1000,400]
    image=Image.open(output)
    bounds=ImageChops.difference(image,Image.new('RGB',image.size,'white')).getbbox()
    assert bounds is not None
    left,top,right,bottom=bounds
    assert abs((right-left)-(bottom-top))<=2
    assert 195<=left<=205 and 95<=top<=105 and right<image.width and bottom<image.height
