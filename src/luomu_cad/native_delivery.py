"""Bounded native DWG facts, collected only by the CAD MCP STA worker.

No export/reconstruction as DXF is used here. The supported scope is top-level
XY primitives and ordinary aligned/rotated dimensions; unsupported facts fail.
The internal context prevents a JSON receipt from becoming a live-MCP channel,
but is not a security authentication mechanism against arbitrary Python code.
"""
from __future__ import annotations

from collections import Counter
import math
import os
import re
from pathlib import Path

from .storage import digest


INTERFACES = {'AcDbLine':'IAcadLine','AcDbArc':'IAcadArc','AcDbCircle':'IAcadCircle',
    'AcDbPolyline':'IAcadLWPolyline','AcDbEllipse':'IAcadEllipse','AcDbText':'IAcadText',
    'AcDbMText':'IAcadMText','AcDbAlignedDimension':'IAcadDimAligned',
    'AcDbRotatedDimension':'IAcadDimRotated'}
DIMENSIONS = {'AcDbAlignedDimension','AcDbRotatedDimension'}


def resolve_font_file(value):
    """Resolve an actual absolute file or its installed Windows font basename."""
    path=Path(value)
    if path.is_absolute() and path.is_file():return path.resolve()
    if len(path.parts)!=1:raise ValueError('Native/source font path cannot be resolved')
    installed=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/path.name
    if not installed.is_file():raise ValueError('Native/source installed font file missing: '+path.name)
    return installed.resolve()


def same_font_family(font_file,left,right):
    """Accept localized family aliases only if they occur on the same real face."""
    if not isinstance(left,str) or not isinstance(right,str) or not left or not right:return False
    if left.casefold()==right.casefold():return True
    from fontTools.ttLib import TTFont,TTCollection
    font_file=Path(font_file)
    collection=None;face=None
    try:
        if font_file.suffix.casefold()=='.ttc':
            collection=TTCollection(font_file,lazy=True);faces=collection.fonts
        else:face=TTFont(font_file,lazy=True);faces=[face]
        for current in faces:
            names=set()
            for name in current['name'].names:
                if name.nameID in {1,16}:
                    try:names.add(name.toUnicode().casefold())
                    except (UnicodeError,LookupError):continue
            if {left.casefold(),right.casefold()}<=names:return True
        return False
    finally:
        if collection is not None:collection.close()
        elif face is not None:face.close()


def font_faces(font_file):
    from fontTools.ttLib import TTFont,TTCollection
    collection=None;face=None
    try:
        if Path(font_file).suffix.casefold()=='.ttc':collection=TTCollection(font_file,lazy=True);faces=collection.fonts
        else:face=TTFont(font_file,lazy=True);faces=[face]
        result=[]
        for index,current in enumerate(faces):
            families=set();logical=set()
            for name in current['name'].names:
                if name.nameID not in {1,4,6,16}:continue
                try:value=name.toUnicode()
                except (UnicodeError,LookupError):continue
                if name.nameID in {1,16}:families.add(value.casefold())
                logical.add(value.casefold())
            result.append({'index':index,'families':families,'logical_names':logical})
        return result
    finally:
        if collection is not None:collection.close()
        elif face is not None:face.close()


