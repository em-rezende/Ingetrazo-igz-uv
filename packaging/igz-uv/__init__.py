# =========================================================================
# Extension: igz-UV — package entry point
# Author:  Ezequiel M. Rezende
# Date:    2026-10-11
# Version: 1.0.0
# License: GPL-3.0-or-later (same as IngeTrazo)
#
# Port of SketchUV (by Dale Martens / Whaat) to IngeTrazo.
#
# Package layout:
#   • __init__.py  — this file: loads igz-UV.py by path and forwards
#                     setup(app) to it.
#   • igz-UV.py    — the whole extension (mappings, triangulation,
#                     interactive keyboard tool, adjustment panel
#                     with sliders, automatic UV grid, toolbar and menu).
#   • icons/       — SVG icons (normal and _light variants).
#   • i18n/        — translation JSON files (en, pt-BR, es, it).
#
# Why this __init__.py exists:
#   IngeTrazo scans plugins in two forms — a loose .py file, or a
#   folder with __init__.py (the "zip form"). Since igz-UV ships more
#   than code (icons, UV grid, translations), it comes as a folder.
#
# Why loading goes through importlib instead of `from . import`:
#   1. The source file name contains a hyphen ("igz-UV.py"). A hyphen
#      is not a valid Python identifier, so `import igz-UV` (and the
#      equivalent `from . import igz_uv`) would fail.
#   2. IngeTrazo's documentation asks that plugins not depend on
#      `sys.path` nor on stable package names. Loading by path is the
#      same route the host's own loader takes.
#   3. Registering the module in `sys.modules` before executing it
#      avoids duplicate reloads if IngeTrazo tries to re-import.
# =========================================================================

from __future__ import annotations

import importlib.util
import os
import sys
import traceback

# Diretório do próprio pacote. Usado para resolver o caminho de
# igz-UV.py e (indiretamente, dentro dele) da pasta icons/.
_HERE = os.path.dirname(os.path.abspath(__file__))

# Log de diagnóstico. Diferente do log do igz-uv.py (que usa o prefixo
# "[igz-UV]") este aqui usa "[igz-UV/init]" para deixar claro de onde
# veio cada mensagem no stderr do IngeTrazo.
_DEBUG = True


def _log(msg: str) -> None:
    """Imprime uma mensagem de diagnóstico do carregador do pacote."""
    if _DEBUG:
        print(f"[igz-UV/init] {msg}", file=sys.stderr, flush=True)


def _load_module(module_name: str):
    """Carrega um arquivo .py irmão por caminho.

    Aceita hífen no nome do arquivo (o nome "igz-UV.py" é usado assim
    mesmo, por tradição do plugin original). Devolve o módulo já
    executado e registrado em sys.modules.
    """
    path = os.path.join(_HERE, f"{module_name}.py")
    # O nome interno do módulo usa underscores: "igz_uv_igz_UV".
    # Assim fica claro (nos logs e no sys.modules) que este é um
    # carregamento privado do plugin, não um import público.
    mod_name = f"igz_uv_{module_name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    # Registra ANTES de executar, para que qualquer import circular
    # dentro do módulo (improvável, mas possível) encontre uma
    # referência válida em sys.modules.
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


# Carrega igz-UV.py uma única vez, no import do pacote. Igual ao que
# aconteceria se o plugin fosse um .py solto.
try:
    _UV = _load_module("igz-UV")
except Exception:
    # Nunca deixamos o carregamento derrubar o IngeTrazo: se falhar,
    # guardamos None e o setup(app) abaixo vira no-op. O traceback
    # completo vai para o stderr do host.
    _UV = None
    traceback.print_exc()


def setup(app) -> None:
    """Chamado uma vez pelo IngeTrazo ao construir a main window.

    Simplesmente encaminha para o `setup(app)` do igz-UV.py, que faz
    todo o trabalho (toolbar, painel lateral e submenu Extensions).
    Uma falha aqui é logada e ignorada — o IngeTrazo nunca deve
    quebrar por causa de um plugin.
    """
    _log(f"setup(app) — PID={os.getpid()}")
    if _UV is not None and hasattr(_UV, "setup"):
        try:
            _UV.setup(app)
        except Exception:
            _log("igz-UV.setup(app) raised")
            traceback.print_exc()