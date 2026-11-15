# =========================================================================
# Pasta: igz-UV/core/
# Arquivo: texture.py
# Descrição: Acesso ao modelo UV de faces (textura, uvw, grade automática).
# =========================================================================
import os
import traceback

from .math_utils import vec3


def _log(s):
    try:
        print(f"[igz-UV] {s}", flush=True)
    except Exception:
        pass


# -- seleção / faces ------------------------------------------------------
def get_scene(viewport_or_scene):
    if viewport_or_scene is None:
        return None
    if type(viewport_or_scene).__name__ == "Scene":
        return viewport_or_scene
    return getattr(viewport_or_scene, "scene", None) or viewport_or_scene


def iter_faces(entities):
    for e in entities or []:
        if type(e).__name__ == "Face":
            yield e


def selected_faces(viewport_or_scene):
    scene = get_scene(viewport_or_scene)
    if scene is None:
        return []
    sel = getattr(scene, "selection", None) or []
    return list(iter_faces(sel))


def face_loop_points(face):
    loop = getattr(face, "loop", None)
    if loop:
        out = []
        for v in loop:
            pos = getattr(v, "position", None)
            if pos is None:
                pos = v
            out.append(vec3(pos))
        if out:
            return out
    verts = getattr(face, "vertices", None) or []
    return [vec3(p) for p in verts]


def face_normal(face):
    n = getattr(face, "normal", None)
    if n is None:
        return (0.0, 0.0, 1.0)
    if callable(n):
        n = n()
    return vec3(n)


def face_texture(face):
    if not hasattr(face, "attrs"):
        return None
    t = face.attrs.get("texture")
    return t if isinstance(t, dict) else None


def face_valida(face):
    try:
        _ = getattr(face, "loop", None)
        return True
    except Exception:
        return False


# -- grade UV automática --------------------------------------------------
_ICONS_DIR = None


def set_icons_dir(path):
    global _ICONS_DIR
    _ICONS_DIR = path


def uv_grid_path():
    if not _ICONS_DIR or not os.path.isdir(_ICONS_DIR):
        return None
    for nome in ("texture_grid.jpg", "texture_grid.png",
                 "texture_grid.JPG", "texture_grid.jpeg"):
        p = os.path.join(_ICONS_DIR, nome)
        if os.path.isfile(p):
            return p
    try:
        for f in os.listdir(_ICONS_DIR):
            if f.lower().startswith("texture_grid."):
                return os.path.join(_ICONS_DIR, f)
    except Exception:
        pass
    return None


def ensure_uv_texture(face) -> bool:
    if face_texture(face) is not None:
        return True
    path = uv_grid_path()
    if not path or not hasattr(face, "attrs"):
        return False
    tex = face.attrs.get("texture")
    tex = dict(tex) if isinstance(tex, dict) else {}
    tex.update({
        "path": path,
        "sw": float(tex.get("sw", 1.0) or 1.0),
        "sh": float(tex.get("sh", 1.0) or 1.0),
        "rot": float(tex.get("rot", 0.0) or 0.0),
    })
    face.attrs["texture"] = tex
    # Registra o nome do material para aparecer no registro de
    # materiais do IngeTrazo.
    if "mat" not in face.attrs:
        face.attrs["mat"] = "igz-UV Texture"
    return True


# -- uvw (transform afim) -------------------------------------------------
def apply_uvw_to_face(face, uvw):
    if not hasattr(face, "attrs"):
        return
    tex = face.attrs.get("texture")
    if not isinstance(tex, dict):
        tex = {}
    tex = dict(tex)
    tex["uvw"] = list(uvw)
    face.attrs["texture"] = tex


def read_uvw(face):
    tex = face_texture(face)
    if not tex:
        return None
    uvw = tex.get("uvw")
    if not uvw or len(uvw) != 8:
        return None
    return [float(x) for x in uvw]


def uv_at(uvw, p):
    x, y, z = vec3(p)
    u = uvw[0] * x + uvw[1] * y + uvw[2] * z + uvw[3]
    v = uvw[4] * x + uvw[5] * y + uvw[6] * z + uvw[7]
    return u, v