# =========================================================================
# Pasta: igz-UV/core/
# Arquivo: keyboard_tool.py
# Descrição: UVTransformTool — transformação UV interativa via teclado.
# =========================================================================
import math

from PySide6.QtCore import Qt

from .mappings import _t
from .texture import selected_faces, ensure_uv_texture, read_uvw, apply_uvw_to_face

try:
    from tools.base import Tool
except Exception:
    class Tool:  # type: ignore
        name = ""
        shortcut = None
        description = ""

        def __init__(self, viewport=None):
            self.viewport = viewport

try:
    from core.history import SnapshotImport
except Exception:
    class SnapshotImport:  # type: ignore
        def __init__(self, fn):
            self.fn = fn


class UVTransformTool(Tool):
    name = "UV Transform"
    description = "Arrow keys move/scale/rotate UVs on selected faces."
    status_clause = "Arrows: move · Shift: scale · Ctrl: rotate"
    vcb_label = "UV"
    shortcut = None
    shortcut_alt = None
    uses_snap = False
    icon = None

    def __init__(self, viewport=None):
        self._nudge = 0.05
        self._scale_nudge = 1.05
        self._rotate_nudge = 1.0

    def on_activate(self, viewport):
        try:
            viewport.flash_status(
                _t("UV Transform: arrow keys (Shift=scale, Ctrl=rotate)."),
                4000)
        except Exception:
            pass

    def on_deactivate(self, viewport):
        pass

    def on_key(self, viewport, key, modifiers):
        faces = selected_faces(viewport)
        if not faces:
            return False
        shift = bool(modifiers & Qt.ShiftModifier)
        ctrl = bool(modifiers & Qt.ControlModifier)
        if key == Qt.Key_Left:
            if shift:
                self._scale(viewport, faces, self._scale_nudge, 1.0)
            elif ctrl:
                self._rotate(viewport, faces, -self._rotate_nudge)
            else:
                self._offset(viewport, faces, self._nudge, 0.0)
        elif key == Qt.Key_Right:
            if shift:
                self._scale(viewport, faces, 1.0 / self._scale_nudge, 1.0)
            elif ctrl:
                self._rotate(viewport, faces, self._rotate_nudge)
            else:
                self._offset(viewport, faces, -self._nudge, 0.0)
        elif key == Qt.Key_Down:
            if shift:
                self._scale(viewport, faces, 1.0, self._scale_nudge)
            else:
                self._offset(viewport, faces, 0.0, self._nudge)
        elif key == Qt.Key_Up:
            if shift:
                self._scale(viewport, faces, 1.0, 1.0 / self._scale_nudge)
            else:
                self._offset(viewport, faces, 0.0, -self._nudge)
        else:
            return False
        return True

    def on_value(self, viewport, value):
        faces = selected_faces(viewport)
        if not faces:
            return False
        try:
            v = float(value)
        except Exception:
            return False
        if -180.0 <= v <= 180.0:
            self._rotate(viewport, faces, v)
        elif v > 0.0:
            self._scale(viewport, faces, v, v)
        else:
            return False
        return True

    def on_cancel(self, viewport):
        pass

    # -- operações -----------------------------------------------------
    def _offset(self, viewport, faces, du, dv):
        def mutate(scene):
            for f in faces:
                if not ensure_uv_texture(f):
                    continue
                uvw = read_uvw(f)
                if uvw is None:
                    uvw = [0.0] * 8
                uvw[3] += du
                uvw[7] += dv
                apply_uvw_to_face(f, uvw)
        viewport.history.execute(SnapshotImport(mutate))
        viewport.notify_scene_changed()

    def _scale(self, viewport, faces, su, sv):
        def mutate(scene):
            for f in faces:
                if not ensure_uv_texture(f):
                    continue
                uvw = read_uvw(f)
                if uvw is None:
                    continue
                uvw[0] *= su; uvw[1] *= su; uvw[2] *= su
                uvw[4] *= sv; uvw[5] *= sv; uvw[6] *= sv
                apply_uvw_to_face(f, uvw)
        viewport.history.execute(SnapshotImport(mutate))
        viewport.notify_scene_changed()

    def _rotate(self, viewport, faces, degrees):
        a = math.radians(degrees)
        ca, sa = math.cos(a), math.sin(a)
        def mutate(scene):
            for f in faces:
                if not ensure_uv_texture(f):
                    continue
                uvw = read_uvw(f)
                if uvw is None:
                    continue
                gx, gy, gz = uvw[0], uvw[1], uvw[2]
                hx, hy, hz = uvw[4], uvw[5], uvw[6]
                uvw[0] = ca * gx - sa * hx
                uvw[1] = ca * gy - sa * hy
                uvw[2] = ca * gz - sa * hz
                uvw[4] = sa * gx + ca * hx
                uvw[5] = sa * gy + ca * hy
                uvw[6] = sa * gz + ca * hz
                apply_uvw_to_face(f, uvw)
        viewport.history.execute(SnapshotImport(mutate))
        viewport.notify_scene_changed()