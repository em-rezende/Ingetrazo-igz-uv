# Publicar no catálogo de Extensões do IngeTrazo

> **Status: v1.0.0 e v1.1.0 publicadas.** A Release `v1.1.0` está no GitHub
> com o asset `igz-uv.zip` (sha256 verificado e reproduzível) e a ficha do
> catálogo já aponta para ela. A v1.0.0 foi submetida no pull request
> <https://github.com/ingelibre/ingetrazo-extensions/pull/75>, que passou na
> verificação automática. Para atualizar o catálogo, reenvie os mesmos dois
> arquivos (`extensions/igz_uv.toml` e `screenshots/igz_uv.png`) com os
> valores novos. Este guia descreve os passos que foram seguidos e, na
> prática, como publicar cada atualização.

Este documento (PT) e a seção em inglês mais abaixo descrevem como publicar
esta extensão no catálogo <https://github.com/ingelibre/ingetrazo-extensions>
(mostrado em <https://ingetrazo.com/extensiones>).

---

## O que já está pronto

| Item | Onde | Observação |
|---|---|---|
| Código | `igz-uv/` | Pacote modular: `__init__.py` + `core/*.py` (mappings, texture, transforms, triangulate, keyboard_tool, panel, toolbar, math_utils). |
| Empacotador | `packaging/build_extension.ps1` (Windows) e `packaging/build_extension.py` (multi-plataforma) | Gera um `.zip` determinístico com **uma** pasta de topo `igz-uv/`. |
| Ponto de entrada do pacote | `igz-uv/__init__.py` | Define `setup(app)` e `__version__` (fonte única da versão). |
| Artefato | `dist/igz-uv.zip` + `dist/igz-uv.zip.sha256` | Gerado pelo script; ele imprime o `sha256`. |
| Notas da Release | `packaging/release_notes/v1.1.0.md` | Texto publicado na Release `v1.1.0`. |
| Ficha do catálogo | `ingetrazo-extensions-submission/extensions/igz_uv.toml` | Copiar para `extensions/igz_uv.toml` no repositório do catálogo. |
| Captura de tela | `ingetrazo-extensions-submission/screenshots/igz_uv.png` | Enviar no pull request do catálogo. |
| Release publicada | <https://github.com/em-rezende/Ingetrazo-igz-uv/releases/tag/v1.1.0> | Asset `igz-uv.zip` (sha256 conferido — ver `dist/igz-uv.zip.sha256`). |
| Pull request | <https://github.com/ingelibre/ingetrazo-extensions/pull/75> | Passou na verificação automática (ficha v1.0.0). |

O `.zip` contém exatamente uma pasta de topo:

```
igz-uv/
├── __init__.py          # setup(app) + __version__ + i18n
├── core/                # código modular (*.py)
├── icons/               # *.svg (tema claro/escuro) + texture_grid.jpg
├── i18n/                # en, pt-BR, es, de, fr, it, zh
├── LICENSE
├── README.md
├── README_ptBR.md
└── THIRD-PARTY.md
```

O catálogo instala **um arquivo por extensão**: um `.py`, ou um `.zip` com
**uma** pasta contendo um `__init__.py` (ver `TEMPLATE.toml` no repositório do
catálogo). Por isso esta extensão, que traz um pacote (`core/`), uma pasta de
ícones e as traduções, usa o formato `.zip`.

> **Nota sobre o `sha256`:** o `.ps1` (Windows) e o `.py` (multi-plataforma)
> geram o **mesmo layout** da pasta, mas **não os mesmos bytes** (o compactador
> do .NET e o zlib do Python diferem), então cada script imprime um `sha256`
> diferente. Gere o `.zip` com **um** script, envie esse arquivo à Release e
> cole em `sha256` o valor que **esse** script imprimiu. O valor atualmente na
> ficha foi produzido pelo `build_extension.ps1`.

---

## Passos para publicar (quando autorizar)

Pré-requisitos atendidos: repositório público, licença livre
(GPL-3.0-or-later) e o arquivo baixado define `setup(app)`.

1. **Confirme as alterações locais e faça o commit.**
   ```powershell
   git add -A
   git commit -m "chore: prepare 1.1.0 for the IngeTrazo extension catalog"
   ```

2. **(Opcional) Reconstrua o artefato** — só é necessário se você mudou o
   código:
   ```powershell
   powershell -ExecutionPolicy Bypass -File packaging\build_extension.ps1
   ```
   Anote o `sha256` impresso e atualize-o em
   `ingetrazo-extensions-submission/extensions/igz_uv.toml` (e nas notas da
   Release).

3. **Envie o código para o GitHub e crie a etiqueta `v1.1.0`.** (A versão fica
   em `igz-uv/__init__.py`, em `__version__` e no cabeçalho `# Version:`.)
   ```powershell
   git push origin main
   git tag v1.1.0
   git push origin v1.1.0
   ```

4. **Crie a Release `v1.1.0`** em
   <https://github.com/em-rezende/Ingetrazo-igz-uv/releases/new>, use
   `packaging/release_notes/v1.1.0.md` como texto e **anexe
   `dist/igz-uv.zip` como asset** (nome exatamente `igz-uv.zip`).

5. **Abra o pull request no repositório do catálogo** (sem Git, pelo
   navegador):
   - *Add file ▸ Create new file* → `extensions/igz_uv.toml`, cole o conteúdo
     de `ingetrazo-extensions-submission/extensions/igz_uv.toml`.
   - *Add file ▸ Upload files* → envie a captura para `screenshots/`, com o
     nome `igz_uv.png` (o mesmo do campo `screenshot`).
   - **Propose changes ▸ Create pull request**.

6. **Responda o checklist** do template do PR:
   - [x] Um arquivo `extensions/igz_uv.toml`, copiado de `TEMPLATE.toml`.
   - [x] `download` aponta para uma **tag** (`v1.1.0`), não para uma branch.
   - [x] A licença em `license` é a do código (GPL-3.0-or-later).
   - [x] `reviewed.toml` **não** foi tocado (só mantenedores).
   - A extensão é puramente local: não acessa a rede nem executa processos
     externos.

---

## Detalhes que você pode querer ajustar ao publicar

- **Versão do IngeTrazo** (`ingetrazo = "0.5.7"`): use a versão com que você
  realmente testou.
- **Tags** (`tags = [...]`): só são válidas `architecture`, `bim`,
  `structures`, `terrain`, `drawing`, `analysis`, `import-export`,
  `rendering`, `fabrication`, `productivity`, `education`, `other`.
- **Captura de tela**: a sugestão do catálogo é ~1200×750 e o limite é
  600 KB.

---

# Publishing to the IngeTrazo extension catalog (EN)

> **Status: v1.0.0 and v1.1.0 published.** The `v1.1.0` Release is live on
> GitHub with the `igz-uv.zip` asset (verified, reproducible sha256) and the
> catalog entry already points at it. The v1.0.0 entry was submitted in pull
> request <https://github.com/ingelibre/ingetrazo-extensions/pull/75>, which
> passed the automatic check. To update the catalog, send the same two files
> (`extensions/igz_uv.toml` and `screenshots/igz_uv.png`) with the new values.
> This guide covers the steps that were taken and, in practice, how to publish
> each update.

Everything needed is in place (code, a `.zip` builder, the package entry, the
catalog entry and a screenshot). These are the steps to publish:

1. Commit locally (`git add -A; git commit -m "chore: prepare 1.1.0 ..."`).
2. (Only if the code changed) rebuild with `packaging\build_extension.ps1` and
   copy the printed `sha256` into the entry.
3. `git push origin main`, then `git tag v1.1.0` and `git push origin v1.1.0`.
4. Create the **v1.1.0** GitHub Release, use
   `packaging/release_notes/v1.1.0.md` as its text and attach
   `dist/igz-uv.zip` as an asset named exactly `igz-uv.zip`.
5. In <https://github.com/ingelibre/ingetrazo-extensions>, copy
   `ingetrazo-extensions-submission/extensions/igz_uv.toml` to
   `extensions/igz_uv.toml` and
   `ingetrazo-extensions-submission/screenshots/igz_uv.png` to
   `screenshots/igz_uv.png` (browser: *Add file ▸ Create new file* /
   *Upload files*), then **Create pull request**.
6. Fill in the PR template checklist.

The **sha256** in the entry must match `dist/igz-uv.zip` byte-for-byte. The
`.ps1` (Windows) and `.py` (multi-platform) builders produce the same folder
layout but **not the same bytes** — the .NET and Python compressors differ — so
each prints its own `sha256`; build the `.zip` with one script, upload that file
and paste that script's value. The current entry holds the value produced by
`build_extension.ps1`. The extension makes no network calls and runs no
external processes.
