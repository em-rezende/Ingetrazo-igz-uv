# =========================================================================
# Extension: igz-UV — UV mapping tools
# Author: Ezequiel M. Rezende
# Date:   2026-10-11
# Version: 1.0.0
# License: GPL-3.0-or-later (same as IngeTrazo)
#
# Inspired by classic UV mapping tools, adapted for IngeTrazo.
#
# Features:
#   • Mappings: planar, spherical, cylindrical, box, quad-face, tube
#   • Triangulation preserving UVs
#   • Interactive UV transform via keyboard (arrow keys)
#   • Side panel with sliders for block fine-tuning
#     (U, V, Rotation, Scale U, Scale V — anisotropic scaling)
#   • Automatic UV grid on untextured faces
#   • i18n: en-US (source), pt-BR, es, it — JSON files in i18n/
#
# IngeTrazo's UV model:
#   • A face's texture lives in face.attrs["texture"] — a dict with
#     {'path', 'sw', 'sh', 'rot', 'uvw'?}. The 'uvw' entry is the
#     affine world→UV transform the renderer applies:
#         u = gu·p + u0
#         v = gv·p + v0
#     in the format [gu.x, gu.y, gu.z, u0, gv.x, gv.y, gv.z, v0].
#   • core.texture exposes planar_uv(), fit_uv_affine(), face_uvs().
#   • Live selection is in scene.selection; face.normal() is a METHOD.
#   • IngeTrazo Tool: on_activate/on_key/on_value ARE called for plugin
#     Tools; on_click/on_hover are NOT.
# =========================================================================

from __future__ import annotations

import json as _json
import math
import os
import sys
import traceback

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QAction, QIcon, QPalette, QVector3D
from PySide6.QtWidgets import (
    QApplication, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QSizePolicy, QSlider, QToolBar,
    QVBoxLayout, QWidget,
)


# -------------------------------------------------------------------------
# LOG DE DIAGNÓSTICO
# -------------------------------------------------------------------------
# Liga/desliga as mensagens de diagnóstico que o plugin emite no stderr
# do IngeTrazo. Útil durante o desenvolvimento; desligue em produção
# trocando para False.
DEBUG = True


def _log(s):
    """Imprime uma mensagem de diagnóstico com o prefixo [igz-UV]."""
    if DEBUG:
        print(f"[igz-UV] {s}", file=sys.stderr, flush=True)


# =========================================================================
# INTERNACIONALIZAÇÃO (i18n) — idioma-fonte: inglês (en-US)
#
# Estratégia em cascata:
#   1. Se o IngeTrazo expõe ``core.i18n.tr``, usa-o primeiro — é o
#      caminho preferido, pois centraliza a tradução no host.
#   2. Senão (ou se o host não tiver a chave), lê os arquivos
#      ``i18n/<lang>.json`` desta extensão.
#   3. Se nada casar, devolve a própria chave (que já é a string-fonte
#      em inglês).
#
# Arquivos em ``igz-UV/i18n/``:
#   • en.json     — vazio (fonte; as chaves SÃO o inglês)
#   • pt-BR.json  — português do Brasil
#   • es.json     — espanhol
#   • it.json     — italiano
#
# Convenções do JSON:
#   • Chave = string-fonte em inglês.
#   • Valor = tradução.
#   • Chaves começando com "_" são metadados e são ignoradas
#     (ex.: "_language").
#   • Aceita `{placeholder}` com str.format().
# =========================================================================
try:
    from core.i18n import tr as _tr_i18n
    from core.i18n import current_language as _current_language
except Exception:  # rodando fora do IngeTrazo
    def _tr_i18n(s, **kw):
        return s.format(**kw) if kw else s

    def _current_language():
        return "en"


#: Cache dos dicionários carregados do disco. Chave = nome do idioma
#: ("pt-BR", "es", "it"). Preenchido sob demanda por ``_load_lang``.
_TEXTS: dict[str, dict] = {}


