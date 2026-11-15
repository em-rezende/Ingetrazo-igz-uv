# =========================================================================
# Pasta: igz-UV/core/
# Arquivo: triangulate.py
# Descrição: Triangulação em leque preservando UVs.
# =========================================================================
import traceback

from .math_utils import as_qvec3
from .mappings import _t, require_faces
from .texture import (
    face_loop_points, face_texture, ensure_uv_texture, apply_uvw_to_face,
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


def triangulate_selection(viewport):
    faces = require_faces(viewport)
    if not faces:
        return

    def mutate(scene):
        for f in faces:
            pts = face_loop_points(f)
            if len(pts) <= 3:
                continue
            tex = face_texture(f)
            if tex is None:
                if not ensure_uv_texture(f):
                    continue
                tex = face_texture(f) or {}
            try:
                uvs = _tex.face_uvs(f, tex)
            except Exception:
                uvs = [(0.0, 0.0)] * len(pts)
            keep_tex = dict(tex)
            keep_mat = f.attrs.get("mat") if hasattr(f, "attrs") else None
            mesh = scene.mesh
            for i in range(1, len(pts) - 1):
                tri_pts = [pts[0], pts[i], pts[i + 1]]
                tri_uvs = [uvs[0], uvs[i], uvs[i + 1]]
                nf = mesh.add_face([as_qvec3(p) for p in tri_pts])
                if nf is None:
                    continue
                if hasattr(nf, "attrs"):
                    if keep_tex:
                        nf.attrs["texture"] = dict(keep_tex)
                    if keep_mat is not None:
                        nf.attrs["mat"] = keep_mat
                try:
                    uvw = _tex.fit_uv_affine(tri_pts, tri_uvs)
                    if uvw is not None:
                        apply_uvw_to_face(nf, uvw)
                except Exception:
                    pass
            try:
                mesh.remove_face(f)
            except Exception:
                pass

    viewport.history.execute(SnapshotImport(mutate))
    viewport.notify_scene_changed()
    try:
        viewport.flash_status(_t("Triangulation finished."), 2500)
    except Exception:
        pass