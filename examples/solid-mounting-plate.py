"""Original parameterized fixture; dimensions are mm, not inferred from an image."""
plate = Box(80, 50, 8)
for x in (-25, 25):
    for y in (-15, 15):
        plate = plate - Pos(x, y, 0) * Cylinder(3, 8)
show_object(plate)
