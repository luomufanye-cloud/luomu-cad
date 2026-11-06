"""Rasterize a native placeable WMF with its explicit logical coordinate frame.

Uses a memory DC only, never a desktop/window DC. No CAD calls or screen capture.
"""
import ctypes as ct
from ctypes import wintypes as wt
import os
from pathlib import Path
import struct
from PIL import Image


def render_wmf(source,output,max_size=1600):
    if os.name!='nt':raise RuntimeError('Windows GDI is required to render native WMF')
    data=Path(source).read_bytes()
    if len(data)<40 or data[:4]!=b'\xd7\xcd\xc6\x9a':raise ValueError('Placeable WMF required')
    x0,y0,x1,y1=struct.unpack_from('<hhhh',data,6)
    if x1<=x0 or y1<=y0:raise ValueError('Invalid WMF logical bounds')
    if not isinstance(max_size,int) or isinstance(max_size,bool) or not 64<=max_size<=8192:raise ValueError('max_size must be 64..8192')
    scale=max_size/max(x1-x0,y1-y0)
    width,height=max(1,round((x1-x0)*scale)),max(1,round((y1-y0)*scale))
    class Header(ct.Structure):
        _fields_=[('size',wt.DWORD),('width',wt.LONG),('height',wt.LONG),('planes',wt.WORD),
                  ('bits',wt.WORD),('compression',wt.DWORD),('image_size',wt.DWORD),
                  ('xppm',wt.LONG),('yppm',wt.LONG),('used',wt.DWORD),('important',wt.DWORD)]
    class Info(ct.Structure):_fields_=[('header',Header),('colors',wt.DWORD*3)]
    gdi=ct.WinDLL('gdi32',use_last_error=True)
    def bind(name,args,result):
        f=getattr(gdi,name);f.argtypes=args;f.restype=result;return f
    dc_new=bind('CreateCompatibleDC',[wt.HDC],wt.HDC)
    dib=bind('CreateDIBSection',[wt.HDC,ct.POINTER(Info),wt.UINT,ct.POINTER(ct.c_void_p),wt.HANDLE,wt.DWORD],wt.HBITMAP)
    select=bind('SelectObject',[wt.HDC,wt.HANDLE],wt.HANDLE)
    delete=bind('DeleteObject',[wt.HANDLE],wt.BOOL)
    dc_delete=bind('DeleteDC',[wt.HDC],wt.BOOL)
    metafile=bind('SetMetaFileBitsEx',[wt.UINT,ct.c_void_p],wt.HANDLE)
    meta_delete=bind('DeleteMetaFile',[wt.HANDLE],wt.BOOL)
    play=bind('PlayMetaFile',[wt.HDC,wt.HANDLE],wt.BOOL)
    mode=bind('SetMapMode',[wt.HDC,ct.c_int],ct.c_int)
    window=bind('SetWindowExtEx',[wt.HDC,ct.c_int,ct.c_int,ct.c_void_p],wt.BOOL)
    origin=bind('SetWindowOrgEx',[wt.HDC,ct.c_int,ct.c_int,ct.c_void_p],wt.BOOL)
    viewport=bind('SetViewportExtEx',[wt.HDC,ct.c_int,ct.c_int,ct.c_void_p],wt.BOOL)
    flush=bind('GdiFlush',[],wt.BOOL)
    dc=dc_new(None);bitmap=None;old=None;meta=None
    if not dc:raise ct.WinError(ct.get_last_error())
    try:
        info=Info(Header(ct.sizeof(Header),width,-height,1,32,0,width*height*4,0,0,0,0))
        bits=ct.c_void_p()
        bitmap=dib(dc,ct.byref(info),0,ct.byref(bits),None,0)
        if not bitmap:raise ct.WinError(ct.get_last_error())
        old=select(dc,bitmap)
        ct.memset(bits,255,width*height*4)
        content=ct.create_string_buffer(data[22:])
        meta=metafile(len(data)-22,content)
        if not meta:raise ct.WinError(ct.get_last_error())
        mode(dc,8);origin(dc,x0,y0,None);window(dc,x1-x0,y1-y0,None);viewport(dc,width,height,None)
        if not play(dc,meta):raise ct.WinError(ct.get_last_error())
        flush()
        image=Image.frombytes('RGB',(width,height),ct.string_at(bits,width*height*4),'raw','BGRX')
        if not any(lo<hi for lo,hi in image.getextrema()):raise ValueError('Native preview contains no visible drawing')
        image.save(output,format='PNG')
        return {'path':str(Path(output).resolve()) if isinstance(output,(str,Path)) else None,'size':[width,height],
                'logical_bounds':[x0,y0,x1,y1],'renderer':'Windows GDI memory DC, explicit WMF mapping'}
    finally:
        if meta:meta_delete(meta)
        if old:select(dc,old)
        if bitmap:delete(bitmap)
        dc_delete(dc)
