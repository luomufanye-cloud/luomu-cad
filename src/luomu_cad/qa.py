"""Read saved DXF geometry independently; never infer acceptance from file size."""
from __future__ import annotations

import hashlib
import math
from collections import Counter
from pathlib import Path

import ezdxf
from shapely.geometry import LineString


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshots(path):
    from ezdxf.lldxf.tagwriter import TagCollector
    doc = ezdxf.readfile(path)
    return {e.dxf.handle: hashlib.sha256(str(TagCollector.dxftags(e)).encode()).hexdigest()
            for e in doc.modelspace()}


def audit_dxf(path, required_layers=None):
    doc = ezdxf.readfile(path)
    auditor = doc.audit()
    findings = []
    dimensions = []
    unsupported = Counter()
    counts = Counter()
    for layout in doc.layouts:
        seen = {}
        for e in layout:
            typ, handle = e.dxftype(), e.dxf.handle
            counts[typ] += 1
            if typ == "LINE":
                a = tuple(round(float(v), 6) for v in e.dxf.start)
                b = tuple(round(float(v), 6) for v in e.dxf.end)
                if not all(math.isfinite(v) for v in (*a, *b)):
                    findings.append({"kind": "nonfinite", "handle": handle})
                elif math.dist(a, b) < 1e-6:
                    findings.append({"kind": "zero_length", "handle": handle})
                signature = (typ, e.dxf.layer, tuple(sorted((a, b))))
                if signature in seen:
                    findings.append({"kind": "duplicate_line", "handles": [seen[signature], handle], "layout": layout.name})
                seen[signature] = handle
            elif typ == "LWPOLYLINE":
                points = list(e.get_points("xy"))
                if any(abs(p[4]) > 1e-9 for p in e.get_points("xyseb")):
                    unsupported["curved_polyline_intersection"] += 1
                elif len(points) >= 2:
                    if e.closed:
                        points.append(points[0])
                    if not LineString(points).is_simple:
                        findings.append({"kind": "self_intersection", "handle": handle})
            elif typ == "DIMENSION":
                measured = e.get_measurement()
                row = {"handle": handle, "measurement": list(measured) if hasattr(measured, "x") else measured,
                       "text_override": e.dxf.get("text", "")}
                override = row["text_override"].strip()
                if override not in {"", "<>", " "}:
                    try:
                        value = float(override)
                        if isinstance(measured, (int, float)) and abs(value - measured) > 0.01:
                            findings.append({"kind": "dimension_override_mismatch", **row})
                    except ValueError:
                        unsupported["formatted_dimension_override"] += 1
                dimensions.append(row)
            elif typ not in {"TEXT", "MTEXT", "ARC", "CIRCLE", "HATCH", "INSERT", "ACAD_TABLE", "TABLE"}:
                unsupported[typ] += 1
    layers = {l.dxf.name for l in doc.layers}
    for name in required_layers or []:
        if name not in layers:
            findings.append({"kind": "missing_layer", "layer": name})
    if int(doc.header.get("$INSUNITS", 0)) != 4:
        findings.append({"kind": "units_not_mm", "actual": doc.header.get("$INSUNITS", 0)})
    findings.extend({"kind": "dxf_structural_error", "message": str(e)} for e in auditor.errors)
    # Repairs by ezdxf.audit are evidence of an issue in the saved input too.
    findings.extend({"kind": "dxf_repair_required", "message": str(e)} for e in auditor.fixes)
    return {"ok": not findings, "checks_status": "PASS" if not findings else "FAIL",
            "file": str(Path(path).resolve()), "sha256": file_hash(path), "entities": dict(counts),
            "findings": findings, "dimensions": dimensions, "not_evaluated": dict(unsupported),
            "scope": "Saved DXF: structure, units, zero/duplicate lines, straight polyline intersections, numeric dimension overrides; not full design acceptance"}


def prepare_chinese_font(path):
    """Use a real Windows Chinese TTF when available; does not change geometry."""
    doc = ezdxf.readfile(path)
    doc.header["$INSUNITS"] = 4  # Generated plan inputs explicitly use WCS mm.
    candidates = [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simsun.ttc")]
    font = next((p for p in candidates if p.exists()), None)
    if font is None:
        return {"available": False, "visual_acceptance": "pending"}
    for style in doc.styles:
        style.dxf.font = str(font)
        style.dxf.bigfont = ""
    doc.saveas(path)
    return {"available": True, "font": font.name}


def render_dxf(path, output):
    import matplotlib
    matplotlib.use("Agg")
    from ezdxf.addons.drawing import matplotlib as drawing_mpl
    # Render directly from the saved DXF; no desktop/window capture.
    drawing_mpl.qsave(ezdxf.readfile(path).modelspace(), str(output), dpi=180,
                      bg="#ffffff", fg="#171717")
    return {"path": str(Path(output).resolve()), "sha256": file_hash(output),
            "method": "offline DXF geometry rendering"}
