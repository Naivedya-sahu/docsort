# docsort — Session Handoff & Project State

> Single-file, self-contained handoff for the next session. Date: **2026-07-01**.
> Current version: **v0.13.0** (released — tag pushed, GitHub release has both exes). Main has
> **additional commits past the v0.13.0 tag** (architecture fixes + a new `recon` feature) that are
> unreleased — see §6 and §7.
> Repo: https://github.com/Naivedya-sahu/docsort · Local: `D:\Vault\Personal\Archive\Doc-handler`
> (working folder still named `Doc-handler` — intentional; nothing depends on it.)

---

## 1. What docsort is

A **local-first document tagger, sorter, and drive organizer** for an academic /
Electronics-Engineering archive. Per file it:
1. Classifies into a **STREAM** (what the file is *for*) + a **SUBJECT** (the topic),
2. Stamps a `[STREAM-SUBJECT]` filename prefix,
3. Optionally **moves** files into a `dest/STREAM/SUBJECT/` tree.

**As of v0.13.0, classification is model-free for the vast majority of files.** The EMBED tier
(a stdlib hashing-trick embedding, zero ML dependency) matches filename+folder+extracted text
against zero-shot centroids built from the user's own `TAGS.md` descriptions — no LLM call, no
processing-time cost. Only the **VISION** tier (scanned/handwritten pages with no extractable
text) still calls **LM Studio** (OpenAI-compatible, `localhost:1234`). An optional Claude `haiku`
frontier fallback exists in the codebase but is currently unreachable from either tier (see §7).
No OpenAI/ChatGPT backend (removed deliberately).

v0.13.0 also adds a **drive-organizer layer**, independent of per-file tagging: a ground-truth
index (archive-aware, recurses into zips), 3-layer dedup + vendor-dump detection ("Clean"), thin
folder-chain flattening ("Reorg"), and — unreleased, on `main` — a name-only zero-model triage
pass ("Recon"). See §3 and §5.

Two surfaces: **CLI** (`docsort`) and a **modern Flet GUI** (`docsort-gui`) — Discord-like dark,
nav rail: **Run / Tags / Stats** (Folders + Reports live inside Stats as sub-sections since
v0.12.3; the 5 run-option toggles live on the Tags tab). **The GUI has no surface for any
v0.13.0/drive-organizer feature yet** — it's CLI-only so far (see §7).

---

## 2. Install / run / dev

**End-user (no Python):** download `docsort-gui.exe` / `docsort.exe` from GitHub Releases (auto-built on
every `v*` tag via `.github/workflows/release.yml`). Needs LM Studio running with a VL model loaded
(only matters for VISION-tier files now — see §3).

**pip (Windows, Python 3.9+):**
```
git clone https://github.com/Naivedya-sahu/docsort.git && cd docsort
python -m venv .venv && .venv\Scripts\activate
pip install ".[gui]"     # engine + Flet GUI   (plain "pip install ." = CLI only)
pip install ".[all]"     # also .doc/.docx/.pptx readers + GUI
pip install ".[recon]"   # optional GPU-capable embedder for --recon-report (sentence-transformers);
                          # NOT in [all] deliberately — pulls in torch, the heaviest dep by far.
                          # Recon works without it too, falling back to the stdlib embedder.
```
Console commands: **`docsort`** (CLI) and **`docsort-gui`** (GUI).

**Dev loop (this machine):**
- Editable interpreter: `.venv\Scripts\python.exe` (has pymupdf, flet 0.85.3, pytest, pyinstaller;
  does NOT have sentence-transformers/torch — the `recon` extra was never installed here, see §9).
- Tests: `.venv\Scripts\python.exe -m pytest -q` — **73 tests**, all pure-logic/hermetic. No
  model/network needed anywhere, including recon's tests (they exercise the real stdlib-fallback
  path, since sentence-transformers genuinely isn't installed in this environment).
- **Build exes locally:** `build-exe.bat` (repo root) — GUI via `flet pack`, CLI via PyInstaller, version
  read from `docsort.__version__`. Outputs `dist\docsort-gui.exe` (~85 MB) + `dist\docsort.exe` (~112 MB).

**Releases are automated:** push a `v*` tag → `release.yml` builds both exes on a Windows runner
and publishes the release. `ci.yml` runs compile + import + `--help` + pytest on 3.9/3.11/3.12.

---

## 3. Architecture

