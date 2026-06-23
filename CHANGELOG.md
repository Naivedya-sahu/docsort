# Changelog — Doc-handler

All notable changes. Newest on top.

## [0.7.1] — 2026-06-23
### Fixed
- **Frontier `claude` (subscription, no API key) now actually works.** Three bugs:
  (1) `shell=True` + list arg mangled the multiline prompt on Windows → removed shell;
  (2) ran inside the repo so Claude Code read project files / global CLAUDE.md → now runs
  from a neutral cwd with a directive one-shot prompt; (3) default model needed paid 1M-context
  credits → pin `--model haiku` (standard-context, sub-covered). Verified: returns a clean
  `STREAM SUBJECT TYPE CONF [PROPOSE:LABEL]` and discovered `PROPOSE:THERMO` live.
### Added
- Generic **`--frontier cmd`** + `--frontier-cmd "<template>"` (prompt piped via stdin) to wire
  ANY local/subscription CLI without an API key. `--frontier-model` (default `haiku`).

## [0.7.0] — 2026-06-23
### Added
- **`.doc` (old binary Word) reader** via a reused Word COM instance (Windows + Word + `pywin32`).
  Falls back to filename tier if Word/pywin32 absent. Optional dep `pip install .[doc]`.
- **`--retag`**: re-classify already-prefixed files — re-runs the model on the content and
  rewrites the prefix. Use after tuning the prompt or promoting a `~PROPOSE` tag to a real code.
### Fixed
- **Tool's own outputs were treated as inputs** — `TAG-REVIEW.md` (and README/CHANGELOG/etc.)
  could be classified/renamed. Now skipped (`SKIP_NAMES`, `_doc_handler*`, `_move*`).
- **Frontier `claude` on Windows** — resolve `claude`/`claude.cmd` via `shutil.which` + `shell`
  on Windows, instead of silently failing to 99UNS.

## [0.6.1] — 2026-06-23
### Fixed
- **TUI broke in cmd.exe** — v0.5.0 forced `legacy_windows=False`, which emits raw ANSI/VT that
  cmd doesn't render, and the 🐵 emoji / braille spinner / unicode box chars aren't in cmd's
  codepage. Now: auto-detect terminal, enable VT via `os.system("")`, and render **ASCII-safe**
  (no emoji, `line` spinner, `+-|` box, `#` bars). Works in cmd.exe **and** Windows Terminal.
- TUI apply path is now collision-safe (`unique_path`), matching the CLI.

## [0.6.0] — 2026-06-23
### Added
- **Foundation subjects** `91PHY` (physics), `92CHEM` (chemistry) — physics no longer forced into EE codes.
- **Tag evolution / proposals**: model can answer `99UNS PROPOSE:<LABEL>`; the file is written
  `[STREAM-~LABEL]` (the `~` = review symbol, not auto-moved). `--review` tallies them into
  `TAG-REVIEW.md` so recurring proposals can be promoted into `TAGS.md`.
- **`--review`** offline aggregator: distribution, proposed tags, low-confidence list.
- Prompt tuning: decide from real content; syllabus/scheme → `REF 99UNS`; prefer `99UNS` over a
  low-confidence guess; physics→91PHY / chem→92CHEM.
### Fixed (from an edge-case audit)
- **Tag matching used substrings** → `NA` matched inside "FINAL", `lab` inside "syllabus"
  (mislabeled types). Now word-boundary matched.
- **Move could overwrite same-named files (data loss)** and **failed cross-device** (archive on
  another drive). Now `shutil.move` + `unique_path` (never overwrite).
- Tagging rename now collision-safe (`unique_path`).
- **A single LLM HTTP error crashed the whole run** → now caught, that file → 99UNS.
- **Unreachable model server hung 180s/file** → now aborts with a clear message.
- `--move @archive` with empty `archive_root` now errors instead of moving into CWD.
- TUI `Table.box=None` mutated rich globally; removed. `max_tokens` 16→24 for 5-token answers.

## [0.5.1] — 2026-06-23
### Added
- **Model auto-resolve**: if the configured model id isn't loaded on the server, fall back to a
  loaded one (vision-preferring) instead of failing — handles "models may change" and remote hosts.
