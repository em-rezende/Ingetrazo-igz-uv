# =========================================================================
# Pasta: igz-UV/core/
# Arquivo: math_utils.py
# Descrição: Utilidades geométricas puras (sem dependência do IngeTrazo).
# =========================================================================
import math

from PySide6.QtGui import QVector3D


def vec3(p):
    """Normaliza QVector3D / objeto com .x()/.y()/.z() / tupla → (x, y, z)."""
    if isinstance(p, QVector3D):
        return (float(p.x()), float(p.y()), float(p.z()))
    if hasattr(p, "x") and hasattr(p, "y") and hasattr(p, "z"):
        x = p.x() if callable(p.x) else p.x
        y = p.y() if callable(p.y) else p.y
        z = p.z() if callable(p.z) else p.z
        return (float(x), float(y), float(z))
    x, y, z = p
    return (float(x), float(y), float(z))


def as_qvec3(p) -> QVector3D:
    x, y, z = vec3(p)
    return QVector3D(x, y, z)


def sub(a, b):
    a, b = vec3(a), vec3(b)
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    a, b = vec3(a), vec3(b)
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def length(v):
    x, y, z = vec3(v)
    return math.sqrt(x * x + y * y + z * z)


def normalize(v):
    l = length(v)
    if l == 0.0:
        return (0.0, 0.0, 0.0)
    x, y, z = vec3(v)
    return (x / l, y / l, z / l)


def centroid(points):
    n = float(len(points))
    if n == 0:
        return (0.0, 0.0, 0.0)
    cx = cy = cz = 0.0
    for p in points:
        x, y, z = vec3(p)
        cx += x
        cy += y
        cz += z
    return (cx / n, cy / n, cz / n)


def bounding_box(points):
    if not points:
        return None
    xs, ys, zs = zip(*[vec3(p) for p in points])
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def fit_plane(points):
    if len(points) < 3:
        return ((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    c = centroid(points)
    for i in range(1, len(points) - 1):
        a = sub(points[i], points[0])
        b = sub(points[i + 1], points[0])
        n = cross(a, b)
        if length(n) > 1e-9:
            return (normalize(n), c)
    return ((0.0, 0.0, 1.0), c)