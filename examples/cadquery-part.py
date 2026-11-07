"""Original parameterized plate exercise; dimensions are explicit design inputs."""
import cadquery as cq

length, width, thickness, bore = 80, 50, 8, 12
result = (cq.Workplane('XY').box(length, width, thickness)
          .faces('>Z').workplane().hole(bore))