### Fixed
- **Packaging**: `config` and `tui` were missing from `py-modules`, so `pip install` left imports
  broken. Now all three modules install; `doc-handler` console entry verified.
### Tested
- Remote-host config (`HOME` → `http://HOME:1234/...`) URL resolution, auto-resolve fallback,
  `pip install .` + console entry + imports — all verified.

## [0.5.0] — 2026-06-23
### Added
- **`config.py` + `config.json`** central config (model endpoints, named **hosts**, named
  **locations**, archive root, options). Precedence: CLI > config.json > defaults.
  Built for Pi5 deployment — point `host` at the laptop's LM Studio over Tailscale.
- CLI: `--config`, `--host` (name or URL), `--location NAME`, `--move @archive`. `root` is
  now optional when `--location` is given.
- `config.example.json` template with localhost/laptop-Tailscale hosts and local/mount locations.
- TUI + CLI read config defaults; per-run DPI/min_text/deep_pages now configurable.
### Fixed
- **Windows UTF-8 crash** in the TUI (emoji/unicode hit the cp1252 legacy console) — force
  UTF-8 stdout and disable the legacy Windows renderer.
### Tested
- End-to-end live run on real PDFs: text + vision tiers, rename, move, `--move @archive`,
  config-driven `--location`, and TUI rendering all verified.

## [0.4.0] — 2026-06-23
### Added
- **`TAGS.md` single source of truth** — STREAM/SUBJECT/TYPE/FACET lists live here; both the
  script (validation) and the injected system prompt read from it. `system_prompt.md` is now a
  template with `{{STREAMS}}/{{SUBJECTS}}/{{TYPES}}` placeholders filled at runtime.
- **Frontier fallback** for hard `99UNS` cases: `--frontier claude` (Claude Code CLI — uses the
  Claude subscription, text-only) or `--frontier openai` (needs `OPENAI_API_KEY`). `--backend openai`
  can also run the whole pass on a frontier model.
- **Animated TUI** (`tui.py`, Rich) — menu-driven tag/move with unicode spinners, live progress,
  and per-subject bar chart.
### Notes
- ChatGPT Plus/Go web subscription is NOT API-accessible; programmatic OpenAI use needs an API key.

## [0.3.0] — 2026-06-23
### Added
- **Page escalation**: when first-pass SUBJECT = `99UNS` on a PDF, re-read up to 5 pages
  (text) or page 3 (vision) and retry — fixes books/published PDFs whose page 1 is only
  cover / preface / copyright / table-of-contents.
- Packaged as self-contained **`Doc-handler/`** folder: README, GUIDE, CHANGELOG,
  requirements.txt, system_prompt.md.
- `requirements.txt` listing all software (pip + external apps) for independent use.
- Log `source` now distinguishes escalation tiers: `text5`, `vision3`.

## [0.2.0] — 2026-06-23
### Added
- **Two-axis tagging**: STREAM (CW/GATE/PROJ/RES/REC/REF) + SUBJECT (13 EE codes), so
  GATE/projects/research peel off while coursework unifies by subject.
- **Vision tier**: render page 1 → vision model for handwritten / scanned / vector PDFs.
- **`--move DEST`**: relocate `[STREAM-SUBJECT]` files into `DEST\STREAM\SUBJECT\`
  (replaces File Juggler), dry-run + reversible `_move_log.csv`.
- System prompt externalised to `system_prompt.md` (editable vocabulary).

## [0.1.0] — 2026-06-23
### Added
- Initial tagger: extract first pages → local LLM (LM Studio) → single SUBJECT code →
  `[CODE]` filename prefix. Dry-run by default, `--apply` to rename, CSV decision log.
- Cheap by design: classify by content, constrained to a fixed code list.

## Design notes
- Unifying axis = **SUBJECT** (reuses the GATE-EC KB's 13 categories) so the sorted
  archive mirrors the study KB.
- Decisive & mutually exclusive: one STREAM + one SUBJECT per file; uncertainty → 99UNS.
- Runs after dupeGuru hashed-dedup so duplicates aren't classified.
