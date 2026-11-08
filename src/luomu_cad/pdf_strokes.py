"""Measure actually painted PDF stroke segments in physical page millimetres."""
import math
from collections import defaultdict
from pypdf.generic import ContentStream


def painted_segments(page,reader):
    unit=float(page.get('/UserUnit',1))*25.4/72
    def mul(left,right):
        a,b,c,d,e,f=left;aa,bb,cc,dd,ee,ff=right
        return (a*aa+c*bb,b*aa+d*bb,a*cc+c*dd,b*cc+d*dd,a*ee+c*ff+e,b*ee+d*ff+f)
    def walk(stream,resources,matrix=(1,0,0,1,0,0),width=1,alpha=1,depth=0):
        if depth>12:raise ValueError('PDF Form stroke depth exceeded')
        if hasattr(resources,'get_object'):resources=resources.get_object()
        stack=[];segments=[];current=None;start=None;result=[]
        def point(x,y):
            a,b,c,d,e,f=matrix
            return ((a*float(x)+c*float(y)+e)*unit,(b*float(x)+d*float(y)+f)*unit)
        def line(end):
            nonlocal current
            if current is None:raise ValueError('PDF line has no current point')
            segments.append(('L',current,end));current=end
        def close():
            if current is not None and start is not None and current!=start:line(start)
        for args,op in ContentStream(stream,reader).operations:
            if op==b'q':stack.append((matrix,width,alpha))
            elif op==b'Q':
                if not stack:raise ValueError('Unbalanced PDF stroke state')
                matrix,width,alpha=stack.pop()
            elif op==b'cm':matrix=mul(matrix,tuple(map(float,args)))
            elif op==b'w':width=float(args[0])
            elif op==b'gs':
                state=resources.get('/ExtGState',{}).get(args[0])
                if state is not None:
                    state=state.get_object();width=float(state.get('/LW',width));alpha=float(state.get('/CA',alpha))
            elif op==b'm':current=point(*args);start=current
            elif op==b'l':line(point(*args))
            elif op in {b'c',b'v',b'y'}:
                if current is None:raise ValueError('PDF curve has no current point')
                if op==b'c':first=point(*args[:2]);second=point(*args[2:4]);end=point(*args[4:])
                elif op==b'v':first=current;second=point(*args[:2]);end=point(*args[2:])
                else:first=point(*args[:2]);end=point(*args[2:]);second=end
                segments.append(('C',current,first,second,end));current=end
            elif op==b'h':close()
            elif op==b're':
                x,y,w,h=map(float,args);current=point(x,y);start=current
                for end in [point(x+w,y),point(x+w,y+h),point(x,y+h),start]:line(end)
            elif op in {b'S',b's',b'B',b'B*',b'b',b'b*'}:
                if op in {b's',b'b',b'b*'}:close()
                if segments and alpha>0:
                    a,b,c,d,_,_=matrix;sx,sy=math.hypot(a,b),math.hypot(c,d)
                    if not math.isclose(sx,sy,rel_tol=1e-5,abs_tol=1e-8) or abs(a*c+b*d)>1e-5*max(sx*sy,1e-8):
                        raise ValueError('Nonuniform PDF stroke physical-width adapter required')
                    physical=width*sx*unit
                    if not math.isfinite(physical) or physical<0:raise ValueError('Invalid physical PDF pen')
                    result.extend((segment,physical) for segment in segments)
                segments=[];current=start=None
            elif op in {b'f',b'f*',b'F',b'n'}:segments=[];current=start=None
            elif op==b'Do':
                form=resources.get('/XObject',{}).get(args[0])
                if form is not None:
                    form=form.get_object()
                    if form.get('/Subtype')=='/Form':
                        result.extend(walk(form,form.get('/Resources',resources),
                            mul(matrix,tuple(map(float,form.get('/Matrix',[1,0,0,1,0,0])))),width,alpha,depth+1))
        if stack:raise ValueError('Unbalanced PDF stroke state')
        return result
    return walk(page.get_contents(),page.get('/Resources',{}))


def compare_painted_segments(actual,expected):
    def inventory(values):
        result=defaultdict(list)
        for segment,width in values:
            kind,*points=segment
            points=tuple(tuple(round(float(v),4) for v in point) for point in points)
            # Equivalent direction and path grouping do not alter line geometry.
            geometry=(kind,*min(points,tuple(reversed(points))))
            result[geometry].append(round(width,5))
        return {key:sorted(values) for key,values in result.items()}
    left,right=inventory(actual),inventory(expected)
    different=[key for key in left.keys()|right.keys() if left.get(key)!=right.get(key)]
    return {'passed':not different,'actual_painted_segments':len(actual),'expected_painted_segments':len(expected),
        'different_segments':len(different),'differences':[{'geometry_mm':key,'actual_widths_mm':left.get(key,[]),
            'expected_widths_mm':right.get(key,[])} for key in sorted(different)[:50]],
        'method':'actual stroked L/C segments matched in physical page coordinates; widths sampled at paint, not idle w declarations'}
