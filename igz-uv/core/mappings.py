# =========================================================================
# Pasta: igz-UV/core/
# Arquivo: mappings.py
# Descrição: Projeções UV (planar, esférica, cilíndrica, box, quad, tube)
#            e o núcleo de aplicação (_apply_uv_map).
# =========================================================================
import math
import traceback

from PySide6.QtWidgets import QMessageBox

from .math_utils import (
    as_qvec3, sub, length, centroid, bounding_box, fit_plane,
)
from .texture import (
    selected_faces, face_loop_points, face_normal, face_texture,
    ensure_uv_texture, apply_uvw_to_face,
)

try:
    from core import texture as _tex
except Exception:
    _tex = None

try:
    from core.history import SnapshotImport
except Exception:
    class SnapshotImport:  # type: ignore
        def __init__(self, fn):
            self.fn = fn


def _t(s, **kw):
    # Stub até o __init__.py instalar a tradução real via set_translator()
    return _GLOBAL_TRANSLATOR(s, **kw) if _GLOBAL_TRANSLATOR else s


_GLOBAL_TRANSLATOR = None


def set_translator(fn):
    global _GLOBAL_TRANSLATOR
    _GLOBAL_TRANSLATOR = fn


def require_faces(viewport):
    faces = selected_faces(viewport)
    if not faces:
        QMessageBox.information(
            viewport.window, "igz-UV",
            _t("Select at least one face."),
        )
    return faces


# -- núcleo ---------------------------------------------------------------
def apply_uv_map(viewport, faces, uv_fn, label):
    if not faces:
        return

    no_tex, failed, ok = [], [], 0

    def mutate(scene):
        nonlocal ok, no_tex, failed
        for f in faces:
            pts = face_loop_points(f)
            if len(pts) < 3:
                failed.append(f)
                continue
            if not ensure_uv_texture(f):
                no_tex.append(f)
                continue
            try:
                uvs = uv_fn(f, pts)
            except Exception:
                traceback.print_exc()
                failed.append(f)
                continue
            try:
                uvw = _tex.fit_uv_affine(pts, uvs)
            except Exception:
                traceback.print_exc()
                failed.append(f)
                continue
            if uvw is None:
                failed.append(f)
                continue
            apply_uvw_to_face(f, uvw)
            ok += 1

    viewport.history.execute(SnapshotImport(mutate))
    viewport.notify_scene_changed()

    msg = _t("{label}: {ok}/{total} face(s).",
             label=label, ok=ok, total=len(faces))
    if no_tex:
        msg += _t("  {n} without texture.", n=len(no_tex))
    if failed:
        msg += _t("  {n} failed.", n=len(failed))
    try:
        viewport.flash_status(msg, 3500)
    except Exception:
        pass


# -- projeções ------------------------------------------------------------
def _planar_uvs(pts, normal, sw, sh, rot=0.0):
    if _tex is not None and hasattr(_tex, "planar_uv"):
        return _tex.planar_uv(as_qvec3(normal),
                              [as_qvec3(p) for p in pts], sw, sh, rot)
    bb = bounding_box(pts)
    if bb is None:
        return [(0.0, 0.0)] * len(pts)
    min_x, min_y, _, max_x, max_y, _ = bb
    w = max(1e-9, max_x - min_x)
    h = max(1e-9, max_y - min_y)
    return [((p[0] - min_x) / w, (p[1] - min_y) / h) for p in pts]


def _spherical_uvs(pts, center):
    pi = math.pi
    out = []
    for p in pts:
        dx = p[0] - center[0]
        dy = p[1] - center[1]
        dz = p[2] - center[2]
        r = math.sqrt(dx * dx + dy * dy + dz * dz)
        if r == 0.0:
            out.append((0.0, 0.0))
            continue
        theta = math.acos(max(-1.0, min(1.0, dz / r)))
        phi = math.atan2(dy, dx)
        v = 1.0 - (theta / pi)
        if phi < 0.0:
            phi = 2.0 * pi + phi
        out.append((phi / (2.0 * pi), v))
    return out


def _cylindrical_uvs(pts, z_extents, center):
    pi = math.pi
    zmax, zmin = z_extents
    out = []
    for p in pts:
        dx = p[0] - center[0]
        dy = p[1] - center[1]
        v = 0.0 if zmax == zmin else (p[2] - zmin) / (zmax - zmin)
        phi = math.atan2(dy, dx)
        if phi < 0.0:
            phi = 2.0 * pi + phi
        out.append((phi / (2.0 * pi), v))
    return out


