# =========================================================================
# Pasta: igz-UV/core/
# Arquivo: toolbar.py
# Descrição: Criação da toolbar, submenu e anexo do painel (app.add_panel).
# =========================================================================
import os
import traceback

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon, QPalette
from PySide6.QtWidgets import (
    QWidget, QToolBar, QSizePolicy, QMessageBox, QTabBar,
)

from .mappings import (
    planar_map, spherical_map, cylindrical_map, box_map,
    quad_face_map, tube_map, _t,
)
from .triangulate import triangulate_selection
from .keyboard_tool import UVTransformTool
from .panel import UVAdjustPanel


_PANEL_DOCK = None
_PANEL_TOGGLE = None
_TOOLBAR_CREATED = False
_HERE = None
_ICONS_DIR = None


def _log(s):
    try:
        print(f"[igz-UV] {s}", flush=True)
    except Exception:
        pass


def init(here_dir):
    """Chamado pelo __init__.py para fixar o _HERE e _ICONS_DIR."""
    global _HERE, _ICONS_DIR
    _HERE = here_dir
    icons = os.path.join(here_dir, "icons")
    _ICONS_DIR = icons if os.path.isdir(icons) else None


def _load_themed_icon(base_name: str, main_window) -> QIcon:
    if not _ICONS_DIR:
        return QIcon()
    if base_name.endswith(".svg"):
        base_name = base_name[:-4]
    is_dark = True
    try:
        if main_window is not None:
            bg = main_window.palette().color(QPalette.Window)
            is_dark = bg.lightness() < 128
    except Exception:
        pass
    if not is_dark:
        light = os.path.join(_ICONS_DIR, f"{base_name}_light.svg")
        if os.path.isfile(light):
            return QIcon(light)
    default = os.path.join(_ICONS_DIR, f"{base_name}.svg")
    if os.path.isfile(default):
        return QIcon(default)
    return QIcon()


def find_viewport(main_window):
    if not main_window:
        return None
    if hasattr(main_window, "viewport"):
        return main_window.viewport
    for child in main_window.findChildren(QWidget):
        name = child.__class__.__name__.lower()
        if ("viewport" in name or "gl" in name
                or "canvas" in name or "scene" in name):
            return child
    return None


# --- 3-state helpers (idênticos ao meu_plugin) --------------------------
def _bring_dock_to_front(window, dock):
    if dock is None:
        return
    try:
        siblings = dock.tabifiedDockWidgets()
    except Exception:
        siblings = []
    try:
        for sib in siblings:
            sib.lower()
    except Exception:
        pass
    try:
        dock.setVisible(True)
    except Exception:
        pass
    try:
        dock.raise_()
    except Exception:
        pass
    if siblings:
        try:
            title = dock.windowTitle()
            for tb in window.findChildren(QTabBar):
                for i in range(tb.count()):
                    if tb.tabText(i) == title:
                        tb.setCurrentIndex(i)
                        return
        except Exception:
            pass


def _dock_is_front(dock):
    if dock is None:
        return False
    try:
        if not dock.isVisible():
            return False
    except Exception:
        return False
    try:
        siblings = dock.tabifiedDockWidgets()
    except Exception:
        siblings = []
    return not bool(siblings)


# --- attach panel -------------------------------------------------------
def attach_panel(app, main_window, panel):
    global _PANEL_DOCK, _PANEL_TOGGLE
    add_panel = getattr(app, "add_panel", None)
    if callable(add_panel):
        try:
            dock = add_panel(_t("Adjust UV"), panel,
                             name="igz_uv_adjust", stretch=1)
            _PANEL_DOCK = dock
            _log("painel 'Adjust UV' registrado via app.add_panel.")
            try:
                set_icon = getattr(app, "_set_panel_icon", None)
                icon = _load_themed_icon("uv_panel_tab", main_window)
                if callable(set_icon) and not icon.isNull():
                    set_icon(dock, icon)
                    _log("ícone da aba aplicado.")
            except Exception:
                pass
            try:
                dock.hide()
            except Exception:
                pass
            if hasattr(dock, "toggleViewAction"):
                _PANEL_TOGGLE = dock.toggleViewAction()
            return dock
        except Exception:
            traceback.print_exc()
    _log("app.add_panel indisponível; painel não exibido.")
    return None