def _i18n_dir() -> str:
    """Pasta ``i18n/`` ao lado deste arquivo."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "i18n")


def _load_lang(lang: str) -> dict:
    """Carrega ``i18n/<lang>.json`` e devolve o dict de traduções.

    Faz cache em ``_TEXTS`` para não reler o disco a cada chamada.
    Se o arquivo não existir ou estiver malformado, devolve um dict
    vazio (o ``_t`` cai para o inglês-fonte)."""
    if lang in _TEXTS:
        return _TEXTS[lang]
    path = os.path.join(_i18n_dir(), f"{lang}.json")
    if not os.path.isfile(path):
        _TEXTS[lang] = {}
        return _TEXTS[lang]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        if isinstance(data, dict):
            # Ignora metadados (chaves começando com "_").
            data = {k: v for k, v in data.items()
                    if not k.startswith("_")}
        else:
            data = {}
    except Exception:
        _log(f"i18n: falha ao carregar {path}")
        traceback.print_exc()
        data = {}
    _TEXTS[lang] = data
    return data


def _lang_key() -> str:
    """Código do idioma atual.

    Tolerante a variantes:
      • 'pt_BR' → 'pt-BR' (normalização de separador)
      • 'pt-PT' → 'pt-BR' (casamento por base)
      • 'en-US' → 'en'    (cai para a fonte)
    """
    try:
        raw = str(_current_language() or "en").strip().replace("_", "-")
    except Exception:
        return "en"
    if raw in ("en", "pt-BR", "es", "it"):
        return raw
    base = raw.split("-")[0].lower()
    for cand in ("pt-BR", "es", "it"):
        if cand.lower().split("-")[0] == base:
            return cand
    return "en"


def _t(text: str, **kw) -> str:
    """Traduz ``text`` (string-fonte em inglês) para o idioma atual.

    Ordem:
      1. ``core.i18n.tr`` do IngeTrazo (se disponível e devolver algo
         diferente da fonte).
      2. Dicionário local carregado de ``i18n/<lang>.json``.
      3. A própria fonte em inglês.

    Aceita ``{placeholders}`` com ``str.format``."""
    # 1) host
    try:
        x = _tr_i18n(text)
        if isinstance(x, str) and x != text:
            return x.format(**kw) if kw else x
    except Exception:
        pass

    # 2) JSON local
    lang = _lang_key()
    if lang != "en":
        table = _load_lang(lang)
        out = table.get(text, text)
    else:
        out = text

    return out.format(**kw) if kw else out


# -------------------------------------------------------------------------
# DEPENDÊNCIAS DO INGETRAZO
# -------------------------------------------------------------------------
# O plugin é escrito para rodar DENTRO do IngeTrazo, mas cada import é
# protegido para que o módulo também possa ser importado fora (testes,
# linting) sem quebrar.

try:
    # Classe base de todas as ferramentas interativas do IngeTrazo.
    # É uma classe "magra": a interação real do host com ela se dá por
    # métodos com nomes específicos (on_activate, on_key, on_value, ...)
    from tools.base import Tool
except Exception:
    # Stub mínimo para uso fora do IngeTrazo. Não faz nada de útil, mas
    # permite que as subclasses sejam definidas e inspecionadas.
    class Tool:  # type: ignore
        name = ""
        shortcut = None
        description = ""

        def __init__(self, viewport=None):
            self.viewport = viewport


try:
    # SnapshotImport é o mecanismo do IngeTrazo para agrupar mutações
    # num único passo de undo. Passa-se uma função que recebe a cena;
    # o host guarda o estado anterior e aplica/desfaz como um todo.
    from core.history import SnapshotImport
except Exception:
    # Stub para fora do IngeTrazo.
    class SnapshotImport:  # type: ignore
        def __init__(self, fn):
            self.fn = fn


try:
    # Módulo com a matemática de textura do IngeTrazo:
    #   planar_uv(normal, positions, sw, sh, rot) -> [(u, v), ...]
    #   fit_uv_affine(points, uvs) -> [gu.xyz, u0, gv.xyz, v0]
    #   face_uvs(face, tex_dict) -> [(u, v), ...]
    from core import texture as _tex
except Exception:
    _tex = None


# -------------------------------------------------------------------------
# ÍCONES
# -------------------------------------------------------------------------
# Cada ação da toolbar tem um SVG próprio em icons/. O sufixo _light
# indica a variante para tema claro; se não existir, usamos o ícone
# padrão (pensado para tema escuro).

_HERE = os.path.dirname(os.path.abspath(__file__))
_ICONS_DIR = (
    os.path.join(_HERE, "icons")
    if os.path.isdir(os.path.join(_HERE, "icons"))
    else None
)


def _load_themed_icon(base_name: str, main_window) -> QIcon:
    """Carrega o SVG adequado ao tema atual do IngeTrazo.

    Estratégia:
      1. Se o tema é claro e existe <nome>_light.svg, usa esse.
      2. Senão, usa <nome>.svg (pensado para tema escuro).
      3. Se nenhum existe, retorna um QIcon vazio (a ação fica sem ícone).
    """
    if not _ICONS_DIR:
        return QIcon()
    if base_name.endswith(".svg"):
        base_name = base_name[:-4]

    # Decide o tema observando a luminosidade do fundo da janela.
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


# =========================================================================
# UTILIDADES GEOMÉTRICAS
# =========================================================================
# Funções puras, sem dependência do IngeTrazo. Operam sobre tuplas
# (x, y, z) e QVector3D indistintamente; a conversão é feita por _vec3.

def _vec3(p):
    """Normaliza qualquer coisa (QVector3D, objeto com .x()/.y()/.z(),
    ou tupla/lista) para uma tupla de floats (x, y, z)."""
    if isinstance(p, QVector3D):
        return (float(p.x()), float(p.y()), float(p.z()))
    if hasattr(p, "x") and hasattr(p, "y") and hasattr(p, "z"):
        # O IngeTrazo usa tanto propriedades (p.x) quanto métodos (p.x()).
        x = p.x() if callable(p.x) else p.x
        y = p.y() if callable(p.y) else p.y
        z = p.z() if callable(p.z) else p.z
        return (float(x), float(y), float(z))
    x, y, z = p
    return (float(x), float(y), float(z))


def _as_qvec3(p) -> QVector3D:
    """Converte para QVector3D (exigido por algumas APIs do core)."""
    x, y, z = _vec3(p)
    return QVector3D(x, y, z)


def _sub(a, b):
    a, b = _vec3(a), _vec3(b)
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    a, b = _vec3(a), _vec3(b)
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _length(v):
    x, y, z = _vec3(v)
    return math.sqrt(x * x + y * y + z * z)


def _normalize(v):
    l = _length(v)
    if l == 0.0:
        return (0.0, 0.0, 0.0)
    x, y, z = _vec3(v)
    return (x / l, y / l, z / l)


def _centroid(points):
    """Média aritmética dos pontos. Usado como "centro" de uma face
    ou de um conjunto de faces para projeções radiais."""
    n = float(len(points))
    if n == 0:
        return (0.0, 0.0, 0.0)
    cx = cy = cz = 0.0
    for p in points:
        x, y, z = _vec3(p)
        cx += x; cy += y; cz += z
    return (cx / n, cy / n, cz / n)


def _bounding_box(points):
    """Retorna (min_x, min_y, min_z, max_x, max_y, max_z), ou None."""
    if not points:
        return None
    xs, ys, zs = zip(*[_vec3(p) for p in points])
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def _fit_plane(points):
    """Plano médio por triangulação: pega o primeiro triângulo não
    degenerado dos pontos e usa sua normal. Suficiente para escolher o
    eixo dominante no Box Map."""
    if len(points) < 3:
        return ((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    c = _centroid(points)
    for i in range(1, len(points) - 1):
        a = _sub(points[i], points[0])
        b = _sub(points[i + 1], points[0])
        n = _cross(a, b)
        if _length(n) > 1e-9:
            return (_normalize(n), c)
    return ((0.0, 0.0, 1.0), c)


# =========================================================================
# ACESSO AO MODELO DO INGETRAZO
# =========================================================================

def _get_scene(_viewport_or_scene):
    """Aceita um viewport OU um scene e devolve o scene.

    Motivo: algumas funções recebem o viewport (a toolbar passa isso),
    outras recebem o scene (o painel guarda uma referência). Manter as
    duas assinaturas facilita.
    """
    if _viewport_or_scene is None:
        return None
    if type(_viewport_or_scene).__name__ == "Scene":
        return _viewport_or_scene
    return getattr(_viewport_or_scene, "scene", None) or _viewport_or_scene


def _iter_faces(entities):
    """Filtra entidades para apenas as que são faces.

    O IngeTrazo identifica faces pelo nome da classe (`Face`); é o
    mesmo critério que o console expõe em `selection`."""
    for e in entities or []:
        if type(e).__name__ == "Face":
            yield e


def _selected_faces(viewport_or_scene):
    """Faces atualmente selecionadas.

    Importante: a seleção viva mora em `scene.selection`, NÃO em
    `viewport.selection` (esse atributo não existe no viewport do
    IngeTrazo — foi uma fonte de bug durante o desenvolvimento)."""
    scene = _get_scene(viewport_or_scene)
    if scene is None:
        return []
    sel = getattr(scene, "selection", None) or []
    return list(_iter_faces(sel))


def _face_loop_points(face):
    """Vértices do loop EXTERNO da face, em ordem, como tuplas (x, y, z).

    Preferimos `face.loop` (lista de Vertex com `.position`) a
    `face.vertices` (lista de QVector3D diretos), porque a ordem de
    `loop` é garantidamente a ordem do contorno, enquanto a ordem de
    `vertices` pode variar entre versões do IngeTrazo."""
    loop = getattr(face, "loop", None)
    if loop:
        out = []
        for v in loop:
            pos = getattr(v, "position", None)
            if pos is None:
                pos = v
            out.append(_vec3(pos))
        if out:
            return out
    # Fallback: usa face.vertices se loop não existir/estiver vazio.
    verts = getattr(face, "vertices", None) or []
    return [_vec3(p) for p in verts]


def _face_normal(face):
    """Normal da face como tupla (x, y, z).

    Atenção: `face.normal` é MÉTODO no IngeTrazo, não atributo. Esta
    função encapsula a diferença para o resto do código."""
    n = getattr(face, "normal", None)
    if n is None:
        return (0.0, 0.0, 1.0)
    if callable(n):
        n = n()
    return _vec3(n)


def _face_texture(face):
    """Devolve o dict de textura da face, ou None se não houver."""
    if not hasattr(face, "attrs"):
        return None
    t = face.attrs.get("texture")
    if isinstance(t, dict):
        return t
    return None


def _face_valida(face):
    """True se a face ainda existe na cena (não foi removida).

    Usado pelo painel para detectar quando o snapshot está "sujo"
    porque uma face que estava nele foi apagada."""
    try:
        # Acessar face.loop numa face removida levanta exceção no
        # IngeTrazo (o objeto perde a referência ao mesh pai).
        _ = getattr(face, "loop", None)
        return True
    except Exception:
        return False


# -------------------------------------------------------------------------
# GRADE UV AUTOMÁTICA
# -------------------------------------------------------------------------
# Faces sem textura recebem automaticamente o texture_grid.* da pasta
# icons/. Isso permite ver o mapeamento imediatamente sem precisar
# pintar a face antes. O material atribuído chama-se "igz-UV
# Texture" e aparece no registro de materiais do IngeTrazo.

def _uv_grid_path() -> str | None:
    """Localiza o arquivo texture_grid.* na pasta de ícones do plugin."""
    if not _ICONS_DIR:
        return None
    # Ordem de preferência: jpg, png, JPG, jpeg
    for nome in ("texture_grid.jpg", "texture_grid.png",
                 "texture_grid.JPG", "texture_grid.jpeg"):
        p = os.path.join(_ICONS_DIR, nome)
        if os.path.isfile(p):
            return p
    # Fallback: qualquer arquivo começando com "texture_grid."
    try:
        for f in os.listdir(_ICONS_DIR):
            if f.lower().startswith("texture_grid."):
                return os.path.join(_ICONS_DIR, f)
    except Exception:
        pass
    return None


def _ensure_uv_texture(face) -> bool:
    """Garante que a face tem textura. Devolve True se a face tem (ou
    passou a ter) uma textura; False se não foi possível.

    Se a face já tem textura, não mexe em nada (respeita a escolha do
    usuário). Se não tem, atribui a grade UV com sw=sh=1.0."""
    if _face_texture(face) is not None:
        return True
    path = _uv_grid_path()
    if not path:
        return False
    if not hasattr(face, "attrs"):
        return False
    # Copia o dict existente (se houver) para não mutar o original
    # fora do passo de undo.
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


def _apply_uvw_to_face(face, uvw):
    """Grava a transformação afim world→UV na textura da face.

    `uvw` está no formato devolvido por core.texture.fit_uv_affine:
    [gu.x, gu.y, gu.z, u0, gv.x, gv.y, gv.z, v0]."""
    if not hasattr(face, "attrs"):
        return
    tex = face.attrs.get("texture")
    if not isinstance(tex, dict):
        tex = {}
    tex = dict(tex)  # copy para undo seguro
    tex["uvw"] = list(uvw)
    face.attrs["texture"] = tex


def _read_uvw(face):
    """Lê a uvw da face. Devolve uma lista de 8 floats, ou None."""
    tex = _face_texture(face)
    if not tex:
        return None
    uvw = tex.get("uvw")
    if not uvw or len(uvw) != 8:
        return None
    return [float(x) for x in uvw]


# =========================================================================
# MATEMÁTICA: COMPOSIÇÃO DE TRANSFORMAÇÕES EM UV
# =========================================================================

def _uv_at(uvw, p):
    """Aplica a uvw ao ponto do mundo p e devolve o par (u, v).

    É a fórmula afim que o IngeTrazo usa para amostrar a textura:
        u = gu·p + u0
        v = gv·p + v0
    """
    x, y, z = _vec3(p)
    u = uvw[0] * x + uvw[1] * y + uvw[2] * z + uvw[3]
    v = uvw[4] * x + uvw[5] * y + uvw[6] * z + uvw[7]
    return u, v


def _compose_uvw(uvw0, cu, cv, scale_u, scale_v, ca, sa, du, dv):
    """Compõe uma nova uvw aplicando escala, rotação e deslocamento
    em torno do centro UV (cu, cv).

    A escala é anisotrópica: ``scale_u`` atua no eixo U, ``scale_v``
    no eixo V. A rotação (θ) e o offset (du, dv) vêm depois.

    A transformação desejada em coordenadas UV é:
        p_uv  = (u, v) obtido do uvw0 no ponto
        q_uv  = R(θ) · diag(su, sv) · (p_uv − c) + c + (du, dv)

    Como u e v são lineares em world (afins), a composição também é
    afim em world. Resolvemos identificando os coeficientes a partir
    da aplicação da composta em quatro pontos-base do mundo (origem +
    três eixos unitários).
    """
    # Os quatro pontos-base que definem a base do espaço world.
    P0 = (0.0, 0.0, 0.0)
    P1 = (1.0, 0.0, 0.0)
    P2 = (0.0, 1.0, 0.0)
    P3 = (0.0, 0.0, 1.0)

    def composto(P):
        """Aplica a composta (uvw0 → escala U/V → rotação → offset)."""
        u0, v0 = _uv_at(uvw0, P)
        # Escala anisotrópica em torno de (cu, cv)
        u = cu + (u0 - cu) * scale_u
        v = cv + (v0 - cv) * scale_v
        # Rotação em torno de (cu, cv)
        x = u - cu
        y = v - cv
        u = cu + ca * x - sa * y
        v = cv + sa * x + ca * y
        # Deslocamento final
        return (u + du, v + dv)

    u0, v0 = composto(P0)
    u1, v1 = composto(P1)
    u2, v2 = composto(P2)
    u3, v3 = composto(P3)

    # A uvw final tem a forma:
    #   u = gu·p + u0_new
    #   v = gv·p + v0_new
    # As diferenças entre P1..P3 e P0 revelam os componentes de gu e gv.
    gux = u1 - u0
    guy = u2 - u0
    guz = u3 - u0
    gvx = v1 - v0
    gvy = v2 - v0
    gvz = v3 - v0

    return [gux, guy, guz, u0, gvx, gvy, gvz, v0]


# =========================================================================
# NÚCLEO: APLICAR MAPEAMENTO UV
# =========================================================================

def _apply_uv_map(viewport, faces, uv_fn, label):
    """Aplica um mapeamento UV a um conjunto de faces.

    `uv_fn(face, points) -> [(u, v), ...]` deve devolver um par (u, v)
    por vértice do loop externo da face.

    Passos por face:
      1. Garante textura (aplica grade se necessário).
      2. Calcula UVs por vértice.
      3. Encosta um mapa afim (uvw) via fit_uv_affine.
      4. Grava o uvw em face.attrs["texture"]["uvw"].

    Tudo num único SnapshotImport (um passo de undo), e reporta um
    resumo no status bar."""
    if not faces:
        return

    no_tex = []      # faces sem textura e sem grade disponível
    failed = []      # faces cujo fit_uv_affine falhou
    ok = 0

    def mutate(scene):
        nonlocal ok, no_tex, failed
        for f in faces:
            pts = _face_loop_points(f)
            if len(pts) < 3:
                failed.append(f)
                continue
            if not _ensure_uv_texture(f):
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
            _apply_uvw_to_face(f, uvw)
            ok += 1

    viewport.history.execute(SnapshotImport(mutate))
    viewport.notify_scene_changed()

    # Resumo no status bar
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


def _require_faces(viewport):
    """Devolve as faces da seleção, ou avisa (e devolve []) se vazia."""
    faces = _selected_faces(viewport)
    if not faces:
        QMessageBox.information(
            viewport.window, "igz-UV",
            _t("Select at least one face."),
        )
    return faces


# =========================================================================
# CÁLCULO DE UVS (POR TIPO DE PROJEÇÃO)
# =========================================================================

def _planar_uvs(pts, normal, sw, sh, rot=0.0):
    """Projeção planar. Usa a API do IngeTrazo (que respeita a base
    .skp) quando disponível; senão cai para bbox normalizada."""
    if _tex is not None and hasattr(_tex, "planar_uv"):
        return _tex.planar_uv(_as_qvec3(normal), [_as_qvec3(p) for p in pts],
                              sw, sh, rot)
    # Fallback independente do host: usa bbox e normaliza em [0, 1].
    bb = _bounding_box(pts)
    if bb is None:
        return [(0.0, 0.0)] * len(pts)
    min_x, min_y, _, max_x, max_y, _ = bb
    w = max(1e-9, max_x - min_x)
    h = max(1e-9, max_y - min_y)
    return [((p[0] - min_x) / w, (p[1] - min_y) / h) for p in pts]


def _spherical_uvs(pts, center):
    """Coordenadas esféricas: phi (azimute) vira U, theta (polar) vira V."""
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
    """Coordenadas cilíndricas: phi vira U, altura vira V."""
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
    """Corrige o "loop" de U em projeções que dão a volta.

    Quando a projeção cobre os 360°, alguns vértices ficam com u ~0.0
    e outros com u ~1.0, criando uma "costura" visível. Aqui
    deslocamos os u's próximos de 0 para ~1, alinhando com o lado
    oposto da costura."""
    if not uvs:
        return uvs
    u_max = max(u for u, _ in uvs)
    out = []
    for u, v in uvs:
        if u != u_max and (u_max - u) > 0.8:
            u += 1.0
        out.append((u, v))
    return out


# =========================================================================
# COMANDOS PÚBLICOS DE MAPEAMENTO
# =========================================================================

def planar_map(viewport):
    """Projeção planar pela vista/normal da face."""
    faces = _require_faces(viewport)
    if not faces:
        return
    def fn(face, pts):
        tex = _face_texture(face) or {}
        sw = float(tex.get("sw", 1.0) or 1.0)
        sh = float(tex.get("sh", 1.0) or 1.0)
        rot = float(tex.get("rot", 0.0) or 0.0)
        return _planar_uvs(pts, _face_normal(face), sw, sh, rot)
    _apply_uv_map(viewport, faces, fn, "Planar Map")


def spherical_map(viewport):
    """Projeção esférica em torno do centroide da seleção."""
    faces = _require_faces(viewport)
    if not faces:
        return
    all_pts = []
    for f in faces:
        all_pts.extend(_face_loop_points(f))
    center = _centroid(all_pts)
    def fn(face, pts):
        return _validate_uvs(_spherical_uvs(pts, center))
    _apply_uv_map(viewport, faces, fn, "Spherical Map")


def cylindrical_map(viewport):
    """Projeção cilíndrica em torno do eixo Z global."""
    faces = _require_faces(viewport)
    if not faces:
        return
    all_pts = []
    for f in faces:
        all_pts.extend(_face_loop_points(f))
    bb = _bounding_box(all_pts)
    if bb is None:
        return
    # z_extents para o V: zmax no "topo", zmin na "base"
    z_min, z_max = bb[2], bb[5]
    z_extents = (z_max, z_min)
    center = _centroid(all_pts)
    def fn(face, pts):
        return _validate_uvs(_cylindrical_uvs(pts, z_extents, center))
    _apply_uv_map(viewport, faces, fn, "Cylindrical Map")


def box_map(viewport):
    """Mapeamento caixa: cada face vai para o plano dominante (XY, XZ
    ou YZ), escolhido pela maior componente da normal. O sentido da
    normal decide o espelhamento, para a textura não sair invertida nas
    faces de fundo, esquerda e trás."""
    faces = _require_faces(viewport)
    if not faces:
        return
    all_pts = []
    for f in faces:
        all_pts.extend(_face_loop_points(f))
    bb = _bounding_box(all_pts)
    if bb is None:
        return
    min_x, min_y, min_z, max_x, max_y, max_z = bb
    # Normaliza pela maior dimensão para não estourar a textura.
    size = max(max_x - min_x, max_y - min_y, max_z - min_z)
    if size <= 0.0:
        size = 1.0
    def fn(face, pts):
        # Normal de fora da face: define o plano dominante E o sentido da
        # projeção. Sem o sentido, as faces com normal negativa (base,
        # esquerda e trás) sairiam espelhadas. Preferimos a normal do
        # IngeTrazo; se ela não vier, caímos no plano médio por
        # triangulação.
        n = _face_normal(face)
        if _length(n) <= 1e-9:
            n, _c = _fit_plane(pts)
        ax, ay, az = abs(n[0]), abs(n[1]), abs(n[2])
        if ax >= ay and ax >= az:
            # Face "de lado" no eixo X → projeta em YZ. Em -X o Y corre
            # ao contrário na tela, então espelhamos o U.
            if n[0] >= 0.0:
                return [((p[1] - min_y) / size, (p[2] - min_z) / size)
                        for p in pts]
            return [((max_y - p[1]) / size, (p[2] - min_z) / size)
                    for p in pts]
        if ay >= ax and ay >= az:
            # Face "de frente" no eixo Y → projeta em XZ. Em +Y o X corre
            # ao contrário na tela, então espelhamos o U.
            if n[1] >= 0.0:
                return [((max_x - p[0]) / size, (p[2] - min_z) / size)
                        for p in pts]
            return [((p[0] - min_x) / size, (p[2] - min_z) / size)
                    for p in pts]
        # Face "horizontal" → projeta em XY. Em -Z o X corre ao contrário
        # na tela, então espelhamos o U.
        if n[2] >= 0.0:
            return [((p[0] - min_x) / size, (p[1] - min_y) / size)
                    for p in pts]
        return [((max_x - p[0]) / size, (p[1] - min_y) / size)
                for p in pts]
    _apply_uv_map(viewport, faces, fn, "Box Map")


def quad_face_map(viewport):
    """UVs (0,0)-(1,0)-(1,1)-(0,1) em faces de quatro vértices."""
    faces = [f for f in _require_faces(viewport)
             if len(getattr(f, "vertices", None) or []) == 4]
    if not faces:
        QMessageBox.information(viewport.window, "igz-UV",
                                _t("Select quad faces (4 vertices)."))
        return
    quad_uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    def fn(face, pts):
        return quad_uvs[:len(pts)]
    _apply_uv_map(viewport, faces, fn, "Quad Face Map")


def tube_map(viewport):
    """Mapeamento tubo: percorre o perímetro das faces em ordem,
    avançando U a cada face. V é 0 na metade "inferior" do contorno e
    1 na metade "superior" — aproximação razoável para cadeias
    regulares de faces."""
    faces = _require_faces(viewport)
    if not faces:
        return
    # Ordena por centroide para dar uma sequência determinística.
    ordered = sorted(faces, key=lambda f: _centroid(_face_loop_points(f)))
    state = {"u": 0.0}  # U acumulado entre chamadas de fn
    def fn(face, pts):
        # Comprimento total do contorno da face
        per = 0.0
        n = len(pts)
        for i in range(n):
            per += _length(_sub(pts[i], pts[(i + 1) % n]))
        u0 = state["u"]
        state["u"] += per
        u1 = state["u"]
        # Distribui U ao longo do contorno; V binário pelas metades.
        out = []
        acc = 0.0
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            seg = _length(_sub(a, b))
            u = u0 + (acc / per if per > 0 else 0.0) * (u1 - u0)
            v = 0.0 if i < n / 2.0 else 1.0
            out.append((u, v))
            acc += seg
        return out
    _apply_uv_map(viewport, ordered, fn, "Tube Map")


# =========================================================================
# TRIANGULAÇÃO (LEQUE) PRESERVANDO UVS
# =========================================================================

def triangulate_selection(viewport):
    """Divide cada face selecionada em triângulos (leque a partir do
    primeiro vértice), reprojetando as UVs para que a textura
    permaneça idêntica após o corte.

    Estratégia:
      1. Lê as UVs atuais por vértice via core.texture.face_uvs.
      2. Para cada triângulo, reencaixa um uvw independente com
         fit_uv_affine (assim cada triângulo tem seu próprio mapa,
         evitando "esticos" nas diagonais).
      3. Remove a face original.
    """
    faces = _require_faces(viewport)
    if not faces:
        return
    def mutate(scene):
        for f in faces:
            pts = _face_loop_points(f)
            if len(pts) <= 3:
                continue  # já é triângulo; nada a fazer
            tex = _face_texture(f)
            if tex is None:
                if not _ensure_uv_texture(f):
                    continue
                tex = _face_texture(f) or {}
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
                nf = mesh.add_face([_as_qvec3(p) for p in tri_pts])
                if nf is None:
                    continue
                if hasattr(nf, "attrs"):
                    if keep_tex:
                        nf.attrs["texture"] = dict(keep_tex)
                    if keep_mat is not None:
                        nf.attrs["mat"] = keep_mat
                # Reencaixa a uvw triângulo a triângulo
                try:
                    uvw = _tex.fit_uv_affine(tri_pts, tri_uvs)
                    if uvw is not None:
                        _apply_uvw_to_face(nf, uvw)
                except Exception:
                    pass
            # Remove a face original (já foi substituída pela fan)
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


# =========================================================================
# FERRAMENTA INTERATIVA: UV TRANSFORM (TECLADO)
# =========================================================================

class UVTransformTool(Tool):
    """Transformação interativa de UVs via teclado.

    Protocolo de Tool do IngeTrazo:
      • on_activate(viewport)    — chamado ao entrar na ferramenta
      • on_deactivate(viewport)  — chamado ao sair
      • on_key(viewport, key, mods) -> bool   — tecla; True consome
      • on_value(viewport, value) -> bool     — VCB numérico

    Importante: on_click/on_hover NÃO são chamados para Tools de
    plugin no IngeTrazo 0.x (foi verificado empiricamente). Por isso
    a interação é toda por teclado/VCB.
    """

    # Metadados lidos pelo host para exibir em menus e status bar.
    name = "UV Transform"
    description = "Setas movem/escalam/rotacionam as UVs das faces selecionadas."
    status_clause = "Setas: mover · Shift+setas: escalar · Ctrl+setas: rotacionar"
    vcb_label = "UV"
    shortcut = None
    shortcut_alt = None
    uses_snap = False
    icon = None

    def __init__(self, viewport=None):
        # Passos de deslocamento/escala/rotação por tecla.
        self._nudge = 0.05
        self._scale_nudge = 1.05
        self._rotate_nudge = 1.0

    def on_activate(self, viewport):
        try:
            viewport.flash_status(
                _t("UV Transform: use the arrow keys (Shift=scale, "
                   "Ctrl=rotate)."),
                4000)
        except Exception:
            pass

    def on_deactivate(self, viewport):
        # Sem estado a limpar; a ferramenta é stateless.
        pass

    def on_key(self, viewport, key, modifiers):
        """Trata as teclas de seta e combinações com Shift/Ctrl."""
        faces = _selected_faces(viewport)
        if not faces:
            return False
        shift = bool(modifiers & Qt.ShiftModifier)
        ctrl = bool(modifiers & Qt.ControlModifier)
        handled = True
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
            handled = False
        return handled

    def on_value(self, viewport, value):
        """VCB numérico. -180..180 vira graus; > 0 vira fator de escala."""
        faces = _selected_faces(viewport)
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
        # Nada a cancelar — cada tecla já é aplicada como passo de undo.
        pass

    # ---- Operações elementares ----------------------------------------
    # Cada uma abre seu próprio SnapshotImport e chama notify_scene_changed.

    def _offset(self, viewport, faces, du, dv):
        """Desloca a imagem nas direções U e V (componentes do offset)."""
        def mutate(scene):
            for f in faces:
                if not _ensure_uv_texture(f):
                    continue
                uvw = _read_uvw(f)
                if uvw is None:
                    uvw = [0.0] * 8
                uvw[3] += du  # u0
                uvw[7] += dv  # v0
                _apply_uvw_to_face(f, uvw)
        viewport.history.execute(SnapshotImport(mutate))
        viewport.notify_scene_changed()

    def _scale(self, viewport, faces, su, sv):
        """Escala U e V. Multiplica os gradientes gu e gv, mantendo
        as origens (u0, v0)."""
        def mutate(scene):
            for f in faces:
                if not _ensure_uv_texture(f):
                    continue
                uvw = _read_uvw(f)
                if uvw is None:
                    continue
                uvw[0] *= su; uvw[1] *= su; uvw[2] *= su
                uvw[4] *= sv; uvw[5] *= sv; uvw[6] *= sv
                _apply_uvw_to_face(f, uvw)
        viewport.history.execute(SnapshotImport(mutate))
        viewport.notify_scene_changed()

    def _rotate(self, viewport, faces, degrees):
        """Rotaciona gu e gv no plano UV (em torno de (0, 0) de UV).

        Essa rotação é local à face — diferente da rotação do painel,
        que é em torno do centro comum da seleção. Foi a limitação
        original que motivou o painel de ajuste fino."""
        a = math.radians(degrees)
        ca, sa = math.cos(a), math.sin(a)
        def mutate(scene):
            for f in faces:
                if not _ensure_uv_texture(f):
                    continue
                uvw = _read_uvw(f)
                if uvw is None:
                    continue
                gx, gy, gz = uvw[0], uvw[1], uvw[2]
                hx, hy, hz = uvw[4], uvw[5], uvw[6]
                # Rotação 2D dos gradientes
                uvw[0] = ca * gx - sa * hx
                uvw[1] = ca * gy - sa * hy
                uvw[2] = ca * gz - sa * hz
                uvw[4] = sa * gx + ca * hx
                uvw[5] = sa * gy + ca * hy
                uvw[6] = sa * gz + ca * hz
                _apply_uvw_to_face(f, uvw)
        viewport.history.execute(SnapshotImport(mutate))
        viewport.notify_scene_changed()


# =========================================================================
# PAINEL: AJUSTE FINO (SLIDERS)
# =========================================================================

class UVAdjustPanel(QWidget):
    """Painel lateral com sliders para ajuste fino em BLOCO.

    Diferença central em relação ao UVTransformTool (teclado):
      • O teclado gira cada face em torno do seu próprio (0,0) de UV.
      • O painel gira TODA a seleção em torno do centro UV comum,
        mantendo a imagem coesa (é o comportamento que se espera de
        uma ferramenta de ajuste de textura).

    Modelo:
      • Ao abrir (ou ao clicar em "Recarregar"), o painel tira um
        snapshot {face: uvw0} da seleção e calcula o centro UV comum.
      • Os sliders são DELTAS relativos a esse snapshot.
      • Cada movimento de slider aplica a composição em cima do
        snapshot (não do estado anterior) — por isso voltar os
        sliders a zero restaura as UVs originais.
      • "Reset" reaplica o snapshot; "Aplicar" promove o estado atual
        a novo snapshot e zera os sliders.

    Sliders disponíveis:
      • U (offset horizontal)
      • V (offset vertical)
      • Rotation (graus)
      • Scale U (escala anisotrópica no eixo U)
      • Scale V (escala anisotrópica no eixo V)
    """

    def __init__(self, viewport, parent=None):
        super().__init__(parent)
        self.viewport = viewport
        self._snapshot = {}       # {face: [uvw0]} — UVs de referência
        self._centro_uv = (0.0, 0.0)  # centro comum em coordenadas UV
        self._faces_atuais = []   # lista ordenada das faces no snapshot
        self._build()
        self._refresh()

        # Timer que verifica se a seleção divergiu do snapshot, para
        # acender o botão "Recarregar" em vermelho. Roda em 400 ms;
        # barato, porque só percorre scene.selection.
        self._state_timer = QTimer(self)
        self._state_timer.setInterval(400)
        self._state_timer.timeout.connect(self._check_state)
        self._state_timer.start()

    # ------------------------------------------------------------------
    def _build(self):
        """Monta a UI do painel."""
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Cabeçalho
        hint = QLabel(
            "<b>" + _t("Fine-tune UVs") + "</b><br>"
            "<i>" + _t("Move the sliders; click Apply to confirm.") + "</i>"
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        # Linha informativa: quantas faces e onde é o centro UV
        self.lbl_sel = QLabel("")
        self.lbl_sel.setWordWrap(True)
        self.lbl_sel.setStyleSheet("color: #888; font-size: 10px;")
        root.addWidget(self.lbl_sel)

        # Botão que tira novo snapshot da seleção atual
        self.btn_atualizar = QPushButton(_t("Reload from current selection"))
        self.btn_atualizar.setToolTip(
            _t("Take a new snapshot of the selection and reset the sliders.")
        )
        self.btn_atualizar.clicked.connect(self._refresh)
        root.addWidget(self.btn_atualizar)

        # -------- Grupo: deslocamento em U e V ----------------------
        gb_off = QGroupBox(_t("Offset"))
        form = QFormLayout(gb_off)

        # U e V: slider em centésimos (-200..200) → spin em unidades
        # (-2.00..2.00). Guardamos as funções de conversão como
        # properties no próprio widget, para o _preview poder
        # sincronizar spin ↔ slider sem precisar reconfigurar.
        self.sl_u, self.sp_u = self._make_pair(
            slider_range=(-200, 200), slider_value=0,
            spin_range=(-2.0, 2.0), spin_step=0.01, spin_decimals=2,
            spin_suffix="", slider_to_spin=lambda v: v / 100.0,
            spin_to_slider=lambda v: int(round(v * 100)),
        )
        form.addRow("U:", self._pair(self.sl_u, self.sp_u))

        self.sl_v, self.sp_v = self._make_pair(
            slider_range=(-200, 200), slider_value=0,
            spin_range=(-2.0, 2.0), spin_step=0.01, spin_decimals=2,
            spin_suffix="", slider_to_spin=lambda v: v / 100.0,
            spin_to_slider=lambda v: int(round(v * 100)),
        )
        form.addRow("V:", self._pair(self.sl_v, self.sp_v))

        root.addWidget(gb_off)

        # -------- Grupo: rotação e escalas --------------------------
        gb_rs = QGroupBox(_t("Rotation and scale"))
        form2 = QFormLayout(gb_rs)

        # Rotação: slider em décimos de grau (-1800..1800)
        # → spin de -180.0° a 180.0°.
        self.sl_rot, self.sp_rot = self._make_pair(
            slider_range=(-1800, 1800), slider_value=0,
            spin_range=(-180.0, 180.0), spin_step=0.1, spin_decimals=1,
            spin_suffix="°", slider_to_spin=lambda v: v / 10.0,
            spin_to_slider=lambda v: int(round(v * 10)),
        )
        form2.addRow(_t("Rotation:"), self._pair(self.sl_rot, self.sp_rot))

        # Escala U: slider em centésimos (10..400) → 0.10× a 4.00×
        self.sl_scu, self.sp_scu = self._make_pair(
            slider_range=(10, 400), slider_value=100,
            spin_range=(0.10, 4.00), spin_step=0.01, spin_decimals=2,
            spin_suffix="×", slider_to_spin=lambda v: v / 100.0,
            spin_to_slider=lambda v: int(round(v * 100)),
        )
        form2.addRow(_t("Scale U:"), self._pair(self.sl_scu, self.sp_scu))

        # Escala V: slider em centésimos (10..400) → 0.10× a 4.00×
        self.sl_scv, self.sp_scv = self._make_pair(
            slider_range=(10, 400), slider_value=100,
            spin_range=(0.10, 4.00), spin_step=0.01, spin_decimals=2,
            spin_suffix="×", slider_to_spin=lambda v: v / 100.0,
            spin_to_slider=lambda v: int(round(v * 100)),
        )
        form2.addRow(_t("Scale V:"), self._pair(self.sl_scv, self.sp_scv))

        root.addWidget(gb_rs)

        # -------- Botões Reset / Aplicar ----------------------------
        botoes = QHBoxLayout()
        self.btn_reset = QPushButton(_t("Reset"))
        self.btn_reset.clicked.connect(self._on_reset)
        botoes.addWidget(self.btn_reset)
        self.btn_aplicar = QPushButton(_t("Apply"))
        self.btn_aplicar.clicked.connect(self._on_aplicar)
        botoes.addWidget(self.btn_aplicar)
        root.addLayout(botoes)

        # Lista dos pares (slider, spinbox) para sincronização
        # automática quando um dos dois muda.
        self._pair_sync = [
            (self.sl_u,    self.sp_u),
            (self.sl_v,    self.sp_v),
            (self.sl_rot,  self.sp_rot),
            (self.sl_scu,  self.sp_scu),
            (self.sl_scv,  self.sp_scv),
        ]
        for sl, sp in self._pair_sync:
            sl.valueChanged.connect(self._preview)
            sp.valueChanged.connect(self._on_spin_changed)

        root.addStretch(1)

    def _make_pair(self, slider_range, slider_value, spin_range,
                   spin_step, spin_decimals, spin_suffix,
                   slider_to_spin, spin_to_slider):
        """Cria (QSlider, QDoubleSpinBox) coerentes, guardando as funções
        de conversão como properties nos widgets para reuso depois."""
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
        """Empacota slider + spinbox num mesmo widget horizontal."""
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(sl, 1)
        h.addWidget(sp)
        return w

    def _on_spin_changed(self, _value):
        """A spinbox mudou: empurra para o slider e dispara o preview.
        É a metade 'spin → slider' da sincronização; a outra metade
        ('slider → spin') vive no _preview."""
        sp = self.sender()
        for sl, sp2 in self._pair_sync:
            if sp2 is sp:
                to_slider = sl.property("_to_slider")
                sl.blockSignals(True)
                sl.setValue(to_slider(sp.value()))
                sl.blockSignals(False)
                break
        self._preview()

    # ------------------------------------------------------------------
    def _refresh(self):
        """Tira novo snapshot da seleção atual e zera os sliders.

        Chamado no __init__, no clique do botão "Recarregar" e no
        "Aplicar" (para promover o estado atual a novo snapshot)."""
        faces = _selected_faces(self.viewport)
        self._snapshot = {}
        us, vs = [], []
        for f in faces:
            uvw = _read_uvw(f)
            if uvw is None:
                # Sem UV ainda: aplica grade e tenta ler de novo.
                if not _ensure_uv_texture(f):
                    continue
                uvw = _read_uvw(f)
            if uvw is None:
                continue
            self._snapshot[f] = list(uvw)
            # Centro UV da face = (u, v) do centroide geométrico dela.
            # A média desses centros vira o centro comum da seleção.
            pts = _face_loop_points(f)
            if not pts:
                continue
            cx, cy, cz = _centroid(pts)
            u, v = _uv_at(uvw, (cx, cy, cz))
            us.append(u); vs.append(v)
        self._faces_atuais = list(self._snapshot.keys())
        self._centro_uv = (
            sum(us) / len(us) if us else 0.0,
            sum(vs) / len(vs) if vs else 0.0,
        )
        n = len(self._faces_atuais)
        self.lbl_sel.setText(_t(
            "{n} face(s) with UV. UV center: ({u:.3f}, {v:.3f})",
            n=n, u=self._centro_uv[0], v=self._centro_uv[1],
        ))
        self._reset_sliders()

    # ------------------------------------------------------------------
    def _on_reset(self):
        """Desfaz o preview atual (reaplica o snapshot) e zera sliders."""
        if not self._snapshot:
            return
        snap = self._snapshot

        def mutate(scene):
            for f, uvw in snap.items():
                _apply_uvw_to_face(f, uvw)

        self.viewport.history.execute(SnapshotImport(mutate))
        self.viewport.notify_scene_changed()
        # Zera os sliders SEM disparar preview (senão reaplicaria).
        # Escalas voltam a 100 (= 1.00×); os demais a 0.
        for sl in (self.sl_u, self.sl_v, self.sl_rot,
                   self.sl_scu, self.sl_scv):
            sl.blockSignals(True)
            if sl in (self.sl_scu, self.sl_scv):
                sl.setValue(100)
            else:
                sl.setValue(0)
            sl.blockSignals(False)
        try:
            self.viewport.flash_status(_t("UV adjustments reverted."), 2000)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _on_aplicar(self):
        """Promove o estado atual a novo snapshot.

        A cena já está atualizada (o _preview aplicou); aqui só
        tiramos um novo snapshot e zeramos os sliders, para o usuário
        poder continuar ajustando a partir do novo ponto."""
        if not self._snapshot:
            return
        self._refresh()
        try:
            self.viewport.flash_status(_t("Adjustments applied."), 2000)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _set_button_state(self, dirty: bool):
        """Pinta o texto do botão 'Recarregar' em vermelho se dirty."""
        if dirty:
            self.btn_atualizar.setStyleSheet(
                "QPushButton { color: #c0392b; font-weight: bold; }"
            )
            self.btn_atualizar.setToolTip(_t(
                "The viewport selection differs from the one loaded in "
                "the panel.\nClick to synchronize."))
        else:
            self.btn_atualizar.setStyleSheet("")
            self.btn_atualizar.setToolTip(_t(
                "Take a new snapshot of the selection and reset the "
                "sliders."))

    def _check_state(self):
        """Compara a seleção viva com o snapshot; acende o botão se
        divergirem. Chamado a cada 400 ms pelo QTimer."""
        try:
            atuais = set(_selected_faces(self.viewport))
        except Exception:
            return
        snap = set(self._snapshot.keys())
        # Face removida do documento também deixa o snapshot sujo.
        snap_invalidas = {f for f in snap if not _face_valida(f)}
        dirty = (atuais != snap) or bool(snap_invalidas)
        self._set_button_state(dirty)

    # ------------------------------------------------------------------
    def _read_sliders(self):
        """Lê os valores atuais dos sliders já convertidos para unidade
        real (usando as funções guardadas nas properties).

        Devolve (du, dv, rot_deg, scale_u, scale_v)."""
        def conv(sl):
            fn = sl.property("_to_spin")
            return fn(sl.value()) if fn else float(sl.value())
        return (
            conv(self.sl_u),
            conv(self.sl_v),
            conv(self.sl_rot),
            conv(self.sl_scu),
            conv(self.sl_scv),
        )

    def _reset_sliders(self):
        """Volta todos os sliders/spin ao neutro (0, 0, 0°, 1×, 1×)."""
        defaults = (
            (self.sl_u,    self.sp_u,    0.0),
            (self.sl_v,    self.sp_v,    0.0),
            (self.sl_rot,  self.sp_rot,  0.0),
            (self.sl_scu,  self.sp_scu,  1.0),
            (self.sl_scv,  self.sp_scv,  1.0),
        )
        for sl, sp, v in defaults:
            sl.blockSignals(True); sp.blockSignals(True)
            sl.setValue(sl.property("_to_slider")(v))
            sp.setValue(v)
            sl.blockSignals(False); sp.blockSignals(False)

    def _preview(self, *_):
        """Aplica em tempo real a composição (snapshot + sliders).

        Duas etapas:
          1. Sincroniza as spinboxes com os sliders (slider → spin).
             O sentido inverso é tratado em _on_spin_changed.
          2. Compõe a transformação em torno do centro comum e
             escreve as novas uvw nas faces do snapshot.
        """
        # 1) slider → spin
        for sl, sp in self._pair_sync:
            to_spin = sl.property("_to_spin")
            if to_spin is None:
                continue
            v = to_spin(sl.value())
            sp.blockSignals(True)
            sp.setValue(v)
            sp.blockSignals(False)

        # 2) aplica a composição na cena
        if not self._snapshot:
            return
        du, dv, rot_deg, su, sv = self._read_sliders()
        ang = math.radians(rot_deg)
        ca, sa = math.cos(ang), math.sin(ang)
        cu, cv = self._centro_uv
        snap = self._snapshot

        def mutate(scene):
            for f, uvw0 in snap.items():
                uvw = _compose_uvw(uvw0, cu, cv, su, sv, ca, sa, du, dv)
                _apply_uvw_to_face(f, uvw)

        self.viewport.history.execute(SnapshotImport(mutate))
        self.viewport.notify_scene_changed()


# =========================================================================
# AJUDA
# =========================================================================

def show_help(viewport):
    """Diálogo de ajuda (acessível apenas pelo menu Extensions ▸ igz-UV).

    Escolhe um parent que seja, de fato, um QWidget. `viewport.window`
    pode devolver o ExtensionApp do host, que não é um QWidget e faria
    o QMessageBox falhar silenciosamente."""
    parent = None
    try:
        parent = QApplication.activeWindow()
    except Exception:
        parent = None
    if parent is None:
        # Fallback: tenta o `window` do viewport, mas só aceita se for
        # um QWidget de verdade.
        cand = getattr(viewport, "window", None) if viewport else None
        if cand is not None and hasattr(cand, "isWidgetType") \
                and cand.isWidgetType():
            parent = cand

    corpo = "\n\n".join([
        _t("UV mapping for IngeTrazo"),
        _t("1. Paint the face(s) with a texture (Paint → Texture).\n"
           "   Without a texture, the UV grid is applied automatically."),
        _t("2. Select the face(s)."),
        _t("3. Choose a mapping on the toolbar (or the menu):\n"
           "   • Planar (View), Spherical, Cylindrical\n"
           "   • Box, Quad Face, Tube"),
        _t("4. Fine-tuning:\n"
           "   • Side panel 'Adjust UV' has sliders for U, V,\n"
           "     rotation and scale (U and V separately) — they act in\n"
           "     BLOCK, rotating all faces around the selection's common\n"
           "     center.\n"
           "   • UV Transform (arrow keys): adjusts each face\n"
           "     individually. Shift=scale, Ctrl=rotate, digits in the VCB."),
        _t("5. 'Triangulate' splits faces into triangles preserving UVs."),
    ])
    QMessageBox.information(parent, _t("igz-UV — Help"), corpo)


# =========================================================================
# TOOLBAR E MENU
# =========================================================================

# Estado global do plugin, para evitar recriar toolbar/painel.
_TOOLBAR_CREATED = False
_PANEL_DOCK = None
_PANEL_TOGGLE = None


def find_viewport(main_window):
    """Localiza o widget do viewport 3D a partir da main window.

    Estratégia: tenta o atributo `viewport` (que o IngeTrazo expõe) e,
    se não houver, procura entre os filhos por nome de classe que
    contenha 'viewport', 'gl', 'canvas' ou 'scene'."""
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


def _make_action(main_window, nome, icone_base, tooltip, callback):
    """Cria um QAction com ícone temático, tooltip e callback."""
    icon = _load_themed_icon(icone_base, main_window)
    a = QAction(icon, nome, main_window)
    a.setToolTip(tooltip)
    a.setStatusTip(tooltip)
    a.triggered.connect(lambda checked=False: callback())
    return a


def create_toolbar(main_window, viewport=None, app=None):
    """Constrói a toolbar igz-UV e devolve-a (sem adicionar à janela;
    quem adiciona é o setup(app))."""
    if viewport is None:
        viewport = find_viewport(main_window)

    tb = QToolBar("igz-UV", main_window)
    tb.setObjectName("igz_uv_toolbar")
    tb.setWindowTitle("igz-UV")
    tb.setIconSize(QSize(24, 24))

    def run(fn):
        return lambda: fn(viewport)

    # --- Mapeamentos ---------------------------------------------------
    tb.addAction(_make_action(main_window, _t("Planar Map"), "uv_planar",
        _t("Planar projection from the current view."), run(planar_map)))
    tb.addAction(_make_action(main_window, _t("Spherical Map"), "uv_spherical",
        _t("Spherical projection around the selection."),
        run(spherical_map)))
    tb.addAction(_make_action(main_window, _t("Cylindrical Map"),
        "uv_cylindrical",
        _t("Cylindrical projection around the Z axis."),
        run(cylindrical_map)))
    tb.addAction(_make_action(main_window, _t("Box Map"), "uv_box",
        _t("Box projection (each face by its dominant plane)."),
        run(box_map)))
    tb.addAction(_make_action(main_window, _t("Quad Face Map"), "uv_quad",
        _t("UV (0,0)-(1,1) for quad faces."),
        run(quad_face_map)))
    tb.addAction(_make_action(main_window, _t("Tube Map"), "uv_tube",
        _t("Tube projection (U along the perimeter)."),
        run(tube_map)))

    tb.addSeparator()

    # --- Triangulação --------------------------------------------------
    tb.addAction(_make_action(main_window, _t("Triangulate"), "uv_triangulate",
        _t("Triangulate preserving UVs."), run(triangulate_selection)))

    tb.addSeparator()

    # --- Ferramenta interativa (UV Transform) --------------------------
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

    tb.addAction(_make_action(main_window, _t("UV Transform"), "uv_transform",
        _t("Interactive UV transform (arrow keys)."), act_uv_transform))

    # --- Botão do painel de ajuste fino --------------------------------
    # Usa o toggleViewAction() do dock, que o IngeTrazo já sincroniza
    # com a visibilidade real (faz o botão "afundar" quando o painel
    # está visível, e alterna mostrar/ocultar ao clicar).
    if _PANEL_TOGGLE is not None:
        act = _PANEL_TOGGLE
        act.setIcon(_load_themed_icon("uv_panel", main_window))
        act.setText(_t("Adjust UV"))
        act.setToolTip(_t("Show/hide the fine-tune panel (sliders)."))
        tb.addAction(act)
    else:
        # Fallback: dock sem toggleViewAction — abre pelo app.
        def show_adjust_panel():
            if _PANEL_DOCK is not None and app is not None:
                try:
                    app.show_panel(_PANEL_DOCK)
                except Exception:
                    pass
        tb.addAction(_make_action(main_window, _t("Adjust UV"), "uv_transform",
            _t("Open the fine-tune panel (sliders)."),
            show_adjust_panel))

    tb.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return tb


# =========================================================================
# PONTO DE ENTRADA DO PLUGIN
# =========================================================================

def setup(app) -> None:
    """Registra a toolbar, o painel e o submenu do igz-UV.

    Chamado uma única vez pelo IngeTrazo quando a main window é
    construída. Idempotente via _TOOLBAR_CREATED.
    """
    global _TOOLBAR_CREATED, _PANEL_DOCK, _PANEL_TOGGLE
    if _TOOLBAR_CREATED:
        return
    try:
        # 1) Localiza a main window do Qt (o mesmo caminho do
        #    igz_tb_scenes: procura widgets top-level que tenham
        #    addToolBar).
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

        # 2) Localiza o viewport.
        vp = find_viewport(mw) or getattr(app, "viewport", None)
        if vp is None:
            _log("setup: viewport não encontrada.")
        else:
            _log(f"setup: viewport = {vp.__class__.__name__}")

        # 3) Cria e registra o painel de ajuste fino.
        try:
            panel = UVAdjustPanel(vp, mw)
            dock = app.add_panel(
                "Ajuste UV", panel, name="adjust", stretch=1
            )
            _PANEL_DOCK = dock
            _log("setup: painel 'Ajuste UV' registrado.")
        except Exception:
            _log("setup: app.add_panel indisponível; painel ignorado.")
            traceback.print_exc()
            dock = None
        # Guarda o toggleViewAction para a toolbar (faz o botão afundar).
        if dock is not None and hasattr(dock, "toggleViewAction"):
            _PANEL_TOGGLE = dock.toggleViewAction()
        else:
            _PANEL_TOGGLE = None

        # 4) Adiciona a toolbar no topo da janela.
        tb = create_toolbar(mw, vp, app=app)
        mw.addToolBar(Qt.TopToolBarArea, tb)
        _TOOLBAR_CREATED = True
        _log("setup: toolbar 'igz-UV' adicionada.")

        # 5) Cria o submenu Extensions ▸ igz-UV com todos os comandos.
        try:
            sub = app.add_menu("igz-UV")
            sub.addAction(_t("Planar Map"),       lambda: planar_map(vp))
            sub.addAction(_t("Spherical Map"),    lambda: spherical_map(vp))
            sub.addAction(_t("Cylindrical Map"),  lambda: cylindrical_map(vp))
            sub.addAction(_t("Box Map"),          lambda: box_map(vp))
            sub.addAction(_t("Quad Face Map"),    lambda: quad_face_map(vp))
            sub.addAction(_t("Tube Map"),         lambda: tube_map(vp))
            sub.addSeparator()
            sub.addAction(_t("Triangulate"),
                          lambda: triangulate_selection(vp))
            sub.addSeparator()
            sub.addAction(_t("UV Transform"),
                          lambda: _activate_uv_transform(vp))
            if _PANEL_TOGGLE is not None:
                sub.addAction(_PANEL_TOGGLE)
            else:
                sub.addAction(_t("Adjust UV"),
                              lambda: _mostrar_painel(app))
            sub.addSeparator()
            sub.addAction(_t("Help…"),            lambda: show_help(vp))
        except Exception:
            _log("setup: app.add_menu indisponível; submenu ignorado.")
    except Exception:
        traceback.print_exc()


def _activate_uv_transform(viewport):
    """Ativa o UVTransformTool via viewport.set_active_tool."""
    if viewport is None or not hasattr(viewport, "set_active_tool"):
        return
    try:
        viewport.set_active_tool(UVTransformTool(viewport))
    except Exception:
        traceback.print_exc()


def _mostrar_painel(app):
    """Traz o painel de ajuste fino à frente (fallback do toggle)."""
    if _PANEL_DOCK is None:
        return
    try:
        app.show_panel(_PANEL_DOCK)
    except Exception:
        traceback.print_exc()


# API pública do módulo (usada pelo __init__.py e por testes).
__all__ = [
    "UVTransformTool",
    "UVAdjustPanel",
    "create_toolbar",
    "setup",
    "planar_map", "spherical_map", "cylindrical_map", "box_map",
    "quad_face_map", "tube_map", "triangulate_selection",
    "show_help",
]