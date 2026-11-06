"""Source-coordinate helpers for faithful redraws; no layout inference."""
import math


class PageTransform:
    """Uniform page scale, optional Y reflection and explicit origin."""
    def __init__(self, mm_per_unit, origin=(0,0), flip_y=True):
        values=[mm_per_unit,*origin]
        if len(origin)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values) or mm_per_unit<=0:
            raise ValueError('Explicit finite origin and positive uniform scale required')
        if not isinstance(flip_y,bool):raise ValueError('flip_y must be boolean')
        self.scale=mm_per_unit;self.origin=origin;self.flip_y=flip_y

    def point(self, value):
        if len(value)!=2 or any(not math.isfinite(v) for v in value):raise ValueError('Expected finite 2D source point')
        return ((value[0]-self.origin[0])*self.scale,
                (value[1]-self.origin[1])*self.scale*(-1 if self.flip_y else 1),0)

    def arc(self, center, radius, start_angle, end_angle):
        if not all(math.isfinite(v) for v in (radius,start_angle,end_angle)) or radius<=0:
            raise ValueError('Invalid source arc')
        if (end_angle-start_angle)%360==0:raise ValueError('Use a CIRCLE for a full circle')
        # DXF ARC travels counterclockwise. Reflection reverses traversal.
        start,end=(-end_angle,-start_angle) if self.flip_y else (start_angle,end_angle)
        return {'center':self.point(center),'radius':radius*self.scale,
                'start_angle':start%360,'end_angle':end%360}

    def add_cubic(self, model, controls, dxfattribs=None):
        """Preserve a cubic Bezier exactly as a clamped cubic SPLINE."""
        if len(controls)!=4:raise ValueError('A cubic requires four source control points')
        return model.add_open_spline([self.point(p) for p in controls],degree=3,
                                    knots=[0,0,0,0,1,1,1,1],dxfattribs=dxfattribs)