# --- toolbar ------------------------------------------------------------
def create_toolbar(main_window, viewport=None, app=None):
    if viewport is None:
        viewport = find_viewport(main_window)

    tb = QToolBar("igz-UV", main_window)
    tb.setObjectName("igz_uv_toolbar")
    tb.setWindowTitle("igz-UV")
    tb.setIconSize(QSize(24, 24))

    def make_action(nome, icone_base, tooltip, cb):
        icon = _load_themed_icon(icone_base, main_window)
        a = QAction(icon, nome, main_window)
        a.setToolTip(tooltip)
        a.setStatusTip(tooltip)
        a.triggered.connect(lambda checked=False: cb())
        return a

    def run(fn):
        return lambda: fn(viewport)

    tb.addAction(make_action(_t("Planar Map"), "uv_planar",
        _t("Planar projection from the current view."), run(planar_map)))
    tb.addAction(make_action(_t("Spherical Map"), "uv_spherical",
        _t("Spherical projection around the selection."),
        run(spherical_map)))
    tb.addAction(make_action(_t("Cylindrical Map"), "uv_cylindrical",
        _t("Cylindrical projection around the Z axis."),
        run(cylindrical_map)))
    tb.addAction(make_action(_t("Box Map"), "uv_box",
        _t("Box projection (each face by its dominant plane)."),
        run(box_map)))
    tb.addAction(make_action(_t("Quad Face Map"), "uv_quad",
        _t("UV (0,0)-(1,1) for quad faces."), run(quad_face_map)))
    tb.addAction(make_action(_t("Tube Map"), "uv_tube",
        _t("Tube projection (U along the perimeter)."), run(tube_map)))

    tb.addSeparator()
    tb.addAction(make_action(_t("Triangulate"), "uv_triangulate",
        _t("Triangulate preserving UVs."), run(triangulate_selection)))
    tb.addSeparator()

    def act_uv_transform():
        vp = viewport
        if vp is None or not hasattr(vp, "set_active_tool"):
            QMessageBox.warning(main_window, "igz-UV",
                                _t("Viewport not found."))
            return
        try:
            tool = UVTransformTool(vp)
        except TypeError:
            tool = UVTransformTool()
        try:
            vp.set_active_tool(tool)
        except Exception:
            traceback.print_exc()

    tb.addAction(make_action(_t("UV Transform"), "uv_transform",
        _t("Interactive UV transform (arrow keys)."), act_uv_transform))

    # Botão do painel (lógica de 3 estados)
    if _PANEL_DOCK is not None:
        icon_panel = _load_themed_icon("uv_panel", main_window)
        action_panel = QAction(icon_panel, _t("Adjust UV"), main_window)
        action_panel.setToolTip(
            _t("Show/hide the fine-tune panel (sliders)."))
        action_panel.setCheckable(True)
        try:
            action_panel.setChecked(_PANEL_DOCK.isVisible())
        except Exception:
            action_panel.setChecked(False)

        def _toggle_or_show(_checked=False):
            try:
                d = _PANEL_DOCK
                if d is None:
                    return
                if _dock_is_front(d):
                    d.hide()
                    return
                _bring_dock_to_front(main_window, d)
                try:
                    w = d.widget()
                    if w is not None:
                        w.setFocus()
                except Exception:
                    pass
                try:
                    main_window.raise_()
                    main_window.activateWindow()
                except Exception:
                    pass
            except Exception as exc:
                _log(f"_toggle_or_show falhou: {exc}")

        action_panel.triggered.connect(_toggle_or_show)
        try:
            _PANEL_DOCK.visibilityChanged.connect(
                action_panel.setChecked)
        except Exception:
            pass
        tb.addAction(action_panel)

    tb.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return tb


# --- setup --------------------------------------------------------------
def setup(app) -> None:
    global _TOOLBAR_CREATED, _PANEL_DOCK
    if _TOOLBAR_CREATED:
        return

    try:
        from PySide6.QtWidgets import QApplication
        mw = None
        qapp = QApplication.instance()
        if qapp is not None:
            for w in qapp.topLevelWidgets():
                if hasattr(w, "addToolBar"):
                    mw = w
                    break
        if mw is None:
            mw = (getattr(app, "main_window", None)
                  or getattr(app, "window", None)
                  or (app if hasattr(app, "addToolBar") else None))
        if mw is None or not hasattr(mw, "addToolBar"):
            _log("setup: main window não encontrada; abortando.")
            return

        vp = find_viewport(mw) or getattr(app, "viewport", None)
        if vp is None:
            _log("setup: viewport não encontrada.")
        else:
            _log(f"setup: viewport = {vp.__class__.__name__}")

        panel = UVAdjustPanel(vp, mw)
        attach_panel(app, mw, panel)

        tb = create_toolbar(mw, vp, app=app)
        mw.addToolBar(Qt.TopToolBarArea, tb)
        _TOOLBAR_CREATED = True
        _log("setup: toolbar 'igz-UV' adicionada.")

        try:
            sub = app.add_menu("igz-UV")
            sub.addAction(_t("Planar Map"), lambda: planar_map(vp))
            sub.addAction(_t("Spherical Map"), lambda: spherical_map(vp))
            sub.addAction(_t("Cylindrical Map"),
                          lambda: cylindrical_map(vp))
            sub.addAction(_t("Box Map"), lambda: box_map(vp))
            sub.addAction(_t("Quad Face Map"), lambda: quad_face_map(vp))
            sub.addAction(_t("Tube Map"), lambda: tube_map(vp))
            sub.addSeparator()
            sub.addAction(_t("Triangulate"),
                          lambda: triangulate_selection(vp))
            sub.addSeparator()
            sub.addAction(_t("UV Transform"),
                          lambda: _activate_uv_transform(vp))
            if _PANEL_TOGGLE is not None:
                sub.addAction(_PANEL_TOGGLE)
        except Exception:
            _log("app.add_menu indisponível; submenu ignorado.")
    except Exception:
        traceback.print_exc()


def _activate_uv_transform(viewport):
    if viewport is None or not hasattr(viewport, "set_active_tool"):
        return
    try:
        viewport.set_active_tool(UVTransformTool(viewport))
    except Exception:
        traceback.print_exc()