### Package layout (flat-layout package at repo root)
```
docsort/
  __init__.py        # __version__ = "0.13.0"
  cli.py             # the engine + main(): tiers, backends, journal, all flags, index_session dispatch
  runcore.py         # UI-agnostic run core: parse_progress, parse_result_row, build_run_cmd, RunController
  tagsio.py          # TAGS.md ```tags block read/rewrite, decoupled from any UI
  gui.py             # the Flet GUI; drives `python -m docsort.cli` via subprocess. NO v0.13.0 surface yet.
  config.py          # DEFAULTS, per-user dir seeding, host/location/model resolution, EMBED thresholds
  index.py           # ground-truth SQLite index: archive-aware scan (nested zips, depth/budget-capped),
                      # index_session() context manager, embed_index()
  tree.py            # DirectoryTree — path-tree traversal shared by dedup/reorg/vendor (NEW, post-v0.13.0)
  embed.py           # stdlib hashing-trick embed_text() + cosine_similarity() — zero ML dependency
  cascade.py         # zero-shot centroid classification, seeded from TAGS.md descriptions
  dedup.py           # exact-hash, duplicate-subtree (via DirectoryTree), near-duplicate detection
  vendor.py          # vendor-dump (GitHub -master/-main) heuristic detector
  clean.py           # combines dedup+vendor detectors into one report + quarantine-apply
  reorg.py           # thin single-child-folder-chain detection + flatten proposals
  recon.py           # (unreleased) name-only, whole-tree, zero-model triage — NameEmbedder + recon_scan()
  data/              # bundled templates (TAGS.md, system_prompt.md, config.example.json)
tests/  — test_core.py test_runcore.py test_index.py test_dedup.py test_vendor.py test_clean.py
          test_reorg.py test_embed.py test_cascade.py test_tree.py test_recon.py  (73 tests total)
