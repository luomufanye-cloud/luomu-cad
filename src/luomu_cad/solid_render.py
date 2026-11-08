"""CPU previews from build123d's tessellation; no OpenGL context is needed."""
from pathlib import Path


def image_has_content(path):
    from PIL import Image
    try:
        with Image.open(path) as image:
            return image.format == 'PNG' and any(low != high for low, high in image.convert('RGB').getextrema())
    except (OSError, ValueError):
        return False


def render(source, output):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    from matplotlib.colors import LightSource
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from build123d import import_step

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    shape = import_step(str(source))
    vertices, indices = shape.tessellate(.05, .1)
    if not indices or len(indices) > 200000:
        raise ValueError('CPU_PREVIEW_TRIANGLE_BUDGET')
    points = np.array([(v.X, v.Y, v.Z) for v in vertices])
    faces = points[np.asarray(indices)]
    normals = np.cross(faces[:, 1] - faces[:, 0], faces[:, 2] - faces[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    normals /= np.where(lengths > 0, lengths, 1)[:, None]
    shade = LightSource(azdeg=315, altdeg=45).shade_normals(normals)
    colors = np.column_stack((.30 + .35*shade, .44 + .35*shade, .60 + .30*shade, np.ones(len(shade))))
    center = (points.min(axis=0) + points.max(axis=0)) / 2
    radius = float(np.ptp(points, axis=0).max()) * .58
    if not radius:
        raise ValueError('CPU_PREVIEW_EMPTY_BOUNDS')
    images = {}
    for name, (elevation, azimuth) in {'front': (0, -90), 'right': (0, 0), 'top': (90, -90), 'iso': (30, -45)}.items():
        figure = plt.figure(figsize=(8, 6), dpi=100)
        axis = figure.add_axes([0, 0, 1, 1], projection='3d')
        axis.set_proj_type('ortho')
        elev, azim = np.radians([elevation, azimuth])
        direction = np.array([np.cos(elev)*np.cos(azim), np.cos(elev)*np.sin(azim), np.sin(elev)])
        # Cull outward faces pointing away from this orthographic camera.
        # Otherwise Matplotlib's painter order can show back faces through holes.
        visible = normals @ direction > 1e-9
        axis.add_collection3d(Poly3DCollection(faces[visible], facecolors=colors[visible],
            edgecolors='none', antialiased=False, zsort='average'))
        axis.set_xlim(center[0]-radius, center[0]+radius)
        axis.set_ylim(center[1]-radius, center[1]+radius)
        axis.set_zlim(center[2]-radius, center[2]+radius)
        axis.set_box_aspect((1, 1, 1))
        axis.view_init(elev=elevation, azim=azimuth)
        axis.set_axis_off()
        path = output / (name + '.png')
        figure.savefig(path, facecolor='white')
        plt.close(figure)
        if not image_has_content(path):
            raise ValueError('CPU_PREVIEW_BLANK: ' + name)
        images[name] = str(path.resolve())
    return {'status': 'success', 'backend': 'build123d tessellation + matplotlib Agg',
            'renders': images, 'triangle_count': len(indices), 'requested_linear_tolerance_mm': .05,
            'requested_angular_tolerance_rad': .1, 'visual_review_passed': False}
