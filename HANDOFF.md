# docsort — Session Handoff & Project State

> Single-file handoff. This is the **only** document uploaded to the next session — it is
> self-contained. Date of handoff: **2026-06-29**. Current version: **v0.10.2** (docs-only).
> Repo: https://github.com/Naivedya-sahu/docsort  ·  Local path: `D:\Vault\Personal\Archive\Doc-handler`
> (Note: the working *folder* is still named `Doc-handler` — intentionally not renamed; nothing depends on it.)

---

## 1. What docsort is

A **local-LLM document tagger + sorter** for an academic / Electronics-Engineering archive.
For each document it:
1. Classifies into a **STREAM** (what the file is *for*) and a **SUBJECT** (the topic),
2. Stamps a `[STREAM-SUBJECT]` filename prefix,
3. Optionally **moves** files into a `dest/STREAM/SUBJECT/` tree.

The classification pass runs **100% locally and free** against **LM Studio** (OpenAI-compatible
server, default `http://localhost:1234`). An **optional** frontier fallback (Claude Code CLI, bound
to `haiku`, uses the user's Claude subscription — no API key) handles the few genuinely-ambiguous
files. There is **no OpenAI/ChatGPT backend** (a ChatGPT web sub is not an API; removed deliberately).

Two surfaces: **CLI** (`docsort`, the clean/agentic surface) and a **modern dark Tkinter GUI**
(`docsort-gui`, the primary UX investment).

---

## 2. Install / run / dev

**End-user (no Python):** download `docsort-gui.exe` / `docsort.exe` from the GitHub Releases page
(auto-built on every `v*` tag). Needs LM Studio running with a VL model loaded.

**pip (Windows, Python 3.9+):**
```
git clone https://github.com/Naivedya-sahu/docsort.git
cd docsort
python -m venv .venv && .venv\Scripts\activate
pip install .            # or: pip install -e .   (editable)
pip install ".[all]"     # optional .doc/.docx/.pptx readers (python-docx, python-pptx, pywin32)
```
Gives two console commands: **`docsort`** (CLI) and **`docsort-gui`** (GUI). If the Python `Scripts\`
dir is on PATH they work in any shell; else `python -m docsort.cli` / `python -m docsort.gui`.

**No-install:** `run.bat` (launches GUI) or `run.bat "C:\folder" [flags]` (CLI). Uses the repo `.venv`.

**Dev loop (this machine):**
- Editable interpreter: `.venv\Scripts\python.exe` (has pymupdf/pytest/pyinstaller).
- Global interpreter: `py -3.14` (its `Scripts\` IS on PATH → `docsort` works globally). After code
  changes run `py -3.14 -m pip install . --force-reinstall --no-deps` to refresh the global command.
- Tests: `.venv\Scripts\python.exe -m pytest -q` (6 tests, all pure-logic / hermetic).
- Build exe locally (mirrors the release workflow):
  `pyinstaller --onefile --windowed --name docsort-gui --collect-all docsort scripts/run_gui.py`

**Releases are automated:** push a `v*` tag → `.github/workflows/release.yml` builds both exes on a
Windows runner and publishes a GitHub release with the assets. (`ci.yml` runs compile + import + `docsort --help` + pytest on 3.9/3.11/3.12.)

---

## 3. Architecture

### Package layout (flat-layout package at repo root)
```
docsort/
  __init__.py        # __version__
  cli.py             # the engine + main(): tiers, backends, journal, report/undo/stats, all flags
  config.py          # DEFAULTS, per-user dir seeding, host/location/model resolution
  gui.py             # dark Tkinter GUI (subprocess-drives `python -m docsort.cli`)
  data/              # bundled templates (packaged as package-data)
    TAGS.md          # tag vocabulary (single source of truth)
    system_prompt.md # model rules/examples; {{STREAMS}}/{{SUBJECTS}}/{{TYPES}} injected from TAGS.md
    config.example.json
tests/test_core.py   # pytest
scripts/run_gui.py, run_cli.py   # PyInstaller entry points
.github/workflows/ci.yml, release.yml
docs/MODEL-GUIDE.md  # OCR/VL model shortlist + LM Studio tuning + benchmark method
docs/superpowers/specs/2026-06-28-docsort-robustness-gui-design.md   # the Phase 1-4 design
README.md GUIDE.md CHANGELOG.md TROUBLESHOOTING.md LICENSE MANIFEST.in pyproject.toml run.bat requirements.txt
```

### Per-user data dir (seeded from bundled templates on first run; survives reinstall)
`%APPDATA%\docsort\` (Windows) / `~/.docsort/` (other):
- `config.json` — model host, named hosts/locations, exclude/include, archive_root, options
- `TAGS.md` — the user's editable tag vocabulary
- `system_prompt.md` — model rules/examples
- `index.jsonl` — global lifetime run index (appended per run; powers `--stats`)

### Classification tiers (in `classify()`), trust order high→low
`TEXT` (first 2 pages, if ≥`min_text` chars) → `ESCALATE` (re-read up to 5 pages on `99UNS`, `source=text5`)
→ `VISION` (render page-1 PNG to the VL model; still `99UNS`? page-3, `source=vision3`) →
`FRONTIER` (optional, `--frontier claude` = haiku, `source=frontier:claude`) → `FILENAME` (last resort).
Settings per call: `temperature=0`, `max_tokens=24`. Model must reply ONE line: `STREAM SUBJECT TYPE CONF`
(e.g. `CW 12EMAG notes high`), optionally `... PROPOSE:LABEL` to suggest a new subject.

### Model resolution (`resolve_model`, both text & vision tiers, `prefer_vision=True`)
If the configured model id isn't loaded in LM Studio, it auto-picks **any loaded VL model**
(`*vl*`/`*vision*`), else any non-embedding model. So it adapts to whatever the user has loaded.
`--list-models` prints what's loaded (tagged `[VL]`/`[embed]`).

### Run journal (the robustness backbone — JSONL, Approach 2)
`_docsort_state.jsonl` in the working dir, **one flushed line per file**:
`{rel, name, mtime, status, stream, subject, type, conf, source, dst, error, ts}`,
`status ∈ done | failed | skipped`. Source of truth for `--resume`, `--retry-failed`, `--undo`, and the
report. `dst` = final relative path after rename/misc-move (enables real undo).

### Live progress
CLI emits `PROGRESS i/N done=D failed=F tps=T toks=K eta=Es` per file (tps from LM Studio response
`usage.completion_tokens` / wall time; eta = remaining × avg time — crude/cosmetic). The GUI parses
these lines and drives a progress bar + tok/s + ETA + counters.

### Server-health guard (the real bug fix)
If the model returns nothing for **3 consecutive files** AND `/v1/models` no longer responds, the run
**stops with a resume hint** instead of silently mislabeling every remaining file `99UNS`.

### Outputs per run
- `_docsort_state.jsonl` (journal), `_docsort_log.csv` (flat report), `DOCSORT-REPORT.md`
  (distribution / types / proposals / low-conf / failures — auto-written at run end and by `--report`),
  and an appended record in the global `index.jsonl`.

---

## 4. Tag vocabulary (current `TAGS.md`)
Single source of truth — codes are injected into the prompt AND the parser only accepts these
(off-list → `99UNS`). The filename prefix uses **STREAM-SUBJECT only**; TYPE+CONF go to the log.
- **STREAMS (6):** `CW GATE PROJ RES REC REF`
- **SUBJECTS (19):** `00MM 01CA 02SEMI 03PN 04BJT 05MOS 06OPAMP 07ANLG 08DIG 09SNS 10CTRL 11COMM 12EMAG 13TOOLS 90HUM 91PHY 92CHEM` + `NA` + `99UNS`
- **TYPES (11):** `notes pyq book slides assignment lab report datasheet syllabus solution misc`

**Self-growth:** model meets a clear new subject not in the list → `99UNS PROPOSE:LABEL` → file written
`[STREAM-~LABEL]` (`~` = pending sub-tag under unknown, NOT auto-moved). `--report` tallies proposals;
promote a frequent one in the tag editor, then `--retag` re-files those `~LABEL` files.

---

## 5. Full feature set & CLI flags

**Commands:** `docsort` (CLI), `docsort-gui` (GUI).

**CLI flags (all):**
`root` (or `--location NAME`) · `--config` · `--host NAME|URL` · `--api` · `--model` · `--vision`
`--vision-model` · `--backend local` · `--frontier none|claude|cmd` · `--frontier-cmd "<tmpl>"`
`--tags` · `--prompt` · `--edit-tags` · `--apply` · `--copy` · `--misc/--no-misc` (default ON)
`--skip-unknown` · `--move DEST|@archive` · `--review` · `--report` · `--undo` · `--stats`
`--retry-failed` · `--retag` · `--resume` · `--exclude PATH` (repeatable) · `--include PATH` (repeatable)
`--list-models` · `--log`

**Behavior of the key toggles for an unknown (`99UNS`) file:**
| flags | result |
|---|---|
| default | renamed `[..-99UNS]` + moved to `misc\` |
| `--no-misc` | renamed `[..-99UNS]`, stays put |
| `--skip-unknown` | **untouched** (no rename, no move; journal `status=skipped`) |

**Safety / reversibility:** `--copy` tags a `<name>COPY` (originals untouched). `--undo` reverses all
journal-recorded renames/moves (incl. misc). Default is dry-run; `--apply` to actually rename.

**GUI features (dark Tkinter):** folder browse · Host field + live **Model picker** (lists loaded LM
Studio models, "auto" default) · toggles (Create copy / Move 99UNS→misc / Vision / Apply / Skip unknown)
· Frontier dropdown (none/claude) · **Run** + **Stop** (terminates subprocess; journal = resumable) ·
**progress bar + tok/s + tokens + done/failed + elapsed + ~ETA** · live log pane · **Edit Tags**
(structured editor: add/delete buttons, colour-coded streams/subjects/types/foundation, double-click to
edit, rebuilds TAGS.md blocks in place) · **Folders** dialog (Exclude/Include lists → config.json) ·
**Report** viewer (shows DOCSORT-REPORT.md from the folder or its COPY).

**Config keys (`config.json`):** `model{host,model,vision_model,backend,frontier,timeout}`, `hosts{}`,
`locations{}`, `exclude[]`, `include[]`, `folder_tags{}` (reserved, see §8), `archive_root`,
`options{vision,apply,min_text,deep_pages,deep_cap,dpi}`. CLI flags override config.

---

## 6. Version log (this project)

| Version | Gist |
|---|---|
| 0.5.1 | model auto-resolve + packaging (pre-session) |
| 0.6.0–0.7.1 | foundation subjects, proposals/`--review`, TUI, `.doc` reader, `--retag`, frontier claude (pre-session) |
| **0.8.0** | **This session.** Removed OpenAI/ChatGPT backend; Claude frontier bound to `haiku` + PATH preflight. **Renamed `doc-handler` → `docsort`.** Repackaged flat scripts → `docsort` package, console commands `docsort`/`docsort-gui`, per-user data dir. Removed the TUI. Added the dark GUI, structured-ish tag editor, **`--copy`**, **`--misc/--no-misc`** (default ON), **`--edit-tags`**, **`--list-models`** + GUI model picker/host field. Portable defaults (localhost). Ported a remote security fix (`shell=True`→`shlex.split` in frontier-cmd). |
| **0.9.0** | Run journal (`_docsort_state.jsonl`), `--resume`, graceful pause, **server-health guard** (no more mass-mislabel on mid-run server drop), CLI `PROGRESS` emission, **live progress GUI** (bar + tok/s + ETA + Stop button). |
| **0.10.0** | Exclude/Include folders (config + `--exclude`/`--include` + GUI Folders dialog). `DOCSORT-REPORT.md` + global `index.jsonl`; `--report`, `--stats`. **`--undo`** (real reversibility via journal `dst`). `--retry-failed`. Structured GUI tag editor (add/delete + colour). Hardened system prompt. `docs/MODEL-GUIDE.md`. Added pytest suite, `release.yml` exe pipeline. Released with `docsort-gui.exe` + `docsort.exe`. |
| **0.10.1** | **`--skip-unknown`** toggle (CLI + GUI) — leave `99UNS` files completely untouched. Hermetic test through `main()`. |
| **0.10.2** | **Docs only.** Design notes under `docs/design/` (council = separate universal-API project; taxonomy-generator sub-project; GUI vision). `docs/ROADMAP.md`. Source path → `D:\Sort\Backup Home PC1\Documents`. No code changes. |

Tags `v0.10.0` and `v0.10.1` are released with exe assets. Git HEAD = `f7e4aa9` on `main`, clean.

---

## 7. Session changelog (chronological narrative — what was decided & why)

1. **Reviewed the repo**, discussed hardware. Removed the **ChatGPT/OpenAI backend** entirely (a ChatGPT
   web sub is not an API; the API path was unused) and **bound the Claude frontier to `haiku`** (sub-covered,
   standard context). Added a PATH preflight so a missing `claude` CLI degrades gracefully to local-only.
2. Fixed **model resolution** so any loaded VL model is auto-picked on both text & vision tiers. Made
   localhost the portable default. Installed pymupdf into the right interpreter (bare `python` lacked it →
   PDFs silently degraded to filename-only — important gotcha).
3. Added **copy-or-direct** (`--copy`) and the **99UNS→misc** sweep (`--misc`, later default ON), then built
   the first Tkinter GUI; later removed the TUI in favour of the GUI.
4. **Big v0.8 refactor + rename to `docsort`**: proper pip package, two console commands, per-user data dir,
   dark GUI, structured tag editor, **model list/select** (CLI `--list-models` + GUI picker/host field).
5. **GitHub recovery:** local remote still pointed at the old `doc-handler.git`; remote also had a security
   commit we lacked → push rejected. Fixed remote URL, **ported the `shlex.split` fix into the new code**,
   rebased over the remote commit, pushed. CI green. exe release pipeline added and verified.
6. **Robustness design (brainstormed, spec written):** chose the **JSONL journal** as the backbone that makes
   progress/pause/resume/retry/undo all fall out. Implemented as v0.9.0 incl. the **server-health guard**
   (a real bug: mid-run server drop was silently mislabeling everything `99UNS`).
7. **v0.10:** exclude/include, reports + lifetime stats, undo, retry-failed, structured colour tag editor,
   prompt hardening, MODEL-GUIDE, tests, exe release. Then **`--skip-unknown`** (v0.10.1).
8. **Model strategy discussion:** user prefers staying on the **LM Studio GGUF stack** (huge HF catalogue,
   steerable) and rejected a fixed dedicated-OCR pipeline. Conclusion: keep **Qwen-VL** as the in-context
   OCR+tagger; treat MinerU / PaddleOCR-VL as *extractors not taggers* that can't load in LM Studio.
9. **Public-readiness assessment** and a **council-of-models** design discussion (see §8).

---

## 8. Open / deferred items & live design ideas (resume here)

### Decided-but-not-built features
- **`folder_tags` direct folder→tag** — config key is stubbed (`{folder: "STREAM-SUBJECT"}`). Idea: files
  under a named folder get a fixed tag without calling the model. Not implemented.
- **Top-tabs UI** — the user originally wanted Exclude/Include as tabs *at the top*; shipped as a **Folders
  dialog** instead (functionally equivalent, less layout risk). Revisit if a full GUI redesign happens.
- **Transient single-retry** — only the consecutive-dead-files guard exists; a one-off empty model reply
  still → `99UNS`. Cheap to add: retry one bad call once before giving up.
- **GUI lifetime-stats view** — `--stats` is CLI-only; the GUI Report viewer shows per-run md only.
- **Deeper ingestion tuning** — only prompt hardening done. Possible: boilerplate stripping, first+last
  page, auto-DPI bump for dense scans, `min_text` tuning.
- **GUI config persistence** — Host/Model fields aren't saved between sessions.

### Public-release blockers (from the readiness review)
1. **Accuracy unproven at scale** — only ever run on a ~5-file sample. **Run the MODEL-GUIDE benchmark on
   50–100 hand-labelled files** to get real numbers. This is the #1 thing before a broad release.
2. **Taxonomy is the user's EE-academic schema** baked into TAGS.md + prompt examples. For public use, add a
   **generic starter TAGS.md + first-run "pick your domain"** onboarding. (User was offered this; pending.)
3. Effectively **Windows-only** (.doc COM, exe, paths). Mac/Linux untested.
4. **Unsigned exe** → SmartScreen warnings for public downloaders.

### The "council of models" idea (designed, NOT built — high-value future tier)
For `99UNS` files only, overnight, accuracy-over-speed: run an **ensemble of diverse VLMs** + an
**LLM-as-judge**. Key design conclusions reached:
- **Code schedules, a model judges.** Don't make a model orchestrate other models; docsort runs a
  deterministic loop and one model (e.g. the `ornith-1.0-9b` text model) is the *judge* that scores the
  candidate tags and approves one OR mints a new sub-tag.
- **LM Studio JIT (Just-In-Time) model loading** makes "serial council" nearly free to implement: just send
  each chat request with a different `model` id and LM Studio swaps models. **No custom orchestrator, no need
  for 2 models in VRAM on 4GB.** On 8GB, keep judge + one tagger resident to cut swap overhead.
- **Reuse the existing `~LABEL` mechanism** for council-minted tags (pending sub-tag under unknown), tallied
  by `--report`, promoted via the tag editor + `--retag`. No new tag system needed.
- **Gate strictly to `99UNS` + opt-in (`--council`) + overnight** — it's minutes/file (JIT load + infer per
  member). Diversity only helps if members are genuinely different models (Qwen-VL + InternVL3 + MiniCPM-V +
  an OCR-fed text judge), not 3 quants of one model.
- Slots in as a new escalation tier after VISION; journal `source=council`.

### `--ocr-cmd` preprocess hook (proposed, NOT built)
To use MinerU / external OCR without a rigid built-in pipeline: a generic `--ocr-cmd "<template>"` (mirrors
the existing `--frontier cmd`) that pipes a file through any external OCR tool to get clean text *before*
the LM-Studio tagging step. Keeps tagging steerable and LM-Studio-only.

### Model upgrade path (see `docs/MODEL-GUIDE.md` for full detail)
- Keep **Qwen3-VL** family (Unsloth Dynamic GGUFs). On 4GB laptop: **Qwen3-VL-4B UD Q4_K_XL @ 8192 ctx**.
  On 8GB desktop: **Qwen3-VL-8B**. Challengers to benchmark: **InternVL3-8B**, **MiniCPM-V 2.6**.
- **LM Studio tuning that matters:** context **8192** (docsort's payload is tiny — big ctx just wastes VRAM),
  Flash Attention ON, KV cache Q8, max GPU layers that fit. docsort-side: `dpi` 120→150-200 for dense scans.

---

## 9. Hardware & environment notes
- **Primary:** laptop, RTX 3050 **4GB VRAM**, 16GB RAM. Saw ~**40 tok/s** on 7–8B VL models. Future: an 8GB
  VRAM box (then run 2 models concurrently or a bigger model — user prefers the multi-model approach).
- Models seen/tested: `qwen3-vl-8b`, `qwen/qwen3-vl-4b`, `qwen2.5-vl-3b-instruct` (+ 7B). All LM-Studio VL.
- This machine's interpreters: editable `.venv` (repo) and global `py -3.14` (on PATH; `pymupdf` works via
  its `abi3` wheel). LM Studio at `localhost:1234`.

## 10. ⚠️ Warnings / things to verify next session
- **Source-data path (RESOLVED):** real-data folder is now `D:\Sort\Backup Home PC1\Documents`
  (confirmed exists 2026-06-29). The old path `C:\Users\NAVY\Documents\Backup\Backup Home PC1\Documents`
  had vanished mid-session (`FileNotFoundError` on copytree) — **not** deleted by docsort/Claude (only
  `…COPY` test folders, stray logs, and a test `index.jsonl` were removed); likely OneDrive move / manual
  delete. Use the `D:\Sort` path for any real run.
- **LM Studio had a non-VL model loaded** (`ornith-1.0-9b`) at one point — load a **Qwen-VL** before a real
  tagging pass or the vision tier can't read images. (`ornith` is, however, a good candidate **judge** for the
  council idea.)
- **GH Actions Node-20 deprecation warning** on checkout/setup-python/gh-release — harmless; bump action
  versions when next touching the workflows.
- Confirm the **v0.10.1 release exes** finished building/publishing (the tag push triggered the workflow).

## 11. Working agreements / preferences observed
- User wants the **GUI to be the primary surface**; CLI is the clean programmatic surface for agentic
  integration. Stay on the **LM Studio GGUF stack** (no OpenAI, no rigid OCR pipeline). Values **accuracy**
  for large overnight batches over speed. Prefers **multi-model / diverse-training** ensembles. Renaming-only
  is considered safe (reversible via journal). Token budget was tight late-session — be economical.
- Process: features were designed (brainstormed) before building; committed in small, tested increments;
  every `v*` tag auto-ships exes.

---

### Start here (next session)
Likely next moves, in priority order: (a) **run the accuracy benchmark** on real labelled files via the
auto-`DOCSORT-REPORT.md`; (b) **de-personalize the taxonomy + first-run onboarding** (public blocker #2);
(c) **spec & build the council-of-models `99UNS` tier** (and/or `--ocr-cmd` hook) for the 8GB box;
(d) small robustness/UX debt: transient single-retry, GUI config persistence, GUI lifetime-stats view.
The full Phase 1–4 design lives in `docs/superpowers/specs/2026-06-28-docsort-robustness-gui-design.md`.
