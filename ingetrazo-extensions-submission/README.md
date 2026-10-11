# Submission bundle — IngeTrazo extension catalog

> **Submission bundle for the IngeTrazo extension catalog** (v1.0.0). These
> are the files to be submitted in a catalog pull request at
> <https://github.com/ingelibre/ingetrazo-extensions>.

The files below go into the catalog repository:

| From here | To the catalog repository |
|---|---|
| `extensions/igz_uv.toml` | `extensions/igz_uv.toml` |
| `screenshots/igz_uv.png` | `screenshots/igz_uv.png` |

## Preconditions (before opening the pull request)

- The `download` URL points at the **v1.0.0** GitHub Release asset
  `igz-uv.zip`, so create that tag/release in this repository first and
  upload `dist/igz-uv.zip` as the asset with that exact name.
- The `sha256` in the entry must match that asset byte-for-byte. It was built
  with `packaging/build_extension.ps1` (the Windows builder); rebuild with it
  if the code changed, and paste the value it prints. (The multi-platform
  `packaging/build_extension.py` builds the same layout but not the same
  bytes — the .NET and Python compressors differ — so it prints a different
  `sha256`; use whichever script you actually built the uploaded `.zip` with.)
- Add a screenshot named `igz_uv.png` (the `screenshot` field refers to it);
  the extension shows a top toolbar plus the **Adjust UV** side panel.

Full, step-by-step instructions are in [`../PUBLISHING.md`](../PUBLISHING.md).
