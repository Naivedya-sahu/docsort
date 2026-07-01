# docsort — Session Handoff & Project State

> Single-file, self-contained handoff for the next session. Date: **2026-07-01**.
> Current version: **v0.12.3** (GUI tab consolidation — see CHANGELOG; tag/release this once the
> human visual smoke-test in §9 has passed).
> Repo: https://github.com/Naivedya-sahu/docsort · Local: `D:\Vault\Personal\Archive\Doc-handler`
> (working folder still named `Doc-handler` — intentional; nothing depends on it.)

---

## 1. What docsort is

A **local-LLM document tagger + sorter** for an academic / Electronics-Engineering archive. Per file it:
1. Classifies into a **STREAM** (what the file is *for*) + a **SUBJECT** (the topic),
2. Stamps a `[STREAM-SUBJECT]` filename prefix,
3. Optionally **moves** files into a `dest/STREAM/SUBJECT/` tree.

Classification runs **100% locally and free** against **LM Studio** (OpenAI-compatible, `localhost:1234`).
An optional **Claude `haiku` frontier** (uses the user's Claude subscription, no API key) handles
genuinely-ambiguous files. No OpenAI/ChatGPT backend (removed deliberately).

Two surfaces: **CLI** (`docsort`) and a **modern Flet GUI** (`docsort-gui`) — as of v0.11.0 a Flet
(Python/Flutter) app, Discord-like dark, nav rail: Run / Tags / Stats (Folders + Reports live inside
Stats as sub-sections since v0.12.3; the 5 run-option toggles live on the Tags tab).

---

## 2. Install / run / dev

**End-user (no Python):** download `docsort-gui.exe` / `docsort.exe` from GitHub Releases (auto-built on
every `v*` tag via `.github/workflows/release.yml`). Needs LM Studio running with a VL model loaded.

**pip (Windows, Python 3.9+):**
```
git clone https://github.com/Naivedya-sahu/docsort.git && cd docsort
python -m venv .venv && .venv\Scripts\activate
pip install ".[gui]"     # engine + Flet GUI   (plain "pip install ." = CLI only)
pip install ".[all]"     # also .doc/.docx/.pptx readers + GUI
```
Console commands: **`docsort`** (CLI) and **`docsort-gui`** (GUI). The GUI now needs the **`[gui]`** extra
(Flet); a CLI-only install prints a hint if you launch the GUI without it.

**Dev loop (this machine):**
- Editable interpreter: `.venv\Scripts\python.exe` (has pymupdf, flet 0.85.3, pytest, pyinstaller).
  Note `docsort` is installed **editable** here (so PyInstaller needs `--paths=.` to find it — see below).
- Tests: `.venv\Scripts\python.exe -m pytest -q` — **20 tests**, all pure-logic/hermetic
  (`tests/test_core.py` + `tests/test_runcore.py`). No model/network needed.
- **Build exes locally:** `build-exe.bat` (repo root) — GUI via `flet pack`, CLI via PyInstaller, version
  read from `docsort.__version__`. Outputs `dist\docsort-gui.exe` (~85 MB) + `dist\docsort.exe` (~112 MB).
  (If running the .bat through a wrapper misbehaves, run its two commands directly — they're in the file.)

**Releases are automated:** push a `v*` tag → `release.yml` builds both exes on a Windows runner
(GUI = `flet pack ... --add-data "docsort/data;docsort/data" --pyinstaller-build-args=--paths=.`; CLI =
PyInstaller `--collect-all docsort`) and publishes the release. `ci.yml` runs compile + import + `--help`
+ pytest on 3.9/3.11/3.12.

---

## 3. Architecture

### Package layout (flat-layout package at repo root)
```
docsort/
  __init__.py        # __version__ = "0.12.0"
  cli.py             # the engine + main(): tiers, backends, journal, report/undo/stats/apply-journal, all flags
  runcore.py         # UI-agnostic run core: parse_progress, parse_result_row, build_run_cmd, RunController (NEW v0.11.0)
  tagsio.py          # TAGS.md ```tags block read/rewrite, decoupled from any UI (NEW v0.11.0)
  gui.py             # the Flet GUI (NEW Flet rewrite v0.11.0); drives `python -m docsort.cli` via subprocess
  config.py          # DEFAULTS, per-user dir seeding, host/location/model resolution
  data/              # bundled templates (TAGS.md, system_prompt.md, config.example.json)
tests/test_core.py, tests/test_runcore.py
run_gui.py, run_cli.py             # PyInstaller/flet-pack entry points (repo root)
build-exe.bat                      # local exe build
.github/workflows/ci.yml, release.yml
docs/   — GUIDE.md CHANGELOG.md HANDOFF.md TROUBLESHOOTING.md MODEL-GUIDE.md ROADMAP.md
docs/archive/  — design notes (council, taxonomy-generator, gui-vision), the spec + build plan, html mockups
ROOT (only):  README.md  LICENSE  pyproject.toml  MANIFEST.in  requirements.txt  run.bat  build-exe.bat  run_cli.py  run_gui.py
docsort/docsort.ico  — app icon, wired into the exe build via flet pack -i / pyinstaller --icon
```
> Doc layout: only `README.md` lives at the repo root; all other docs are under `docs/`. `.git`, `.github`,
> `.venv`, `.planning`, `.claude`, `.pytest_cache`, and `docsort.egg-info` carry the Windows hidden attribute
> (cosmetic; reverse with `attrib -h <name>`). Build artifacts (`build/`, `dist/`, `*.spec`, `__pycache__`)
> are gitignored and regenerable.

### Classification tiers (`classify()`), trust high→low
`TEXT` (first pages) → `ESCALATE` (re-read up to 5 pages on `99UNS`, `source=text5`) → `VISION` (render
page → VL model; still `99UNS`? page-3, `vision3`) → `FRONTIER` (`--frontier claude` = haiku) → `FILENAME`.
Per call: `temperature=0`, `max_tokens=24`; model replies one line `STREAM SUBJECT TYPE CONF [PROPOSE:LABEL]`.

### Run journal (robustness backbone) — JSONL
`_docsort_state.jsonl` in the working dir, one flushed line per file:
`{rel, name, mtime, status, stream, subject, type, conf, source, dst, error, ts}`, `status ∈
done|failed|skipped`. Source of truth for `--resume`, `--retry-failed`, `--undo`, **`--apply-journal`**, and
the report. In a **dry-run** `dst` stays the original path but the decision (stream/subject/mtime) is
recorded — that's what `--apply-journal` replays.

### GUI ↔ engine (v0.11.0+)
The Flet GUI spawns the existing `docsort` CLI as a subprocess (`runcore.RunController`) and parses its
`PROGRESS` / per-file result-row stdout into typed events (`progress`/`file`/`log`/`done`). **No engine
re-implementation** — the engine is unchanged behaviour-wise. Background-thread events are marshalled onto
the Flet UI thread via `page.run_thread`.

### Outputs per run
`_docsort_state.jsonl` (journal), `_docsort_log.csv`, `DOCSORT-REPORT.md`, and an appended record in the
global lifetime `index.jsonl` (`%APPDATA%\docsort\`).

---

## 4. Tag vocabulary (`TAGS.md` — single source of truth)
Injected into the prompt AND the only codes the parser accepts (off-list → `99UNS`). Filename prefix uses
**STREAM-SUBJECT only**; TYPE+CONF go to the log.
- **STREAMS (6):** `CW GATE PROJ RES REC REF`
- **SUBJECTS (17 + NA + 99UNS):** EE topics `00MM 01CA 02SEMI 03PN 04BJT 05MOS 06OPAMP 07ANLG 08DIG 09SNS
  10CTRL 11COMM 12EMAG 13TOOLS` + foundation `90HUM 91PHY 92CHEM` + `NA` + `99UNS`
- **TYPES (11):** `notes pyq book slides assignment lab report datasheet syllabus solution misc`
- **Self-growth:** `99UNS PROPOSE:LABEL` → `[STREAM-~LABEL]` (pending); `--report` tallies; promote in the
  Tags editor, then `--retag`.

---

## 5. Feature set & key flags
**Commands:** `docsort` (CLI), `docsort-gui` (Flet GUI).
**Flags (additions to note):** `--apply-journal` (fast apply from a dry-run's audit, no model — see §3),
plus the existing set: `--apply --copy --misc/--no-misc --skip-unknown --vision --frontier none|claude|cmd
--move DEST|@archive --review --report --undo --stats --retry-failed --retag --resume --exclude --include
--list-models --edit-tags --host --location`. Full table in `GUIDE.md`.

**Safety:** dry-run by default (`--apply`); `--copy` works on a `<name>COPY`; `--undo` reverses all
journal-recorded renames/moves; `--skip-unknown` leaves `99UNS` untouched. **`--apply-journal` writes fresh
journal rows so `--undo` still reverses it.**

**GUI (Flet):** folder picker, host + live model picker (+ refresh), frontier dropdown,
**Run / Apply audited / Stop**, progress hero (% · file i/N · elapsed · ETA), counters
(done/skipped/failed/tok-s), live per-file feed (tier + `[STREAM-SUBJECT]` tag), **verbose
collapsible log** — all on Run. Tags tab: tag-vocabulary editor + the 5 run-option toggles
(vision/apply/copy/misc/skip-unknown — skip-unknown defaults **on**, misc defaults **off** as of
v0.12.3). Stats tab: lifetime counts + embedded Folders (exclude/include) + embedded Reports viewer.

---

## 6. Version log

| Version | Gist |
|---|---|
| 0.8.0 | Rename → `docsort`; pip package; per-user data dir; first dark GUI; `--copy`, `--misc`; removed TUI. |
| 0.9.0 | Run journal; `--resume`; server-health guard; live progress GUI + Stop. |
| 0.10.0 | Exclude/include; reports + lifetime stats; `--undo`; `--retry-failed`; structured tag editor; pytest; exe pipeline. |
| 0.10.1 | `--skip-unknown`. |
| 0.10.2 | Docs only — design notes + roadmap. |
| **0.11.0** | **GUI rebuilt on Flet** — nav rail + Run view (progress/time/ETA/counters/feed/log) + Tags/Folders/Reports/Stats. New `runcore.py` (parsers + `RunController`, unit-tested) + `tagsio.py`. Engine unchanged; UI drives the CLI via subprocess. |
| **0.11.1** | GUI hotfixes — **FilePicker is a Flet *service*** (was wrongly on `page.overlay` → 10 s picker timeout); dropdown labels (`text`); threaded model refresh; **exe bundling fix** (`flet pack` was missing `docsort` + data → `ModuleNotFoundError`). |
| **0.12.0** | **`--apply-journal` (fast apply)** — replay a dry-run's audited decisions as renames, **zero model calls**, mtime-stale skip; + GUI **Apply audited** button. ← current, released. |

Git: `main` pushed to origin at the v0.12.0 merge; tag `v0.12.0` released with both exe assets. Tree clean.

---

## 7. Open / deferred items (resume here) — full list in `docs/ROADMAP.md`

**Separate project (not docsort):**
- **LLM Council** — universal API endpoints + a controller model managing other models ("poor man's MoE").
  In development by the user; docsort will consume its endpoint as a future `99UNS` tier once integration is
  defined. Design note: `docs/archive/council.md`. Do NOT build inside docsort.

**Planned features:**
- **Taxonomy Generator** (designed, deferred) — interactive wizard: a user's folder tree → generated
  `TAGS.md` / `system_prompt.md` via a small CPU-capable LM Studio text model; de-personalizes the taxonomy
  (public blocker #2). Wizard plugs into the Flet shell. Design: `docs/archive/taxonomy-generator.md`.
- **Background processing + system tray** — run minimized / tray flyout (mockup: `docs/archive/system-tray.html`).
- **Single unified Windows package** as the release artifact (vs. two exes).
- **GUI config persistence** (Host/Model/toggles between launches), **transient single-retry** (one retry on
  an empty model reply before `99UNS`), **in-process engine boundary** (replace subprocess + line parsing).
- **Sub-file progress** (low) — intra-file % (LM Studio prompt-eval) isn't in the OpenAI HTTP API docsort
  uses; would need `stream:true` (little value) or log-tailing (fragile).

**Public-release blockers (still open):** (1) **accuracy unproven at scale** — only ever run on small
samples; run the MODEL-GUIDE benchmark on 50–100 labelled files; (2) personalized taxonomy → Taxonomy
Generator; (3) effectively Windows-only; (4) unsigned exe (SmartScreen).

---

## 8. Hardware & environment
- **Primary:** laptop, RTX 3050 **4 GB VRAM**, 16 GB RAM. ~40 tok/s on 7–8B VL models. LM Studio at
  `localhost:1234`. Future 8 GB box → run 2 models concurrently (user prefers multi-model ensembles).
- Models seen: `qwen3-vl-8b`, `qwen/qwen3-vl-4b`, `qwen2.5-vl-3b-instruct` (+7B). Keep the LM Studio GGUF
  stack (no OpenAI, no rigid OCR pipeline). See `docs/MODEL-GUIDE.md`.

---

## 9. ⚠️ Warnings / gotchas for next session
- **GUI is headless-unverifiable by an agent** — a Flet window can't be opened in a subagent/CI. GUI code is
  validated by constructing the control tree against a stub page + unit tests; **a human visual smoke-test is
  the gate before merge/tag.** The user confirmed the folder picker works post-0.11.1.
- **Flet 0.85.3 API differs from older docs** — use `ft.run` (not `ft.app`), `ft.Icons`/`ft.Colors`
  (uppercase), `ProgressBar.bar_height`, `ft.Padding(...)` (no `padding.symmetric`), `ExpansionTile(expanded=)`,
  **FilePicker is a Service → `page.services`**, `page.run_thread`/`page.run_task`. Introspect the installed
  package; don't trust the old API. (More in the build plan + the user's memory notes.)
- **Editable install + PyInstaller:** docsort is `pip install -e .` in the dev `.venv`, so PyInstaller can't
  find it without `--paths=.`; data needs `--add-data "docsort/data;docsort/data"`. `build-exe.bat`/release.yml
  already do this. CI installs non-editable so it's fine there too.
- **Source-data folder:** `D:\Sort\Backup Home PC1\Documents` (the old `C:\…\Backup Home PC1\Documents` had
  vanished). Use the D:\Sort path for real runs.
- **Load a Qwen-VL model in LM Studio** before a real tagging pass (a non-VL model can't read images).
- Recurring network drops + Claude usage-limit interruptions occurred during the v0.11/0.12 build session —
  prefer inline work over many subagent dispatches when the connection is flaky.

---

## 10. Working agreements / preferences
- **GUI is the primary surface**; CLI is the clean programmatic/agentic surface. Stay on the **LM Studio GGUF
  stack**. Values **accuracy** for large overnight batches over speed; prefers **multi-model ensembles**.
  Renaming-only is considered safe (journal-backed undo); unknowns left untouched.
- Process: features designed (brainstormed) before building; committed in small, tested increments on a
  feature branch then merged `--no-ff` to `main`; every `v*` tag auto-ships exes. Semver: new flags/features →
  minor bump (e.g. apply-journal = 0.12.0), pure fixes → patch.

---

### Start here (next session)
Likely next moves, in priority order:
(a) **Taxonomy Generator** — the designed-but-unbuilt wizard (de-personalization, public blocker #2); design
    is ready in `docs/archive/taxonomy-generator.md`.
(b) **Accuracy benchmark** on 50–100 hand-labelled real files (the #1 public blocker) via the auto
    `DOCSORT-REPORT.md`.
(c) **GUI polish/debt** — config persistence, background processing + system tray, single Windows package.
(d) **Council integration** — only once the user shares the council project's endpoint.
The v0.11.0 GUI build plan (full task list, still a useful reference for Flet patterns) lives in
`docs/archive/gui-visual-overhaul-plan.md`.
