# =========================================================================
# Pasta: igz-UV/
# Arquivo: __init__.py
# Descrição: Ponto de entrada + i18n do plugin igz-UV.
# Version: 1.1.0
# License: GPL-3.0-or-later (same as IngeTrazo)
# =========================================================================
from __future__ import annotations

import json
import os
import sys
import traceback

#: Versão do pacote — fonte única usada pelos scripts de empacotamento.
__version__ = "1.1.0"

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

_DEBUG = True


def _log(msg: str) -> None:
    if _DEBUG:
        print(f"[igz-UV/init] {msg}", file=sys.stderr, flush=True)


# --- i18n ---------------------------------------------------------------
try:
    from core.i18n import tr as _tr_i18n
    from core.i18n import current_language as _current_language
except Exception:
    def _tr_i18n(s, **kw):
        return s.format(**kw) if kw else s

    def _current_language():
        return "en"


_I18N_DIR = os.path.join(_HERE, "i18n")
_I18N_CACHE: dict[str, dict] = {}
_I18N_LANGS: list[str] | None = None


def _available_langs() -> list[str]:
    """Idiomas disponíveis: nomes dos arquivos ``i18n/<lang>.json``."""
    global _I18N_LANGS
    if _I18N_LANGS is None:
        try:
            _I18N_LANGS = sorted(
                os.path.splitext(name)[0]
                for name in os.listdir(_I18N_DIR)
                if name.lower().endswith(".json")
            )
        except Exception:
            _I18N_LANGS = []
    return _I18N_LANGS


def _load_i18n_json(lang_key: str) -> dict:
    if lang_key in _I18N_CACHE:
        return _I18N_CACHE[lang_key]
    data: dict = {}
    try:
        path = os.path.join(_I18N_DIR, f"{lang_key}.json")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                data = {str(k): str(v) for k, v in raw.items()
                        if not str(k).startswith("_")}
    except Exception:
        _log(f"i18n: falha ao carregar {lang_key}")
    _I18N_CACHE[lang_key] = data
    return data


def _lang_key() -> str:
    try:
        raw = str(_current_language() or "en").strip().replace("_", "-")
    except Exception:
        return "en"
    langs = _available_langs()
    if raw in langs:
        return raw
    for cand in langs:
        if cand.lower() == raw.lower():
            return cand
    base = raw.split("-")[0].lower()
    for cand in langs:
        if cand.lower().split("-")[0] == base:
            return cand
    return "en"


def _t(text: str, **kw) -> str:
    try:
        x = _tr_i18n(text)
        if isinstance(x, str) and x != text:
            return x.format(**kw) if kw else x
    except Exception:
        pass

    lang = _lang_key()
    if lang != "en":
        out = _load_i18n_json(lang).get(text, text)
    else:
        out = text
    return out.format(**kw) if kw else out


# --- carregar pacote interno --------------------------------------------
try:
    from .core import toolbar, mappings, texture
except ImportError:
    import core.toolbar as toolbar
    import core.mappings as mappings
    import core.texture as texture

# Registra a pasta de ícones para a grade UV automática.
texture.set_icons_dir(
    os.path.join(_HERE, "icons")
    if os.path.isdir(os.path.join(_HERE, "icons"))
    else None
)
# Injeta o tradutor global nos módulos internos.
mappings.set_translator(_t)
# Inicializa o toolbar com o caminho da pasta.
toolbar.init(_HERE)


def setup(app) -> None:
    _log(f"setup(app) — PID={os.getpid()}")
    try:
        toolbar.setup(app)
    except Exception:
        _log("toolbar.setup(app) raised")
        traceback.print_exc()


__all__ = ["setup"]