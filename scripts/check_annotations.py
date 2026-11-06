"""Check saved text mapping and optional short-extension presentation contract."""
import argparse
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import ezdxf
from luomu_cad.annotations import text_style_findings
from luomu_cad.qa import audit_dxf


def check(path, max_extension=None, min_gap=None):
    for value in (max_extension,min_gap):
        if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0):
            raise ValueError('Limits must be finite positive model lengths')
    doc=ezdxf.readfile(path)
    findings=text_style_findings(doc)
    findings.extend(f for f in audit_dxf(path)['findings'] if f['kind']=='dimension_override_mismatch')
    dimensions=0
    for e in doc.modelspace().query('DIMENSION'):
        if e.dimtype not in (0,1):continue
        dimensions+=1
        style=e.override();scale=style.get('dimscale',1)
        if not math.isfinite(scale) or scale<=0:
            findings.append({'kind':'annotation_scale_unsupported','handle':e.dxf.handle});continue
        if max_extension is not None and (not style.get('dimfxlon',0) or style.get('dimfxl',1)*scale>max_extension+1e-6):
            findings.append({'kind':'extension_not_bounded','handle':e.dxf.handle})
        if min_gap is not None and style.get('dimexo',0)*scale<min_gap-1e-6:
            findings.append({'kind':'extension_gap_too_small','handle':e.dxf.handle})
    return {'ok':not findings,'findings':findings,'linear_dimensions':dimensions,
            'native_display_verified':False,'scope':'Text mapping and linear dimension settings; inspect actual regenerated display and building clearance separately'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('drawing',type=Path)
    p.add_argument('--max-extension',type=float);p.add_argument('--min-gap',type=float)
    p.add_argument('--report',type=Path);args=p.parse_args()
    if args.report and args.report.resolve()==args.drawing.resolve():raise ValueError('Report cannot overwrite drawing')
    result=check(args.drawing,args.max_extension,args.min_gap)
    payload=json.dumps(result,ensure_ascii=False,indent=2)
    if args.report:args.report.write_text(payload,encoding='utf8')
    print(payload);sys.exit(0 if result['ok'] else 1)