run_gui.py, run_cli.py             # PyInstaller/flet-pack entry points (repo root)
build-exe.bat                      # local exe build
.github/workflows/ci.yml, release.yml
docs/   — GUIDE.md CHANGELOG.md HANDOFF.md TROUBLESHOOTING.md MODEL-GUIDE.md ROADMAP.md
docs/superpowers/specs/  — 2026-07-01-v0.13-drive-organizer-design.md (the full v0.13.0 design doc)
docs/superpowers/plans/  — the 8 implementation plans that built v0.13.0, one per subsystem
docs/archive/  — design notes (council, taxonomy-generator, gui-vision), old build plan, html mockups
ROOT (only):  README.md  LICENSE  pyproject.toml  MANIFEST.in  requirements.txt  run.bat  build-exe.bat  run_cli.py  run_gui.py
```

### Classification tiers (`classify()`), trust high→low
**`EMBED`** (model-free, default for every non-vision file) → **`VISION`** (model, only when there's
no extractable text at all; still `99UNS`? page-3, `vision3`). EMBED gates on **two independent
confidence thresholds** (`--stream-threshold`/`--subject-threshold`, config defaults 0.3/0.45) — real
testing found STREAM and SUBJECT scores don't move together (a shared threshold systematically
rejected one axis; see GUIDE.md §7 for the evidence). Below either → `99UNS`, **never escalated to a
model**. `TEXT`/`ESCALATE`/`FRONTIER` (the pre-v0.13.0 model-calling tiers for non-vision files) no
longer exist on that path — `--frontier` is still a valid flag and `llm()`'s `claude`/`cmd` backends
still work, but nothing in `classify()` calls them anymore (vision path never did either). This is a
known, not-yet-closed loose end — see §7.

### Ground-truth index (`index.py`, `tree.py`) — NEW in v0.13.0
SQLite snapshot of drive state (path/size/hash/embedding/mtime), distinct from the run journal below
(index = current-state snapshot, disposable/rebuildable; journal = action-log, durable). Scans
recurse into `.zip` (nested zips, depth-capped default 6, size-budget-capped). **Must skip any file
starting with `_docsort`** (`index._is_own_artifact()`) — the db/journal/log files are routinely
placed *inside* the root being scanned, and a real bug (indexing the index's own db file) was found
and fixed this way. `DirectoryTree.from_index(conn, root)` is the *only* correct way to derive
parent/child structure from the index — it's scoped to `root`; a raw `SELECT path FROM files` +
`os.path.dirname()` walk (the old approach, now deleted) also returns filesystem ancestors *above*
root, which caused two separate real bugs before DirectoryTree existed.

### Run journal (robustness backbone) — JSONL
`_docsort_state.jsonl` in the working dir, one flushed line per file:
`{rel, name, mtime, status, stream, subject, type, conf, source, dst, error, ts}`, `status ∈
done|failed|skipped`. Source of truth for `--resume`, `--retry-failed`, `--undo`, `--apply-journal`,
and the report. Clean/Reorg have their own separate JSONL logs (`_docsort_clean_log.jsonl`,
`_docsort_reorg_log.jsonl`) rather than sharing this one — different action shape (quarantine-move /
flatten-move vs rename), same dry-run/apply/journal-backed pattern.

### GUI ↔ engine
The Flet GUI spawns the existing `docsort` CLI as a subprocess (`runcore.RunController`) and parses its
`PROGRESS` / per-file result-row stdout into typed events (`progress`/`file`/`log`/`done`). **No engine
re-implementation.** This seam is unchanged by v0.13.0 — and v0.13.0's new commands (`--scan`,
`--clean-report`, `--apply-clean`, `--reorg-report`/`--apply-reorg`, `--recon-report`) have **no GUI
wiring at all yet**; they're CLI-only. See §7.

### Outputs per run
`_docsort_state.jsonl` (journal), `_docsort_log.csv`, `DOCSORT-REPORT.md`, appended record in the
global lifetime `index.jsonl` (`%APPDATA%\docsort\`) — plus, for the drive-organizer commands:
`_docsort_index.db`, `_docsort_clean_log.jsonl`, `_docsort_reorg_log.jsonl`.

---

## 4. Tag vocabulary (`TAGS.md` — single source of truth)
Unchanged by v0.13.0. Injected into the prompt AND the only codes the parser accepts (off-list →
`99UNS`). Filename prefix uses **STREAM-SUBJECT only**; TYPE+CONF go to the log.
- **STREAMS (6):** `CW GATE PROJ RES REC REF`
- **SUBJECTS (17 + NA + 99UNS):** EE topics `00MM 01CA 02SEMI 03PN 04BJT 05MOS 06OPAMP 07ANLG 08DIG 09SNS
  10CTRL 11COMM 12EMAG 13TOOLS` + foundation `90HUM 91PHY 92CHEM` + `NA` + `99UNS`
- **TYPES (11):** `notes pyq book slides assignment lab report datasheet syllabus solution misc`
- **Self-growth:** `99UNS PROPOSE:LABEL` → `[STREAM-~LABEL]` (pending); `--report` tallies; promote in the
  Tags editor, then `--retag`.
- These same STREAM/SUBJECT descriptions are now also the **zero-shot centroid seed text** for EMBED
  and Recon — editing `TAGS.md` changes classification behavior immediately, no retraining.

---

## 5. Feature set & key flags
**Commands:** `docsort` (CLI), `docsort-gui` (Flet GUI, v0.13.0-feature-free).
**v0.13.0+ flags:** `--scan`, `--clean-report`, `--apply-clean DIR`, `--reorg-report`, `--apply-reorg`,
`--stream-threshold`, `--subject-threshold`, `--recon-report` (unreleased). Full description of each
in `GUIDE.md` §2.5 and §5.
**Pre-v0.13.0 flags (unchanged):** `--apply --copy --misc/--no-misc --skip-unknown --vision --frontier
none|claude|cmd --move DEST|@archive --review --report --undo --stats --retry-failed --retag --resume
--exclude --include --list-models --edit-tags --host --location --apply-journal`.

**Safety:** dry-run by default (`--apply`); `--copy` works on a `<name>COPY`; `--undo` reverses all
journal-recorded renames/moves; `--skip-unknown` leaves `99UNS` untouched. Clean/Reorg apply to a
quarantine dir / in-place flatten respectively, both journal-backed, both dry-run-by-default via the
`-report` vs `apply-` flag pairing.

**GUI (Flet):** unchanged from v0.12.3 — folder picker, host + live model picker, frontier dropdown,
Run/Apply audited/Stop, progress hero, counters, live feed, verbose log (Run tab); tag editor + 5
run-option toggles (Tags tab); lifetime stats + embedded Folders + embedded Reports viewer (Stats
tab). No v0.13.0 feature is reachable from the GUI.

---

## 6. Version log

| Version | Gist |
|---|---|
| 0.8.0–0.10.2 | See CHANGELOG.md — rename, journal, GUI groundwork, docs-only release. |
| 0.11.0 | GUI rebuilt on Flet — nav rail + Run/Tags/Folders/Reports/Stats. `runcore.py` + `tagsio.py`. |
| 0.11.1 | GUI hotfixes — FilePicker-as-service, exe bundling fix. |
| 0.12.0 | `--apply-journal` (fast apply) — replay a dry-run's decisions as renames, zero model calls. |
| 0.12.1 | GUI hotfixes — no console window, Run/Apply-audited work in the packaged exe. |
| 0.12.3 | GUI nav rail 5→3 tabs (Folders/Reports folded into Stats); `99UNS` defaults flipped. |
| **0.13.0** | **Drive-organizer backend** — ground-truth index (archive-aware), Clean (3-layer dedup + vendor-dump), EMBED cascade tier (replaces TEXT/ESCALATE/FRONTIER for non-vision files), Reorg (thin-chain flatten). Released, tagged, exes published. |
| *(unreleased, on `main`)* | Architecture fixes: `DirectoryTree` (2 real bugs fixed), `index_session()` consolidation (1 real bug fixed — index self-scanning its own db). New **Recon** feature (`recon.py`, `--recon-report`, optional GPU embedder via `[recon]` extra). |

Git: `main` pushed to origin, tree clean, well past the v0.13.0 tag. **Not yet tagged as v0.14.0** —
no release instruction given for the post-v0.13.0 work yet.

---

## 7. Open / deferred items (resume here) — full list in `docs/ROADMAP.md`

**Separate project (not docsort):**
- **LLM Council** — universal API endpoints + a controller model managing other models. In
  development by the user; docsort will consume its endpoint as a future tier once integration is
  defined. Design note: `docs/archive/council.md`. Do NOT build inside docsort.

**Deferred from the v0.13.0 architecture review (see `docs/superpowers/specs/`):**
- **Hybrid multi-tag VISION/FRONTIER output** — needs a system-prompt wording change validated
  against a live model; this dev environment has no LM Studio access to verify it safely.
- **GUI surfacing for every v0.13.0+ feature** (Run-tab EMBED hit-rate counter, Clean/Reorg report
  views, Tags-tab tag-model split, Recon results) — needs a human visual smoke-test (GUI is
  headless-unverifiable by an agent, see §9) and none of it has been attempted yet.
- **Everything HTTP API integration** for fast enumeration — `os.walk` fallback works fine today;
  this is a perf-only nice-to-have, explicitly deprioritized by the user.
- **`classify()`'s `ClassifyConfig` refactor** (Candidate 3) — attempted, found to require also
  redesigning `llm()`'s interface (it reaches into the whole argparse Namespace internally, same
  issue one level down) — out of the originally reviewed scope, not implemented.
- **`build_run_cmd()` duplication** (Candidate 5) — genuinely low value, explicitly deprioritized.
- User's own framing: "we'll address 4 and 5 [GUI, command-builder dedup] when the next version
  with the above implementation is done, if any bug be found" — i.e., revisit opportunistically,
  not proactively.

**Planned features (pre-existing, still deferred):**
- **Taxonomy Generator** — interactive wizard: folder tree → generated `TAGS.md`/`system_prompt.md`
  via a small CPU-capable LM Studio text model; de-personalizes the taxonomy (public blocker #2).
  Design: `docs/archive/taxonomy-generator.md`.
- **Background processing + system tray**, **single unified Windows package**, **GUI config
  persistence**, **in-process engine boundary** (replace subprocess + line parsing).

**Public-release blockers (still open):** (1) accuracy unproven at scale for the NEW EMBED tier
specifically — the old benchmark methodology (MODEL-GUIDE.md) tested LLM tiers only; EMBED needs its
own accuracy benchmark against a real hand-labelled corpus, not yet done; (2) personalized taxonomy →
Taxonomy Generator; (3) effectively Windows-only; (4) unsigned exe (SmartScreen).

---

## 8. Hardware & environment
- **Primary:** laptop, RTX 3050 **4 GB VRAM**, 16 GB RAM. LM Studio at `localhost:1234` — only
  relevant to VISION-tier files now. Future 8 GB box → run 2 models concurrently.
- Models seen: `qwen3-vl-8b`, `qwen/qwen3-vl-4b`, `qwen2.5-vl-3b-instruct` (+7B). Keep the LM Studio
  GGUF stack for VISION-tier. See `docs/MODEL-GUIDE.md` (updated to clarify it's VISION-tier-only now).
- Recon's optional GPU embedder (`sentence-transformers`, `[recon]` extra) auto-selects CUDA if
  available, else CPU — separate concern from LM Studio, not installed in the dev `.venv` here.

---

## 9. ⚠️ Warnings / gotchas for next session
- **GUI is headless-unverifiable by an agent** — a Flet window can't be opened in a subagent/CI. GUI code is
  validated by constructing the control tree against a stub page + unit tests; **a human visual smoke-test is
  the gate before merge/tag.** No GUI code has been touched since v0.12.3 — every v0.13.0+ feature is
  CLI-only and has zero GUI representation.
- **`sentence-transformers`/`torch` are NOT installed in this dev `.venv`** — recon's tests exercise
  the real stdlib-fallback path (not mocked), which is correct/intentional, but the GPU-embedder path
  itself has never been run or verified in this environment. Don't assume it works untested on a real
  machine with the extra installed.
- **Any new docsort-owned state file must start with `_docsort`** — `index.scan_root()`/
  `scan_directory()` skip that prefix specifically; a new artifact file with a different name would
  silently get indexed as data (the exact bug already found and fixed once).
- **`DirectoryTree.from_index(conn, root)` requires `root`, always** — there is no unscoped directory
  enumeration left in the codebase (`index.list_directories()` was deleted after migration); don't
  reintroduce one.
- **EMBED thresholds are a starting point, not tuned** — real testing found the stdlib embedding's
  STREAM-axis signal is often weaker than pure gibberish for subject-vocabulary-heavy text; no
  threshold value fully solves this without also enriching the STREAM centroid seed text (not done).
  Expect real-world runs to need threshold retuning via `--report`.
- **Flet 0.85.3 API differs from older docs** — use `ft.run` (not `ft.app`), `ft.Icons`/`ft.Colors`
  (uppercase), **FilePicker is a Service → `page.services`**. Introspect the installed package.
- **Editable install + PyInstaller:** docsort is `pip install -e .` in the dev `.venv`, so PyInstaller
  needs `--paths=.`. `build-exe.bat`/release.yml already do this.
- **Source-data folder:** `D:\Sort\Backup Home PC1\Documents` for real runs.
- **Load a Qwen-VL model in LM Studio** before a real VISION-tier pass.

---

## 10. Working agreements / preferences
- **GUI is the primary surface**; CLI is the clean programmatic/agentic surface — though currently
  the GUI lags the CLI by a full feature generation (v0.13.0). Stay on the **LM Studio GGUF stack**
  for VISION. Renaming-only is considered safe (journal-backed undo); unknowns left untouched.
- **Prefer model-free approaches when feasible** — explicit user directive: "prevent model usage
  since it has been proven using llms takes lots of processing time." This is why EMBED replaced
  TEXT/ESCALATE/FRONTIER for non-vision files, and why Recon is model-free-by-default too.
- **New tunable knobs → config file, not new GUI widgets** — user preference, stated explicitly when
  scoping v0.13.0's UI changes. Only per-run actions (Run/Stop/Apply-style) justify a dedicated control.
- Process: features designed (brainstormed) before building; committed in small, tested increments on a
  feature branch then merged `--no-ff` to `main`; every `v*` tag auto-ships exes. Semver: new
  flags/features → minor bump, pure fixes → patch. Docs-only changes commit directly to `main`, no
  feature branch (matches the v0.10.2 precedent).
- **Real bugs found during refactors get fixed and documented as findings, not silently absorbed** —
  3 were found and fixed this cycle (index self-scanning its own db; two DirectoryTree-migration
  scoping bugs) via test-first discipline, not by inspection alone.

---

### Start here (next session)
Likely next moves, in priority order:
(a) **Version-bump/tag/release the post-v0.13.0 work** (DirectoryTree fixes, index_session, Recon) as
    v0.14.0 — not yet done, no release instruction given for it yet.
(b) **GUI surfacing** for the whole v0.13.0+ feature set — biggest visible gap, needs a human in the
    loop for the visual smoke-test regardless of who builds it.
(c) **EMBED-tier accuracy benchmark** on a real hand-labelled corpus — the #1 public blocker is now
    specifically about the new tier, not the old LLM tiers.
(d) **Taxonomy Generator** — still designed-but-unbuilt; design ready in `docs/archive/taxonomy-generator.md`.
(e) **Council integration** — only once the user shares the council project's endpoint.
Full v0.13.0 design: `docs/superpowers/specs/2026-07-01-v0.13-drive-organizer-design.md`. The 8
implementation plans that built it are in `docs/superpowers/plans/`, one per subsystem — useful
reference for the module boundaries and TDD approach used throughout.