def registered_fonts():
    """Read installed Windows mappings, never install or alter fonts."""
    if os.name!='nt':raise ValueError('Windows registration proof required for a native logical font alias')
    import winreg
    result=[];directory=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
    for hive in (winreg.HKEY_LOCAL_MACHINE,winreg.HKEY_CURRENT_USER):
        try:key=winreg.OpenKey(hive,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts')
        except FileNotFoundError:continue
        with key:
            index=0
            while True:
                try:label,value,kind=winreg.EnumValue(key,index)
                except OSError as error:
                    if getattr(error,'winerror',None)==259:break
                    raise
                index+=1
                if kind not in {winreg.REG_SZ,winreg.REG_EXPAND_SZ} or not isinstance(value,str):continue
                path=Path(os.path.expandvars(value));path=path if path.is_absolute() else directory/path
                result.append((label,path.resolve()))
    return result


def verify_font_resource(actual_file,actual_family,source_file,source_family):
    """Bind a physical font or a native canonical TTF alias to one real face.

    A missing logical filename is accepted only through a unique installed
    Windows mapping plus actual family/PostScript names on the same TTC face.
    Existing actual files are always hashed; aliases cannot hide other bytes.
    """
    from .qa import file_hash
    source=resolve_font_file(source_file)
    if not isinstance(actual_family,str) or not actual_family or not source_family:
        raise ValueError('Explicit actual/source family required for native font-face proof')
    selected=[face for face in font_faces(source)
        if {actual_family.casefold(),source_family.casefold()}<=face['families']]
    if len(selected)!=1:raise ValueError('Native/source families do not identify one physical font face')
    chosen=selected[0];declared=Path(actual_file)
    try:physical=resolve_font_file(actual_file)
    except ValueError:physical=None
    if physical is not None:
        if file_hash(physical)!=file_hash(source):raise ValueError('Existing actual/source font file bytes differ')
        return {'mode':'physical_font_file','physical_path':str(physical),'file_sha256':file_hash(physical),'face_index':chosen['index']}
    directory=(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts').resolve()
    if (declared.suffix.casefold()!='.ttf' or (declared.is_absolute() and declared.parent.resolve()!=directory)
            or (not declared.is_absolute() and len(declared.parts)!=1)
            or declared.stem.casefold() not in chosen['logical_names']):
        raise ValueError('Missing native filename is not a verified logical face alias')
    matches={}
    for label,path in registered_fonts():
        label=re.sub(r'\s*\((?:TrueType|OpenType)\)\s*$','',label,flags=re.I)
        names={part.strip().casefold() for part in label.split('&')}
        if not names & chosen['families']:continue
        if not path.is_file():raise ValueError('Matching Windows font registration points to a missing file')
        for face in font_faces(path):
            if ({actual_family.casefold(),source_family.casefold()}<=face['families']
                    and declared.stem.casefold() in face['logical_names']):
                matches[(str(path).casefold(),face['index'])]=(path,face['index'])
    if len(matches)!=1:raise ValueError('Native logical font alias has no unique Windows registered face mapping')
    physical,index=next(iter(matches.values()))
    if file_hash(physical)!=file_hash(source) or index!=chosen['index']:
        raise ValueError('Windows registered native font face differs from the original physical source')
    return {'mode':'unique_windows_registered_logical_face','native_declared_file':actual_file,
        'physical_path':str(physical),'file_sha256':file_hash(physical),'face_index':index,
        'native_family':actual_family,'source_family':source_family}


def typed_entity(entity,retry):
    """Query the specific ActiveX interface instead of silently using IAcadEntity."""
    name=retry(lambda:str(entity.ObjectName))
    if name not in INTERFACES:
        raise ValueError('NATIVE_ENTITY_UNSUPPORTED: '+name)
    if not hasattr(entity,'_oleobj_'):
        return entity  # protocol-only fake objects in unit tests, never native evidence
    import win32com.client
    try:
        return retry(lambda:win32com.client.CastTo(entity,INTERFACES[name]))
    except Exception as error:
        raise ValueError('NATIVE_INTERFACE_REQUIRED: '+name+': '+str(error)) from error


def _value(obj,name,retry):
    try:value=retry(lambda:getattr(obj,name),timeout=3)
    except Exception as error:
        # Generated type libraries can omit deprecated but live-supported
        # properties such as Layer.Color. Query actual IDispatch, never invent
        # a fallback value from a different property or from a source DXF.
        if isinstance(error,AttributeError) and hasattr(obj,'_oleobj_'):
            try:
                import pythoncom
                ole=obj._oleobj_
                value=retry(lambda:ole.Invoke(ole.GetIDsOfNames(name),0,pythoncom.DISPATCH_PROPERTYGET,1),timeout=3)
            except Exception as native_error:
                raise ValueError('NATIVE_PROPERTY_REQUIRED: '+str(name)+': '+str(native_error)) from native_error
        else:raise ValueError('NATIVE_PROPERTY_REQUIRED: '+str(name)+': '+str(error)) from error
    if isinstance(value,tuple):value=list(value)
    if value is None or not isinstance(value,(str,int,float,bool,list)):
        raise ValueError('NATIVE_PROPERTY_INVALID: '+name)
    if isinstance(value,float) and not math.isfinite(value):
        raise ValueError('NATIVE_PROPERTY_NONFINITE: '+name)
    return value


def _number(value,name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('NATIVE_FINITE_NUMBER_REQUIRED: '+name)
    return float(value)


def _point(value,name):
    if not isinstance(value,(list,tuple)) or len(value)!=3:
        raise ValueError('NATIVE_POINT_REQUIRED: '+name)
    point=[_number(v,name) for v in value]
    if abs(point[2])>1e-8:
        raise ValueError('NATIVE_XY_SCOPE_REQUIRED: '+name)
    return point


def _normal(value):
    if not isinstance(value,list) or len(value)!=3 or any(abs(float(a)-b)>1e-8 for a,b in zip(value,[0,0,1])):
        raise ValueError('NATIVE_NORMAL_UNSUPPORTED: only positive WCS XY objects are supported')
    return value


def parse_entity_data(source):
    """Parse the fixed bridge's Lisp data, never evaluate supplied code."""
    tokens=re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',source)
    index=0
    def value():
        nonlocal index
        if index>=len(tokens):raise ValueError('Truncated native entity data')
        token=tokens[index];index+=1
        if token=='(':
            result=[]
            while index<len(tokens) and tokens[index]!=')':result.append(value())
            if index>=len(tokens):raise ValueError('Unclosed native entity data')
            index+=1;return result
        if token==')':raise ValueError('Unexpected native entity data close')
        if token.startswith('"'):
            text=re.sub(r'\\([\\"])',r'\1',token[1:-1])
            return _number(float(text[6:]),'native real serialization') if text.startswith('~REAL~') else text
        if token=='.':return token
        try:return int(token)
        except ValueError:
            try:return _number(float(token),'entity data')
            except ValueError:raise ValueError('Unsupported native entity data atom') from None
    groups=value()
    if index!=len(tokens) or not isinstance(groups,list):raise ValueError('Malformed native entity data')
    result=[]
    for row in groups:
        if not isinstance(row,list) or len(row)<2 or type(row[0]) is not int:raise ValueError('Invalid native entity group')
        result.append((row[0],row[2] if len(row)==3 and row[1]=='.' else row[1:]))
    return result


def capture(document,retry,max_entities=20000,entity_data=None):
    """Read all supported native model facts and cached dimension display texts."""
    if type(max_entities) is not int or not 1<=max_entities<=100000:
        raise ValueError('Native entity budget must be 1..100000')
    variables={name:retry(lambda name=name:document.GetVariable(name),timeout=3)
               for name in ('INSUNITS','DBMOD','CMDNAMES','LWDISPLAY','LWDEFAULT','LTSCALE','PSLTSCALE','PSTYLEMODE')}
    layers=[]
    table=retry(lambda:document.Layers)
    for index in range(retry(lambda:int(table.Count))):
        layer=retry(lambda index=index:table.Item(index))
        record={key:_value(layer,key,retry) for key in ('Name','Lineweight','Linetype','Color','LayerOn','Freeze','Plottable')}
        if entity_data is not None:
            record['definition_groups']=parse_entity_data(entity_data(_value(layer,'Handle',retry)))
            if [value for code,value in record['definition_groups'] if code==0]!=['LAYER']:
                raise ValueError('NATIVE_LAYER_DEFINITION_IDENTITY_REQUIRED')
            if any(code==420 for code,_ in record['definition_groups']):
                raise ValueError('Native true-color layers require a dedicated native paper adapter')
            try:transparency=retry(lambda:layer.GetXData('AcCmTransparency'),timeout=3)
            except Exception as error:raise ValueError('NATIVE_LAYER_TRANSPARENCY_READ_REQUIRED: '+str(error)) from error
            if not isinstance(transparency,tuple) or len(transparency)!=2:raise ValueError('Native layer transparency XData unreadable')
            record['transparency_xdata']=[list(v) if isinstance(v,tuple) else v for v in transparency]
            values=transparency[1]
            if values and (not isinstance(values,(tuple,list)) or values[-1]!=0x020000ff):
                raise ValueError('Native nonopaque layer requires a dedicated native paper adapter')
        layers.append(record)
    layer_map={row['Name']:row for row in layers}
    if len(layer_map)!=len(layers):raise ValueError('NATIVE_LAYER_IDENTITY_DUPLICATE')
    text_styles={}

    def font(name):
        if name not in text_styles:
            style=retry(lambda:document.TextStyles.Item(name))
            text_styles[name]={key:_value(style,key,retry) for key in ('Name','FontFile','BigFontFile','Height','Width','ObliqueAngle','TextGenerationFlag')}
            try:details=retry(lambda:style.GetFont(),timeout=3)
            except Exception as error:raise ValueError('NATIVE_FONT_FAMILY_AND_FLAGS_READ_REQUIRED: '+str(error)) from error
            if not isinstance(details,tuple) or len(details)!=5:
                raise ValueError('Native GetFont must return actual Typeface/Bold/Italic/CharSet/PitchAndFamily')
            text_styles[name]['font_details']=dict(zip(('typeface','bold','italic','charset','pitch_and_family'),details))
            try:font_data=retry(lambda:style.GetXData('ACAD'),timeout=3)
            except Exception as error:raise ValueError('NATIVE_FONT_XDATA_READ_REQUIRED: '+str(error)) from error
            if not isinstance(font_data,tuple) or len(font_data)!=2:raise ValueError('Native font ACAD XData unreadable')
            text_styles[name]['font_xdata']=[list(v) if isinstance(v,tuple) else v for v in font_data]
        return text_styles[name]

    def common(entity):
        row={key:_value(entity,key,retry) for key in ('Handle','ObjectName','Layer','Lineweight','Linetype','LinetypeScale','Visible','Color')}
        if row['Layer'] not in layer_map:raise ValueError('NATIVE_LAYER_MISSING: '+row['Layer'])
        layer=layer_map[row['Layer']]
        weight=row['Lineweight']
        if weight==-1:weight=layer['Lineweight']
        if weight==-3:weight=variables['LWDEFAULT']
        if isinstance(weight,bool) or not isinstance(weight,int) or weight<0:
            raise ValueError('NATIVE_LINEWEIGHT_UNRESOLVED: '+row['Handle'])
        row['effective_lineweight_mm']=weight/100
        row['effective_linetype']=layer['Linetype'] if row['Linetype'].casefold()=='bylayer' else row['Linetype']
        if row['effective_linetype'].casefold() in {'bylayer','byblock'}:
            raise ValueError('NATIVE_LINETYPE_UNRESOLVED: '+row['Handle'])
        _number(row['LinetypeScale'],'LinetypeScale')
        return row

    model=retry(lambda:document.ModelSpace)
    count=retry(lambda:int(model.Count))
    if not 1<=count<=max_entities:raise ValueError('Native model requires 1..max_entities objects')
    rows=[];seen=set()
    for index in range(count):
        entity=typed_entity(retry(lambda index=index:model.Item(index)),retry)
        row=common(entity);name=row['ObjectName']
        if entity_data is not None:
            row['native_entity_groups']=parse_entity_data(entity_data(row['Handle']))
        if row['Handle'] in seen:raise ValueError('NATIVE_DUPLICATE_HANDLE')
        seen.add(row['Handle'])
        get=lambda key:_value(entity,key,retry)
        if name=='AcDbLine':
            row.update(StartPoint=_point(get('StartPoint'),'StartPoint'),EndPoint=_point(get('EndPoint'),'EndPoint'))
            if math.dist(row['StartPoint'],row['EndPoint'])<1e-9:raise ValueError('NATIVE_ZERO_LENGTH_LINE')
            row['Length']=_number(get('Length'),'Length')
        elif name in {'AcDbCircle','AcDbArc'}:
            row.update(Center=_point(get('Center'),'Center'),Radius=_number(get('Radius'),'Radius'),Normal=_normal(get('Normal')))
            if row['Radius']<=0:raise ValueError('NATIVE_RADIUS_REQUIRED')
            if name=='AcDbArc':
                row.update(StartAngle=_number(get('StartAngle'),'StartAngle'),EndAngle=_number(get('EndAngle'),'EndAngle'),ArcLength=_number(get('ArcLength'),'ArcLength'))
        elif name=='AcDbEllipse':
            row.update(Center=_point(get('Center'),'Center'),MajorAxis=_point(get('MajorAxis'),'MajorAxis'),
                MinorAxis=_point(get('MinorAxis'),'MinorAxis'),RadiusRatio=_number(get('RadiusRatio'),'RadiusRatio'),
                StartParameter=_number(get('StartParameter'),'StartParameter'),EndParameter=_number(get('EndParameter'),'EndParameter'),Normal=_normal(get('Normal')))
            if not 0<row['RadiusRatio']<=1:raise ValueError('NATIVE_ELLIPSE_RATIO_INVALID')
        elif name=='AcDbPolyline':
            coordinates=get('Coordinates')
            if not isinstance(coordinates,list) or len(coordinates)<4 or len(coordinates)%2:
                raise ValueError('NATIVE_POLYLINE_COORDINATES_REQUIRED')
            coordinates=[_number(v,'Coordinates') for v in coordinates]
            if abs(_number(get('Elevation'),'Elevation'))>1e-8:raise ValueError('NATIVE_XY_SCOPE_REQUIRED')
            row.update(Coordinates=coordinates,Closed=get('Closed'),Normal=_normal(get('Normal')),
                ConstantWidth=_number(get('ConstantWidth'),'ConstantWidth'),Length=_number(get('Length'),'Length'),Area=_number(get('Area'),'Area'),Bulges=[],VertexWidths=[])
            for vertex in range(len(coordinates)//2):
                row['Bulges'].append(_number(retry(lambda vertex=vertex:entity.GetBulge(vertex),timeout=3),'Bulge'))
                widths=retry(lambda vertex=vertex:entity.GetWidth(vertex),timeout=3)
                if len(widths)!=2:raise ValueError('NATIVE_VERTEX_WIDTH_REQUIRED')
                row['VertexWidths'].append([_number(value,'VertexWidth') for value in widths])
        elif name in {'AcDbText','AcDbMText'}:
            row.update(TextString=get('TextString'),InsertionPoint=_point(get('InsertionPoint'),'InsertionPoint'),
                Height=_number(get('Height'),'Height'),StyleName=get('StyleName'))
            font(row['StyleName'])
            if name=='AcDbText':row.update(Rotation=_number(get('Rotation'),'Rotation'),ScaleFactor=_number(get('ScaleFactor'),'ScaleFactor'))
            else:row.update(Width=_number(get('Width'),'Width'),AttachmentPoint=get('AttachmentPoint'))
        elif name in DIMENSIONS:
            keys=('TextOverride','TextPosition','LinearScaleFactor','PrimaryUnitsPrecision','DecimalSeparator',
                  'UnitsFormat','TextPrefix','TextSuffix','ToleranceDisplay','AltUnits','RoundDistance','Rotation',
                  'TextHeight','TextStyle','ScaleFactor','DimensionLineWeight','ExtensionLineWeight')
            row.update({key:get(key) for key in keys})
            try:row['activex_measurement']=_number(get('Measurement'),'Measurement')
            except Exception as error:
                if entity_data is None:raise
                cached=[v for k,v in row['native_entity_groups'] if k==42]
                cause=error;missing_cache_error=False
                while cause is not None:
                    info=getattr(cause,'excepinfo',None)
                    if isinstance(info,(list,tuple)) and len(info)>5 and isinstance(info[5],int) and info[5]&0xffffffff==0x8020002b:
                        missing_cache_error=True
                    # Protocol fixtures have no COM object. This branch never
                    # relaxes an actual native API boolean/NaN/None result.
                    if not hasattr(entity,'_oleobj_') and isinstance(cause,AttributeError):missing_cache_error=True
                    cause=cause.__cause__
                if not missing_cache_error or (cached and cached!=[-1.0]):
                    raise ValueError('NATIVE_MEASUREMENT_PROPERTY_INVALID: only the documented missing optional cache can use native definition measurement') from error
                row['activex_measurement_error']=str(error)
            if entity_data is not None:
                groups=row['native_entity_groups']
                def group(code,default=None):
                    found=[value for key,value in groups if key==code]
                    if len(found)>1:raise ValueError('NATIVE_DIMENSION_DUPLICATE_GROUP')
                    return found[0] if found else default
                if group(0)!='DIMENSION' or group(5).casefold()!=row['Handle'].casefold():raise ValueError('NATIVE_ENTITY_DATA_IDENTITY_MISMATCH')
                if group(70)&7 not in {0,1}:raise ValueError('NATIVE_DIMENSION_DEFINITION_UNSUPPORTED')
                first=_point(group(13),'native dimension definition 13');second=_point(group(14),'native dimension definition 14')
                angle=_number(group(50,0.),'native dimension definition 50')
                row.update(ExtLine1Point=first,ExtLine2Point=second,native_geometry_block=group(2),
                    native_definition_groups=groups,extension_origins_available=True)
                row['Measurement']=(math.dist(first,second) if group(70)&7==1 else
                    abs((second[0]-first[0])*math.cos(angle)+(second[1]-first[1])*math.sin(angle)))
                row['measurement_source']='actual_native_definition'
                if 'activex_measurement' in row and abs(row['activex_measurement']-row['Measurement'])>1e-6:
                    raise ValueError('NATIVE_DIMENSION_CACHE_MEASUREMENT_MISMATCH')
            else:
                row['Measurement']=row['activex_measurement'];row['measurement_source']='actual_activex_measurement'
            row['TextPosition']=_point(row['TextPosition'],'TextPosition')
            if row['TextOverride'] not in {'','<>'} or row['LinearScaleFactor']!=1 or row['ToleranceDisplay']!=0 or row['AltUnits'] or row['RoundDistance']!=0:
                raise ValueError('NATIVE_DIMENSION_OVERRIDE_OR_FORMAT_UNSUPPORTED: '+row['Handle'])
            if row['UnitsFormat']!=2 or row['TextPrefix'] or row['TextSuffix']:
                raise ValueError('NATIVE_DIMENSION_UNIT_ADAPTER_REQUIRED: '+row['Handle'])
            font(row['TextStyle'])
            if name=='AcDbAlignedDimension':
                row.update(ExtLine1Point=_point(get('ExtLine1Point'),'ExtLine1Point'),ExtLine2Point=_point(get('ExtLine2Point'),'ExtLine2Point'))
            elif entity_data is None:
                # ActiveX DimRotated exposes native Measurement/Rotation but not
                # the two extension origins. Never fabricate them from a DXF.
                row['extension_origins_available']=False
        rows.append(row)
    if retry(lambda:int(model.Count))!=count:raise ValueError('NATIVE_INVENTORY_CHANGED_DURING_READ')

    # Match ordinary dimension display at its exact native TextPosition. More
    # than one possible cached display is rejected rather than guessed by order.
    display=[];blocks=retry(lambda:document.Blocks)
    for index in range(retry(lambda:int(blocks.Count))):
        block=retry(lambda index=index:blocks.Item(index));name=_value(block,'Name',retry)
        if not name.upper().startswith('*D'):continue
        if _value(block,'IsXRef',retry):raise ValueError('NATIVE_DIMENSION_XREF_UNSUPPORTED')
        origin=_point(_value(block,'Origin',retry),'dimension block origin')
        for j in range(retry(lambda:int(block.Count))):
            child=retry(lambda j=j:block.Item(j));kind=_value(child,'ObjectName',retry)
            if kind not in {'AcDbText','AcDbMText'}:continue
            child=typed_entity(child,retry)
            point=_point(_value(child,'InsertionPoint',retry),'dimension text insertion')
            point=[a+b for a,b in zip(origin,point)]
            if kind=='AcDbMText' and _value(child,'AttachmentPoint',retry)!=5:
                raise ValueError('NATIVE_DIMENSION_TEXT_ATTACHMENT_UNSUPPORTED')
            display.append({'block':name,'handle':_value(child,'Handle',retry),'text':_value(child,'TextString',retry),
                'position':point,'style':_value(child,'StyleName',retry),'kind':kind})
            font(display[-1]['style'])
    used=set()
    from ezdxf.tools.text import plain_mtext,plain_text
    for row in rows:
        if row['ObjectName'] not in DIMENSIONS:continue
        candidates=[item for item in display if math.dist(item['position'],row['TextPosition'])<=1e-6
            and (not row.get('native_geometry_block') or item['block']==row['native_geometry_block'])]
        if len(candidates)!=1:raise ValueError('NATIVE_DIMENSION_DISPLAY_NOT_UNIQUE: '+row['Handle'])
        item=candidates[0]
        if item['handle'] in used:raise ValueError('NATIVE_DIMENSION_DISPLAY_SHARED')
        used.add(item['handle'])
        shown=plain_mtext(item['text']).strip() if item['kind']=='AcDbMText' else plain_text(item['text']).strip()
        separator=row['DecimalSeparator'];separator=chr(separator) if isinstance(separator,int) else separator
        if separator not in {'.',','}:raise ValueError('NATIVE_DIMENSION_DECIMAL_SEPARATOR_UNSUPPORTED')
        try:number=float(shown.replace(separator,'.'))
        except (ValueError,TypeError):raise ValueError('NATIVE_DIMENSION_DISPLAY_NUMBER_REQUIRED') from None
        precision=row['PrimaryUnitsPrecision']
        if type(precision) is not int or not 0<=precision<=8:raise ValueError('NATIVE_DIMENSION_PRECISION_UNSUPPORTED')
        if not math.isfinite(number) or abs(number-row['Measurement'])>10**(-precision)/2+1e-7:
            raise ValueError('NATIVE_DIMENSION_DISPLAY_MISMATCH: '+row['Handle'])
        row['native_display']={**item,'plain':shown,'value':number}
    if len(used)!=len(display):raise ValueError('NATIVE_UNMAPPED_DIMENSION_DISPLAY')
    native_blocks={};nested_count=0
    def block_facts(name,stack=()):
        nonlocal nested_count
        if name in stack or len(stack)>12:raise ValueError('NATIVE_DIMENSION_BLOCK_CYCLE_OR_DEPTH')
        if name in native_blocks:return
        block=retry(lambda:blocks.Item(name))
        if _value(block,'IsXRef',retry):raise ValueError('NATIVE_DIMENSION_BLOCK_XREF')
        items=[]
        native_blocks[name]={'origin':_point(_value(block,'Origin',retry),'block origin'),'entities':items}
        for index in range(retry(lambda:int(block.Count))):
            nested_count+=1
            if count+nested_count>max_entities:raise ValueError('NATIVE_TOTAL_MODEL_AND_DISPLAY_ENTITY_BUDGET_EXCEEDED')
            child=retry(lambda index=index:block.Item(index));handle=_value(child,'Handle',retry)
            groups=parse_entity_data(entity_data(handle))
            item={'handle':handle,'groups':groups};items.append(item)
            kinds=[value for code,value in groups if code==0]
            if len(kinds)!=1 or kinds[0] not in {'LINE','ARC','CIRCLE','ELLIPSE','TEXT','MTEXT','POINT','SOLID','INSERT'}:
                raise ValueError('NATIVE_DIMENSION_BLOCK_ENTITY_UNSUPPORTED')
            if kinds[0]=='INSERT':
                names=[value for code,value in groups if code==2]
                if len(names)!=1:raise ValueError('NATIVE_DIMENSION_BLOCK_REFERENCE_REQUIRED')
                block_facts(names[0],(*stack,name))
    if entity_data is not None:
        for row in rows:
            if row['ObjectName'] in DIMENSIONS:block_facts(row['native_geometry_block'])
    return {'scope':'top-level positive-WCS-XY primitives and ordinary decimal aligned/rotated dimensions',
        'variables':variables,'layers':layers,'text_styles':text_styles,'model':rows,
        'dimension_blocks':native_blocks,
        'modelspace_count':count,'entity_counts':dict(Counter(row['ObjectName'] for row in rows)),
        'unsupported_entities':[],'complete':True}


_CONTEXT_KEY=object()


class NativeDeliveryContext:
    """Internal, non-JSON result of the live CAD MCP worker, not an offline receipt."""
    def __init__(self,snapshot,key):
        if key is not _CONTEXT_KEY:raise TypeError('Native context is created only by the live service factory')
        self.snapshot=snapshot


def service_context(snapshot):
    if snapshot.get('ok') is not True or snapshot.get('stable_read_verified') is not True or not snapshot.get('provenance'):
        raise ValueError('Actual stable live service snapshot and load/save provenance required')
    return NativeDeliveryContext(snapshot,_CONTEXT_KEY)


def inspect(context,path,expected):
    if not isinstance(context,NativeDeliveryContext):
        raise ValueError('DWG_LIVE_MCP_REVALIDATION_REQUIRED: JSON/offline receipts are not a live channel')
    snapshot=context.snapshot
    from .qa import file_hash
    if Path(snapshot['path']).resolve()!=Path(path).resolve() or snapshot['file_sha256']!=file_hash(path):
        raise ValueError('NATIVE_FILE_BINDING_CHANGED')
    facts=snapshot['facts']
    if expected.get('units')!=facts['variables']['INSUNITS']:
        raise ValueError('Native DWG units differ or are unspecified')
    if expected.get('entity_counts')!=facts['entity_counts']:
        raise ValueError('Complete native DWG entity counts are required and must match')
    required=expected.get('modelspace_handles')
    if not isinstance(required,list) or set(required)!={row['Handle'] for row in facts['model']} or len(required)!=len(set(required)):
        raise ValueError('Complete native DWG handle inventory is required')
    names={layer['Name'] for layer in facts['layers']}
    if set(expected.get('required_layers',[]))-names:raise ValueError('Native DWG required layers missing')
    if not snapshot.get('preview') or not snapshot['preview'].get('native_preview'):
        if not snapshot.get('correspondence_preview'):raise ValueError('NATIVE_CURRENT_PREVIEW_REQUIRED')
    correspondence=snapshot.get('correspondence_preview')
    if correspondence:
        if (correspondence.get('kind')!='native_source_correspondence'
                or correspondence.get('native_file_sha256')!=snapshot['file_sha256']
                or correspondence.get('native_snapshot_sha256')!=snapshot['snapshot_sha256']
                or correspondence.get('full_model_coverage_verified') is not True
                or file_hash(Path(correspondence['source_path']))!=correspondence.get('source_file_sha256')
                or file_hash(Path(correspondence['path']))!=correspondence.get('sha256')):
            raise ValueError('Native-source full-coverage preview binding changed')
    return {'format':'dwg','reopened':snapshot['provenance']['kind']=='open_document',
        'native_save_or_open_verified':True,'document_token':snapshot['document_token'],
        'snapshot_sha256':snapshot['snapshot_sha256'],'file_sha256':snapshot['file_sha256'],
        'native_preview':snapshot['preview'],'actual':facts,
        'lifecycle':snapshot.get('lifecycle'),'saved_closed_reopened_verified':snapshot.get('saved_closed_reopened_verified') is True,
        'verified_visual_preview':correspondence if correspondence else snapshot['preview'],
        'visual_coverage_verified':bool(correspondence and correspondence.get('full_model_coverage_verified')),
        'scope':facts['scope'],'native_paper_plot_verified':False}


def measure_native(actual,check):
    fields={'count':{'range','types'},'dimension':{'range'},'text':{'expected'},
        'geometry':{'expected','tolerance'},'length':{'range'},'closed':{'expected'},'area':{'range'}}
    if not isinstance(check,dict) or check.get('kind') not in fields or set(check)-({'kind','handles'}|fields[check['kind']]):
        raise ValueError('Unsupported native measurement fields need a verified adapter')
    facts=actual['actual'];handles=check.get('handles')
    if not isinstance(handles,list) or not handles or len(handles)!=len(set(handles)):
        raise ValueError('Distinct native handles required')
    table={row['Handle']:row for row in facts['model']}
    if set(handles)-table.keys():raise ValueError('Native object handle not found')
    rows=[table[h] for h in handles];kind=check.get('kind')
    if kind=='count':
        allowed=check.get('types',[])
        value=len(rows);passed=all(row['ObjectName'] in allowed for row in rows)
    elif kind=='dimension':
        if len(rows)!=1 or rows[0]['ObjectName'] not in DIMENSIONS:raise ValueError('One native dimension required')
        value=rows[0]['Measurement'];passed=bool(rows[0].get('native_display'))
    elif kind=='text':
        values=[row.get('TextString') for row in rows]
        return {'passed':values==check['expected'],'actual':values}
    elif kind=='geometry':
        if len(rows)!=1 or not isinstance(check.get('expected'),dict) or not check['expected']:
            raise ValueError('One object with explicit native property expectations required')
        row=rows[0];tolerance=_number(check.get('tolerance'),'geometry tolerance')
        if tolerance<=0:raise ValueError('Positive native geometry tolerance required')
        differences=[]
        def equal(a,b):
            if isinstance(b,(list,tuple)):
                return isinstance(a,(list,tuple)) and len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
            if isinstance(b,bool) or isinstance(b,str):return type(a)==type(b) and a==b
            return not isinstance(a,bool) and isinstance(a,(float,int)) and abs(_number(a,'actual')-_number(b,'expected'))<=tolerance
        permitted={'StartPoint','EndPoint','Center','Radius','StartAngle','EndAngle','MajorAxis','MinorAxis','RadiusRatio',
            'StartParameter','EndParameter','Coordinates','Closed','Bulges','TextString','InsertionPoint','ExtLine1Point','ExtLine2Point','TextPosition','Rotation'}
        for key,target in check['expected'].items():
            if key not in permitted or key not in row:raise ValueError('Native property is not available/verified: '+key)
            if not equal(row[key],target):differences.append(key)
        return {'passed':not differences,'actual':{key:row[key] for key in check['expected']},'different_properties':differences}
    elif kind=='length':
        values=[]
        for row in rows:
            name=row['ObjectName']
            if name=='AcDbLine' or name=='AcDbPolyline':values.append(row['Length'])
            elif name=='AcDbArc':values.append(row['ArcLength'])
            elif name=='AcDbCircle':values.append(2*math.pi*row['Radius'])
            else:raise ValueError('Native exact length adapter unavailable for this entity')
        value=sum(values);passed=True
    elif kind=='closed':
        if len(rows)!=1:raise ValueError('One native closedness object required')
        row=rows[0]
        if row['ObjectName']=='AcDbPolyline':value=row['Closed']
        elif row['ObjectName']=='AcDbCircle':value=True
        else:raise ValueError('Native closedness adapter unavailable')
        return {'passed':value is check.get('expected'),'actual':value}
    elif kind=='area':
        if len(rows)!=1:raise ValueError('One native area object required')
        row=rows[0]
        if row['ObjectName']=='AcDbPolyline' and row['Closed']:value=row['Area']
        elif row['ObjectName']=='AcDbCircle':value=math.pi*row['Radius']**2
        else:raise ValueError('Native exact area adapter unavailable')
        passed=True
    else:raise ValueError('Unsupported native measurement; no approximate DXF fallback: '+str(kind))
    bounds=check.get('range')
    if not isinstance(bounds,list) or len(bounds)!=2:raise ValueError('Native [min,max] interval required')
    lo,hi=[_number(v,'measurement interval') for v in bounds]
    return {'passed':passed and lo<=value<=hi,'actual':value}


def check_style(actual,style):
    if (not isinstance(style,dict) or set(style)-{'basis','layers'} or not style.get('basis')
            or not isinstance(style.get('layers'),dict)):
        raise ValueError('Explicit native layer rules and their basis required')
    failures=[];measured=[];facts=actual['actual'];layers={layer['Name']:layer for layer in facts['layers']}
    for row in actual['actual']['model']:
        rule=style['layers'].get(row['Layer'])
        if rule is None:raise ValueError('Native style rule missing for used layer '+row['Layer'])
        if set(rule)-{'lineweight_mm','linetypes','polyline_width'}:raise ValueError('Unknown native style expectation')
        lo,hi=rule['lineweight_mm']
        if not lo<=row['effective_lineweight_mm']<=hi:failures.append('lineweight:'+row['Handle'])
        if row['effective_linetype'].casefold() not in {name.casefold() for name in rule['linetypes']}:
            failures.append('linetype:'+row['Handle'])
        if row['ObjectName']=='AcDbPolyline':
            lo,hi=rule['polyline_width'];widths=[row['ConstantWidth'],*[v for pair in row['VertexWidths'] for v in pair]]
            if any(not lo<=value<=hi for value in widths):failures.append('polyline_width:'+row['Handle'])
        measured.append({'handle':row['Handle'],'layer':row['Layer'],'lineweight_mm':row['effective_lineweight_mm'],'linetype':row['effective_linetype']})
        if row['ObjectName'] in DIMENSIONS:
            low,high=rule['lineweight_mm']
            def resolved_pen(value,layer,parent_pen):
                if value==-1:value=layers.get(layer,{}).get('Lineweight')
                elif value==-2:return parent_pen
                if value==-3:value=facts['variables']['LWDEFAULT']
                return value/100 if type(value) is int and value>0 else None
            for key in ('DimensionLineWeight','ExtensionLineWeight'):
                pen=row.get(key)
                effective=resolved_pen(pen,row['Layer'],row['effective_lineweight_mm'])
                if effective is None:failures.append('dimension_pen_unsupported:'+row['Handle']+':'+key)
                elif not low<=effective<=high:failures.append('dimension_pen:'+row['Handle']+':'+key)
                measured.append({'handle':row['Handle'],'property':key,'raw_pen':pen,'lineweight_mm':effective,
                    'method':'actual native dimension instance inheritance'})
            block=facts.get('dimension_blocks',{}).get(row.get('native_geometry_block'))
            if block is None:
                failures.append('dimension_display_missing:'+row['Handle']);continue
            strokes=0;budget=0
            def display(block,parent_layer,parent_pen,parent_pattern,names=()):
                nonlocal strokes,budget
                for item in block['entities']:
                    budget+=1
                    if budget>100000 or len(names)>16:raise ValueError('Native dimension display style budget exceeded')
                    groups=dict((code,value) for code,value in item['groups'] if code!=100)
                    layer=groups.get(8,'0');layer=parent_layer if layer=='0' else layer
                    raw=groups.get(370,-1);effective=resolved_pen(raw,layer,parent_pen)
                    pattern=groups.get(6,'ByLayer')
                    if pattern.casefold()=='bylayer':pattern=layers.get(layer,{}).get('Linetype')
                    elif pattern.casefold()=='byblock':pattern=parent_pattern
                    if groups.get(0)=='INSERT':
                        name=groups.get(2);inner=facts.get('dimension_blocks',{}).get(name)
                        if inner is None or name in names or effective is None:
                            failures.append('dimension_display_reference_unsupported:'+row['Handle']);continue
                        display(inner,layer,effective,pattern,(*names,name))
                    elif groups.get(0) in {'LINE','ARC','CIRCLE','ELLIPSE','LWPOLYLINE'}:
                        strokes+=1
                        measured.append({'dimension':row['Handle'],'display_handle':item['handle'],'layer':layer,'raw_pen':raw,
                            'lineweight_mm':effective,'method':'actual native cached stroke instance inheritance'})
                        if effective is None or not low<=effective<=high:
                            failures.append('dimension_display_stroke:'+row['Handle']+'/'+item['handle'])
                        if not isinstance(pattern,str) or pattern.casefold() not in {name.casefold() for name in rule['linetypes']}:
                            failures.append('dimension_display_linetype:'+row['Handle']+'/'+item['handle'])
            display(block,row['Layer'],row['effective_lineweight_mm'],row['effective_linetype'])
            if not strokes:failures.append('dimension_display_strokes_missing:'+row['Handle'])
    return {'passed':not failures,'findings':failures,'actual':measured,'native_plot_style_verified':False}