def _validate_uvs(uvs):
    if not uvs:
        return uvs
    u_max = max(u for u, _ in uvs)
    out = []
    for u, v in uvs:
        if u != u_max and (u_max - u) > 0.8:
            u += 1.0
        out.append((u, v))
    return out


# -- comandos públicos ----------------------------------------------------
def planar_map(viewport):
    faces = require_faces(viewport)
    if not faces:
        return
    def fn(face, pts):
        tex = face_texture(face) or {}
        sw = float(tex.get("sw", 1.0) or 1.0)
        sh = float(tex.get("sh", 1.0) or 1.0)
        rot = float(tex.get("rot", 0.0) or 0.0)
        return _planar_uvs(pts, face_normal(face), sw, sh, rot)
    apply_uv_map(viewport, faces, fn, _t("Planar Map"))


def spherical_map(viewport):
    faces = require_faces(viewport)
    if not faces:
        return
    all_pts = []
    for f in faces:
        all_pts.extend(face_loop_points(f))
    center = centroid(all_pts)
    def fn(face, pts):
        return _validate_uvs(_spherical_uvs(pts, center))
    apply_uv_map(viewport, faces, fn, _t("Spherical Map"))


def cylindrical_map(viewport):
    faces = require_faces(viewport)
    if not faces:
        return
    all_pts = []
    for f in faces:
        all_pts.extend(face_loop_points(f))
    bb = bounding_box(all_pts)
    if bb is None:
        return
    z_min, z_max = bb[2], bb[5]
    z_extents = (z_max, z_min)
    center = centroid(all_pts)
    def fn(face, pts):
        return _validate_uvs(_cylindrical_uvs(pts, z_extents, center))
    apply_uv_map(viewport, faces, fn, _t("Cylindrical Map"))


def box_map(viewport):
    faces = require_faces(viewport)
    if not faces:
        return
    all_pts = []
    for f in faces:
        all_pts.extend(face_loop_points(f))
    bb = bounding_box(all_pts)
    if bb is None:
        return
    min_x, min_y, min_z, max_x, max_y, max_z = bb
    size = max(max_x - min_x, max_y - min_y, max_z - min_z)
    if size <= 0.0:
        size = 1.0
    def fn(face, pts):
        n = face_normal(face)
        if length(n) <= 1e-9:
            n, _c = fit_plane(pts)
        ax, ay, az = abs(n[0]), abs(n[1]), abs(n[2])
        if ax >= ay and ax >= az:
            if n[0] >= 0.0:
                return [((p[1] - min_y) / size, (p[2] - min_z) / size)
                        for p in pts]
            return [((max_y - p[1]) / size, (p[2] - min_z) / size)
                    for p in pts]
        if ay >= ax and ay >= az:
            if n[1] >= 0.0:
                return [((max_x - p[0]) / size, (p[2] - min_z) / size)
                        for p in pts]
            return [((p[0] - min_x) / size, (p[2] - min_z) / size)
                    for p in pts]
        if n[2] >= 0.0:
            return [((p[0] - min_x) / size, (p[1] - min_y) / size)
                    for p in pts]
        return [((max_x - p[0]) / size, (p[1] - min_y) / size)
                for p in pts]
    apply_uv_map(viewport, faces, fn, _t("Box Map"))


def quad_face_map(viewport):
    faces = [f for f in require_faces(viewport)
             if len(getattr(f, "vertices", None) or []) == 4]
    if not faces:
        QMessageBox.information(viewport.window, "igz-UV",
                                _t("Select quad faces (4 vertices)."))
        return
    quad_uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    def fn(face, pts):
        return quad_uvs[:len(pts)]
    apply_uv_map(viewport, faces, fn, _t("Quad Face Map"))


def tube_map(viewport):
    faces = require_faces(viewport)
    if not faces:
        return
    ordered = sorted(faces, key=lambda f: centroid(face_loop_points(f)))
    state = {"u": 0.0}
    def fn(face, pts):
        per = 0.0
        n = len(pts)
        for i in range(n):
            per += length(sub(pts[i], pts[(i + 1) % n]))
        u0 = state["u"]
        state["u"] += per
        u1 = state["u"]
        out = []
        acc = 0.0
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            seg = length(sub(a, b))
            u = u0 + (acc / per if per > 0 else 0.0) * (u1 - u0)
            v = 0.0 if i < n / 2.0 else 1.0
            out.append((u, v))
            acc += seg
        return out
    apply_uv_map(viewport, ordered, fn, _t("Tube Map"))