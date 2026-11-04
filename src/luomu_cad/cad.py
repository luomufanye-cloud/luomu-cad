"""Windows AutoCAD adapter, instantiated only inside the MCP server worker.

Uses documented ActiveX methods. Never launches CAD, sends raw commands,
changes the active tab or captures a desktop image.
"""
import math
import os
from .storage import ROOT, Journal, digest, workspace_lock


def vector(values):
    if not isinstance(values,(list,tuple)) or len(values) not in (2,3):
        raise ValueError("Coordinate requires 2 or 3 components")
    values=list(values)+([0.] if len(values)==2 else [])
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e9 for v in values):
        raise ValueError("Coordinates must be finite")
    return tuple(float(v) for v in values)


class CAD:
    def __init__(self,root=None,attach=None):
        self.app=None
        self.document=None
        self.bound_token=None
        self.attach=attach
        self.com_initialized=False
        self.root=root or ROOT/"runtime/live-operations"
        self.journal=Journal(self.root)

    def versions(self):
        if os.name!="nt":
            return {"ok":True,"versions":[],"platform":"non-Windows"}
        import winreg
        found=[]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,"") as key:
            index=0
            while True:
                try:
                    name=winreg.EnumKey(key,index)
                except OSError:
                    break
                index+=1
                if name=="AutoCAD.Application" or name.startswith("AutoCAD.Application."):
                    found.append(name)
        return {"ok":True,"versions":sorted(found),"running_not_implied":True}

    def application(self,progid="AutoCAD.Application"):
        if not (progid=="AutoCAD.Application" or (progid.startswith("AutoCAD.Application.") and all(p.isdigit() for p in progid.split('.')[2:]))):
            raise ValueError("Invalid AutoCAD ProgID")
        if self.attach:
            return self.attach(progid)
        if os.name!="nt":
            raise RuntimeError("CAD_UNAVAILABLE: live AutoCAD requires Windows")
        import pythoncom
        import win32com.client
        if not self.com_initialized:
            pythoncom.CoInitialize()
            self.com_initialized=True
        # GetActiveObject attaches only; it cannot launch the application.
        return win32com.client.GetActiveObject(progid)

    def identity(self,doc):
        return digest({"window":int(self.app.HWND),"document":str(doc.FullName or doc.Name)})

    def connect(self,document_name=None,progid="AutoCAD.Application"):
        self.app=self.application(progid)
        active=self.app.ActiveDocument
        if document_name and document_name not in {str(active.Name),str(active.FullName)}:
            raise ValueError("DOCUMENT_MISMATCH: requested drawing is not active; no tab switch attempted")
        self.document=active
        self.bound_token=self.identity(active)
        return {"ok":True,"connected":True,"document":str(active.Name),"path":str(active.FullName),"document_token":self.bound_token,
                "units":int(active.GetVariable("INSUNITS")),"commands":str(active.GetVariable("CMDNAMES")),"writes_enabled":os.environ.get("LUOMU_CAD_LIVE_WRITES")=="1"}

    def state(self,token=None,write=False):
        if self.document is None:
            raise RuntimeError("CAD_NOT_CONNECTED: call cad_connect")
        if self.identity(self.app.ActiveDocument)!=self.bound_token:
            raise ValueError("DOCUMENT_CHANGED: reconnect and read before continuing")
        if token is not None and token!=self.bound_token:
            raise ValueError("DOCUMENT_TOKEN_MISMATCH")
        if write:
            if os.environ.get("LUOMU_CAD_LIVE_WRITES")!="1":
                raise ValueError("LIVE_WRITES_DISABLED")
            if token!=self.bound_token:
                raise ValueError("Writes require the current document token")
            if self.document.GetVariable("CMDNAMES"):
                raise ValueError("CAD_BUSY: no command cancellation attempted")
        return self.document

    def list_documents(self,progid="AutoCAD.Application"):
        self.app=self.application(progid)
        return {"ok":True,"documents":[{"name":str(d.Name),"path":str(d.FullName)} for d in self.app.Documents]}

    def read(self,offset=0,limit=20,document_token=None):
        if isinstance(offset,bool) or not isinstance(offset,int) or offset<0 or not isinstance(limit,int) or not 1<=limit<=200:
            raise ValueError("offset>=0 and limit 1..200 required")
        doc=self.state(document_token)
        model=doc.ModelSpace
        result=[]
        for i in range(offset,min(model.Count,offset+limit)):
            entity=model.Item(i)
            item={"handle":str(entity.Handle),"type":str(entity.ObjectName),"layer":str(entity.Layer)}
            for key in ("StartPoint","EndPoint","Center","InsertionPoint","Coordinates","Radius","TextString","Measurement","Closed"):
                try:
                    value=getattr(entity,key)
                    if isinstance(value,(tuple,list)):
                        value=list(value)
                    if isinstance(value,(list,str,int,float,bool)):
                        item[key]=value
                except Exception:
                    pass
            result.append(item)
        return {"ok":True,"document_token":self.bound_token,"entities":result,"total":model.Count,"next_offset":offset+len(result) if offset+len(result)<model.Count else None}

    def mutate(self,operation_id,document_token,operation,arguments):
        # Validation precedes journal start. A started but uncommitted call is never replayed.
        doc=self.state(document_token,write=True)
        allowed={"line","circle","polyline","text","dimension","properties","save"}
        if operation not in allowed:
            raise ValueError("Unsupported live operation")
        fields={"line":{"start","end","layer"},"circle":{"center","radius","layer"},"polyline":{"points","closed","layer"},"text":{"at","text","height","layer"},"dimension":{"start","end","at","layer"},"properties":{"handle","changes"},"save":set()}
        if set(arguments)-fields[operation]:raise ValueError("Unexpected operation arguments")
        for key in ("start","end","center","at"):
            if key in arguments:vector(arguments[key])
        for key in ("radius","height"):
            if key in arguments and (isinstance(arguments[key],bool) or not isinstance(arguments[key],(int,float)) or not math.isfinite(arguments[key]) or arguments[key]<=0):
                raise ValueError("Positive finite radius/height required")
        required={"line":{"start","end"},"circle":{"center","radius"},"polyline":{"points"},"text":{"at","text","height"},"dimension":{"start","end","at"},"properties":{"handle","changes"},"save":set()}
        if required[operation]-arguments.keys():raise ValueError("Missing operation arguments")
        if operation in {"line","dimension"} and vector(arguments["start"])==vector(arguments["end"]):
            raise ValueError("Zero length line")
        if operation=="polyline":
            if not isinstance(arguments["points"],list) or not 2<=len(arguments["points"])<=1000:raise ValueError("Polyline requires 2..1000 points")
            if any(vector(pt)[2]!=0 for pt in arguments["points"]):raise ValueError("Only XY polylines supported")
        if operation=="properties":
            changes=arguments["changes"]
            if not isinstance(changes,dict) or not changes or changes.keys()-{"layer","text","height","color"}:raise ValueError("Invalid property changes")
            if "height" in changes and (not isinstance(changes["height"],(int,float)) or isinstance(changes["height"],bool) or not math.isfinite(changes["height"]) or changes["height"]<=0):raise ValueError("Positive finite height required")
            if "color" in changes and (isinstance(changes["color"],bool) or not isinstance(changes["color"],int) or not 0<=changes["color"]<=256):raise ValueError("Invalid color")
            doc.HandleToObject(str(arguments["handle"]))
        layer=arguments.get("layer") or arguments.get("changes",{}).get("layer")
        if layer:
            doc.Layers.Item(str(layer))  # Verify existing layer before any mutation.
        if operation=="save" and not doc.FullName:raise ValueError("Automatic SaveAs disabled")
        with workspace_lock(self.root):
            fresh,old=self.journal.begin(operation_id,{"document":document_token,"operation":operation,"arguments":arguments})
            if not fresh:
                if old.get("handle"):
                    entity=doc.HandleToObject(old["handle"])
                    if str(entity.Handle)!=old["handle"]:
                        raise RuntimeError("READBACK_FAILED")
                return {**old,"replayed":True}
            import pythoncom
            import win32com.client
            def variant(values):
                return win32com.client.VARIANT(pythoncom.VT_ARRAY|pythoncom.VT_R8,values)
            def p(value):
                return variant(vector(value))
            model=doc.ModelSpace
            entity=None
            if operation=="line":
                entity=model.AddLine(p(arguments["start"]),p(arguments["end"]))
            elif operation=="circle":
                radius=float(arguments["radius"])
                if not math.isfinite(radius) or radius<=0:
                    raise ValueError("Positive finite radius required")
                entity=model.AddCircle(p(arguments["center"]),radius)
            elif operation=="polyline":
                points=[vector(v) for v in arguments["points"]]
                if not 2<=len(points)<=1000 or any(v[2]!=0 for v in points):
                    raise ValueError("Polyline requires 2..1000 XY points")
                entity=model.AddLightWeightPolyline(variant([v for pt in points for v in pt[:2]]))
                entity.Closed=bool(arguments.get("closed",False))
            elif operation=="text":
                height=float(arguments["height"])
                if not math.isfinite(height) or height<=0:
                    raise ValueError("Positive text height required")
                entity=model.AddText(str(arguments["text"]),p(arguments["at"]),height)
            elif operation=="dimension":
                entity=model.AddDimAligned(p(arguments["start"]),p(arguments["end"]),p(arguments["at"]))
            elif operation=="properties":
                changes=arguments["changes"]
                mapping={"layer":"Layer","text":"TextString","height":"Height","color":"Color"}
                if not changes or set(changes)-mapping.keys():
                    raise ValueError("Only layer/text/height/color changes supported")
                entity=doc.HandleToObject(str(arguments["handle"]))
                for key,value in changes.items():
                    setattr(entity,mapping[key],value)
            elif operation=="save":
                if not doc.FullName:
                    raise ValueError("Unsaved drawing: automatic SaveAs disabled")
                doc.Save()
            result={"ok":True,"operation_id":operation_id,"operation":operation,"document_token":document_token,"handle":str(entity.Handle) if entity is not None else None}
            if entity is not None:
                if operation!="properties" and arguments.get("layer"):entity.Layer=str(arguments["layer"])
                readback=doc.HandleToObject(entity.Handle)
                result["entity_type"]=str(readback.ObjectName)
            self.journal.set(operation_id,{"status":"completed","result":result})
            return result
