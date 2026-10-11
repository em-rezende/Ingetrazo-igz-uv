#!/usr/bin/env python3
# =========================================================================
# Copyright (C) 2026 Ezequiel M. Rezende
# License: GPL-3.0-or-later (same as IngeTrazo)
# =========================================================================
# Build the distributable ``igz-uv.zip`` for the IngeTrazo extension
# catalog (https://github.com/ingelibre/ingetrazo-extensions).
#
# The catalog installs ONE file per entry: a .py file, or a .zip holding a
# single folder with an __init__.py (see TEMPLATE.toml in that repository).
# This extension needs the zip form because it ships one module plus a
# folder of SVG icons, a folder of translation JSON files and the UV grid
# image used for untextured faces.
#
# The archive is built deterministically on purpose: fixed timestamps,
# sorted entries and a fixed create-system, so its SHA-256 changes ONLY
# when the content changes. That is what lets the catalog fingerprint
# (``sha256`` in ``extensions/<id>.toml``) be verified and reproduced.
#
# Usage:
#     python packaging/build_extension.py
#
# Output:
#     dist/igz-uv.zip
#     dist/igz-uv.zip.sha256   (the value to paste in the catalog entry)
#
# The printed SHA-256 is what goes into ``extensions/igz_uv.toml``; upload
# the very same dist/igz-uv.zip as a GitHub Release asset of the tag named
# in the entry's ``download`` URL.
# =========================================================================
from __future__ import annotations

import hashlib
import os
import re
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, "dist")

#: Single top-level folder inside the zip (required by the catalog); it is
#: what IngeTrazo unpacks into <plugins>/, so the installed path becomes
#: <plugins>/igz-uv/. The hyphen is deliberate — it is the plugin's name.
PACKAGE = "igz-uv"
ZIP_NAME = f"{PACKAGE}.zip"

#: Modules copied verbatim from the package source folder
#: (packaging/<PACKAGE>/), next to this script. The hyphen in the file
#: name is deliberate (the original name of the plugin module).
MODULES = ["igz-UV.py"]

#: Documentation bundled inside the package (optional but tidy).
EXTRA_FILES = ["LICENSE", "README.md", "README_ptBR.md", "THIRD-PARTY.md"]

#: The package source folder that becomes the single top-level folder in the
#: zip. It holds the entry point, the module and the translations; the docs
#: and the icons are pulled from the repository root so they are not
#: duplicated here.
PACKAGE_SRC = os.path.join(HERE, PACKAGE)

#: The package entry point (defines setup(app)).
INIT_SRC = os.path.join(PACKAGE_SRC, "__init__.py")

#: Translations folder inside the package source folder.
I18N_DIR = os.path.join(PACKAGE_SRC, "i18n")

#: Icons folder in the repository root. Ships the SVG icons plus the UV
#: grid image (texture_grid.*) painted on untextured faces.
ICONS_DIR = os.path.join(ROOT, "icons")

#: Fixed timestamp so the archive is byte-for-byte reproducible.
FIXED_DATE = (2026, 1, 1, 0, 0, 0)

#: The module whose header line ``# Version:`` is the single source of truth
#: for the package version.
VERSION_SRC = os.path.join(PACKAGE_SRC, "igz-UV.py")


def read_version() -> str:
    """Read the version from the module header, so it never drifts."""
    with open(VERSION_SRC, encoding="utf-8") as fh:
        for line in fh:
            match = re.match(r"#\s*Version:\s*(\S+)", line)
            if match:
                return match.group(1)
    return "0.0.0"


def _read(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def _is_icon(name: str) -> bool:
    """True for the SVG icons and the UV grid image (texture_grid.*)."""
    lowered = name.lower()
    return lowered.endswith(".svg") or lowered.startswith("texture_grid.")


def collect_entries() -> list[tuple[str, bytes]]:
    """Return ``(arcname, data)`` for every file, sorted by name."""
    entries: list[tuple[str, bytes]] = []

    entries.append((f"{PACKAGE}/__init__.py", _read(INIT_SRC)))

    for name in MODULES:
        entries.append(
            (f"{PACKAGE}/{name}", _read(os.path.join(PACKAGE_SRC, name)))
        )

    for name in EXTRA_FILES:
        path = os.path.join(ROOT, name)
        if os.path.isfile(path):
            entries.append((f"{PACKAGE}/{name}", _read(path)))

    if os.path.isdir(ICONS_DIR):
        for name in sorted(os.listdir(ICONS_DIR)):
            path = os.path.join(ICONS_DIR, name)
            if os.path.isfile(path) and _is_icon(name):
                entries.append((f"{PACKAGE}/icons/{name}", _read(path)))

    if os.path.isdir(I18N_DIR):
        for name in sorted(os.listdir(I18N_DIR)):
            path = os.path.join(I18N_DIR, name)
            if os.path.isfile(path) and name.lower().endswith(".json"):
                entries.append((f"{PACKAGE}/i18n/{name}", _read(path)))

    entries.sort(key=lambda item: item[0])
    return entries


def build() -> str:
    os.makedirs(DIST, exist_ok=True)
    out_zip = os.path.join(DIST, ZIP_NAME)

    with zipfile.ZipFile(out_zip, "w") as zf:
        for arcname, data in collect_entries():
            info = zipfile.ZipInfo(arcname, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3          # 3 = Unix: stable across OSes
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)

    digest = hashlib.sha256(_read(out_zip)).hexdigest()

    with open(out_zip + ".sha256", "w", encoding="ascii") as fh:
        fh.write(f"{digest}  {ZIP_NAME}\n")

    return digest


def main() -> None:
    version = read_version()
    digest = build()
    print(f"igz-uv {version}")
    print(f"  dist/{ZIP_NAME}")
    print(f"  sha256 = \"{digest}\"")
    print("")
    print("  Paste that sha256 into extensions/igz_uv.toml and upload")
    print(f"  dist/{ZIP_NAME} to the GitHub Release of the tag in `download`.")


if __name__ == "__main__":
    main()
