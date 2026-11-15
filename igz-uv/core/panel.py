# =========================================================================
# Pasta: igz-UV/core/
# Arquivo: panel.py
# Descrição: UVAdjustPanel — painel lateral com sliders de ajuste fino.
# =========================================================================
import math

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QPushButton, QDoubleSpinBox, QSlider,
)

from .mappings import _t
from .texture import (
    selected_faces, face_loop_points, face_valida, ensure_uv_texture,
    read_uvw, apply_uvw_to_face, uv_at,
)
from .transforms import compose_uvw
from .math_utils import centroid

try:
    from core.history import SnapshotImport
except Exception:
    class SnapshotImport:  # type: ignore
        def __init__(self, fn):
            self.fn = fn


class UVAdjustPanel(QWidget):
    def __init__(self, viewport, parent=None):
        super().__init__(parent)
        self.viewport = viewport
        self._snapshot = {}
        self._centro_uv = (0.0, 0.0)
        self._faces_atuais = []
        self._build()
        self._refresh()

        self._state_timer = QTimer(self)
        self._state_timer.setInterval(400)
        self._state_timer.timeout.connect(self._check_state)
        self._state_timer.start()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        hint = QLabel(
            "<b>" + _t("Fine-tune UVs") + "</b><br>"
            "<i>" + _t("Move the sliders; click Apply to confirm.") + "</i>"
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.lbl_sel = QLabel("")
        self.lbl_sel.setWordWrap(True)
        self.lbl_sel.setStyleSheet("color: #888; font-size: 10px;")
        root.addWidget(self.lbl_sel)

        self.btn_atualizar = QPushButton(_t("Reload from current selection"))
        self.btn_atualizar.setToolTip(
            _t("Take a new snapshot of the selection and reset the sliders.")
        )
        self.btn_atualizar.clicked.connect(self._refresh)
        root.addWidget(self.btn_atualizar)

        gb_off = QGroupBox(_t("Offset"))
        form = QFormLayout(gb_off)
        self.sl_u, self.sp_u = self._make_pair(
            (-200, 200), 0, (-2.0, 2.0), 0.01, 2, "",
            lambda v: v / 100.0, lambda v: int(round(v * 100)))
        form.addRow("U:", self._pair(self.sl_u, self.sp_u))
        self.sl_v, self.sp_v = self._make_pair(
            (-200, 200), 0, (-2.0, 2.0), 0.01, 2, "",
            lambda v: v / 100.0, lambda v: int(round(v * 100)))
        form.addRow("V:", self._pair(self.sl_v, self.sp_v))
        root.addWidget(gb_off)

        gb_rs = QGroupBox(_t("Rotation and scale"))
        form2 = QFormLayout(gb_rs)
        self.sl_rot, self.sp_rot = self._make_pair(
            (-1800, 1800), 0, (-180.0, 180.0), 0.1, 1, "°",
            lambda v: v / 10.0, lambda v: int(round(v * 10)))
        form2.addRow(_t("Rotation:"), self._pair(self.sl_rot, self.sp_rot))
        self.sl_scu, self.sp_scu = self._make_pair(
            (10, 400), 100, (0.10, 4.00), 0.01, 2, "×",
            lambda v: v / 100.0, lambda v: int(round(v * 100)))
        form2.addRow(_t("Scale U:"), self._pair(self.sl_scu, self.sp_scu))
        self.sl_scv, self.sp_scv = self._make_pair(
            (10, 400), 100, (0.10, 4.00), 0.01, 2, "×",
            lambda v: v / 100.0, lambda v: int(round(v * 100)))
        form2.addRow(_t("Scale V:"), self._pair(self.sl_scv, self.sp_scv))
        root.addWidget(gb_rs)

        botoes = QHBoxLayout()
        self.btn_reset = QPushButton(_t("Reset"))
        self.btn_reset.clicked.connect(self._on_reset)
        botoes.addWidget(self.btn_reset)
        self.btn_aplicar = QPushButton(_t("Apply"))
        self.btn_aplicar.clicked.connect(self._on_aplicar)
        botoes.addWidget(self.btn_aplicar)
        root.addLayout(botoes)

        self._pair_sync = [
            (self.sl_u, self.sp_u),
            (self.sl_v, self.sp_v),
            (self.sl_rot, self.sp_rot),
            (self.sl_scu, self.sp_scu),
            (self.sl_scv, self.sp_scv),
        ]
        for sl, sp in self._pair_sync:
            sl.valueChanged.connect(self._preview)
            sp.valueChanged.connect(self._on_spin_changed)

        root.addStretch(1)

    def _make_pair(self, slider_range, slider_value, spin_range,
                   spin_step, spin_decimals, spin_suffix,
                   slider_to_spin, spin_to_slider):
        sl = QSlider(Qt.Horizontal)
        sl.setRange(slider_range[0], slider_range[1])
        sl.setValue(slider_value)
        sl.setProperty("_to_spin", slider_to_spin)
        sl.setProperty("_to_slider", spin_to_slider)

        sp = QDoubleSpinBox()
        sp.setRange(spin_range[0], spin_range[1])
        sp.setDecimals(spin_decimals)
        sp.setSingleStep(spin_step)
        sp.setSuffix(spin_suffix)
        sp.setValue(slider_to_spin(slider_value))
        sp.setProperty("_to_spin", slider_to_spin)
        sp.setProperty("_to_slider", spin_to_slider)
        return sl, sp

    def _pair(self, sl, sp):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(sl, 1)
        h.addWidget(sp)
        return w

    def _on_spin_changed(self, _value):
        sp = self.sender()
        for sl, sp2 in self._pair_sync:
            if sp2 is sp:
                to_slider = sl.property("_to_slider")
                sl.blockSignals(True)
                sl.setValue(to_slider(sp.value()))
                sl.blockSignals(False)
                break
        self._preview()

    def _refresh(self):
        faces = selected_faces(self.viewport)
        self._snapshot = {}
        us, vs = [], []
        for f in faces:
            uvw = read_uvw(f)
            if uvw is None:
                if not ensure_uv_texture(f):
                    continue
                uvw = read_uvw(f)
            if uvw is None:
                continue
            self._snapshot[f] = list(uvw)
            pts = face_loop_points(f)
            if not pts:
                continue
            cx, cy, cz = centroid(pts)
            u, v = uv_at(uvw, (cx, cy, cz))
            us.append(u)
            vs.append(v)
        self._faces_atuais = list(self._snapshot.keys())
        self._centro_uv = (
            sum(us) / len(us) if us else 0.0,
            sum(vs) / len(vs) if vs else 0.0,
        )
        n = len(self._faces_atuais)
        self.lbl_sel.setText(_t(
            "{n} face(s) with UV. UV center: ({u:.3f}, {v:.3f})",
            n=n, u=self._centro_uv[0], v=self._centro_uv[1]))
        self._reset_sliders()

    def _on_reset(self):
        if not self._snapshot:
            return
        snap = self._snapshot

        def mutate(scene):
            for f, uvw in snap.items():
                apply_uvw_to_face(f, uvw)

        self.viewport.history.execute(SnapshotImport(mutate))
        self.viewport.notify_scene_changed()
        for sl in (self.sl_u, self.sl_v, self.sl_rot,
                   self.sl_scu, self.sl_scv):
            sl.blockSignals(True)
            sl.setValue(100 if sl in (self.sl_scu, self.sl_scv) else 0)
            sl.blockSignals(False)
        try:
            self.viewport.flash_status(_t("UV adjustments reverted."), 2000)
        except Exception:
            pass

    def _on_aplicar(self):
        if not self._snapshot:
            return
        self._refresh()
        try:
            self.viewport.flash_status(_t("Adjustments applied."), 2000)
        except Exception:
            pass

    def _set_button_state(self, dirty: bool):
        if dirty:
            self.btn_atualizar.setStyleSheet(
                "QPushButton { color: #c0392b; font-weight: bold; }")
            self.btn_atualizar.setToolTip(_t(
                "The viewport selection differs from the one loaded in "
                "the panel.\nClick to synchronize."))
        else:
            self.btn_atualizar.setStyleSheet("")
            self.btn_atualizar.setToolTip(_t(
                "Take a new snapshot of the selection and reset the "
                "sliders."))

    def _check_state(self):
        try:
            atuais = set(selected_faces(self.viewport))
        except Exception:
            return
        snap = set(self._snapshot.keys())
        snap_invalidas = {f for f in snap if not face_valida(f)}
        self._set_button_state((atuais != snap) or bool(snap_invalidas))

    def _read_sliders(self):
        def conv(sl):
            fn = sl.property("_to_spin")
            return fn(sl.value()) if fn else float(sl.value())
        return (conv(self.sl_u), conv(self.sl_v), conv(self.sl_rot),
                conv(self.sl_scu), conv(self.sl_scv))

    def _reset_sliders(self):
        defaults = (
            (self.sl_u, self.sp_u, 0.0),
            (self.sl_v, self.sp_v, 0.0),
            (self.sl_rot, self.sp_rot, 0.0),
            (self.sl_scu, self.sp_scu, 1.0),
            (self.sl_scv, self.sp_scv, 1.0),
        )
        for sl, sp, v in defaults:
            sl.blockSignals(True)
            sp.blockSignals(True)
            sl.setValue(sl.property("_to_slider")(v))
            sp.setValue(v)
            sl.blockSignals(False)
            sp.blockSignals(False)

    def _preview(self, *_):
        for sl, sp in self._pair_sync:
            to_spin = sl.property("_to_spin")
            if to_spin is None:
                continue
            v = to_spin(sl.value())
            sp.blockSignals(True)
            sp.setValue(v)
            sp.blockSignals(False)

        if not self._snapshot:
            return
        du, dv, rot_deg, su, sv = self._read_sliders()
        ang = math.radians(rot_deg)
        ca, sa = math.cos(ang), math.sin(ang)
        cu, cv = self._centro_uv
        snap = self._snapshot

        def mutate(scene):
            for f, uvw0 in snap.items():
                uvw = compose_uvw(uvw0, cu, cv, su, sv, ca, sa, du, dv)
                apply_uvw_to_face(f, uvw)

        self.viewport.history.execute(SnapshotImport(mutate))
        self.viewport.notify_scene_changed()