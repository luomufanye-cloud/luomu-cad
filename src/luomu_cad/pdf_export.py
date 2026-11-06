"""Vector PDF output with an explicit model window and physical paper scale."""
from io import BytesIO
import math
from pathlib import Path
import ezdxf
from .plan import number


def render_pdf(source, paper_mm, window_mm, scale, margin_mm=10):
    if len(paper_mm)!=2 or len(window_mm)!=4:raise ValueError('Paper [width,height] and window [xmin,ymin,xmax,ymax] required')
    width,height=[number(v,'paper mm',1) for v in paper_mm]
    if max(width,height)>2000:raise ValueError('Paper exceeds 2000 mm')
    x0,y0,x1,y1=[number(v,'model window') for v in window_mm]
    scale=number(scale,'scale denominator',.001);margin=number(margin_mm,'paper margin',0)
    if x1<=x0 or y1<=y0:raise ValueError('Positive model window required')
    if (x1-x0)/scale>width-2*margin or (y1-y0)/scale>height-2*margin:
        raise ValueError('Requested model window does not fit paper at the specified scale')
    doc=ezdxf.readfile(source)
    if doc.units!=4:raise ValueError('Explicit mm DXF required for physical PDF scale')
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.figure import Figure
    from ezdxf.addons.drawing import Frontend,RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from ezdxf.addons.drawing.config import Configuration,BackgroundPolicy,ColorPolicy
    from .annotations import text_style_findings
    findings=text_style_findings(doc)
    if findings:raise ValueError('Resolve text/font issues before PDF output: '+str(findings[:3]))
    # Fixed window, centered on the sheet. No auto-fit or tight-bbox cropping.
    plot_width=(x1-x0)/scale;plot_height=(y1-y0)/scale
    figure=Figure(figsize=(width/25.4,height/25.4))
    ax=figure.add_axes([0,0,1,1]);ax.axis('off')
    config=Configuration(background_policy=BackgroundPolicy.WHITE,color_policy=ColorPolicy.COLOR,
                         min_lineweight=.01,lineweight_scaling=72/25.4)
    Frontend(RenderContext(doc),MatplotlibBackend(ax),config=config).draw_layout(doc.modelspace(),finalize=True)
    figure.set_size_inches(width/25.4,height/25.4)
    ax.set_position([(1-plot_width/width)/2,(1-plot_height/height)/2,plot_width/width,plot_height/height])
    ax.set_aspect('equal',adjustable='box');ax.set_xlim(x0,x1);ax.set_ylim(y0,y1)
    stream=BytesIO()
    figure.savefig(stream,format='pdf',facecolor='white',metadata={'Title':'Luomu CAD drawing','Creator':'Luomu CAD'})
    data=stream.getvalue()
    if not data.startswith(b'%PDF-'):raise RuntimeError('PDF backend did not return a PDF')
    return data,{'paper_mm':[width,height],'window_mm':[x0,y0,x1,y1],'scale':scale,
                 'drawing_on_paper_mm':[plot_width,plot_height],'margin_mm':margin,
                 'method':'vector PDF from saved DXF; explicit window and physical scale'}
