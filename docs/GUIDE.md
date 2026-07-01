# docsort — Guide

## 1. What the model receives (VISION tier only)

As of v0.13.0, **only the VISION tier calls a model at all.** Non-vision files (the vast majority —
anything with extractable text) are classified entirely by the model-free EMBED tier: zero LLM calls,
zero processing-time cost. See §2.

For the one tier that still calls a model:
- **SYSTEM** = the `<SYSTEM>` block of `system_prompt.md` with `{{STREAMS}}/{{SUBJECTS}}/{{TYPES}}`
  filled from `TAGS.md` (single source). Same every call.
- **USER** = `Filename / Folder / (handwritten/scanned page) Answer (STREAM SUBJECT TYPE CONF):` +
  the page rendered to PNG.
Settings: `temperature=0`, `max_tokens=24`. Reply is one line, e.g. `CW 12EMAG notes high`
(or with a discovery: `CW 99UNS notes high PROPOSE:THERMO`).

## 2. Classification tiers (in order)
1. **EMBED** — the default and only tier for non-vision files. A stdlib hashing-trick embedding
   (no ML dependency) of filename+folder+extracted text is matched against zero-shot centroids built
   from `TAGS.md`'s own STREAM/SUBJECT descriptions. Two independent confidence cutoffs
   (`--stream-threshold`, `--subject-threshold` — see §5) — clears both → tagged, `source=embed`. A PDF
   whose first pass misses gets one more try against a deeper 5-page extract (`source=embed5`, still no
   model call). Below cutoff on either axis → `stream=CW subject=99UNS source=embed-unsure`, left for
   `--review`/manual promotion, same as any other unsure file — **never escalated to a model.**
2. **VISION** *(the one exception)* — only when there's no extractable text at all (scanned/handwritten
   PDF) and `--vision` is set: render page 1 → vision model; still `99UNS`? page 3 → `vision3`. This is
   the only path with a real processing-time cost, since there's nothing reliable to embed.
Trust order: `embed > embed5 > vision > vision3` (the `source` column). `TEXT`/`ESCALATE`/`FRONTIER`
(pre-v0.13.0 model-calling tiers) no longer exist on the non-vision path — see CHANGELOG v0.13.0.

## 2.5 Drive-organizer features (v0.13.0+)

Beyond per-file tagging, docsort can also clean up and triage a whole messy drive. All of these are
their own CLI passes — dry-run first, journal-backed apply, same safety pattern as tagging:

- **Scan** (`--scan`) — builds a ground-truth SQLite index (`_docsort_index.db`) of the whole tree,
  including recursing into `.zip` archives (nested zips, depth/size-capped).
- **Clean** (`--clean-report` / `--apply-clean`) — three dedup layers (exact-hash, whole-duplicated-
  folder-subtree, embedding-based near-duplicate) plus a vendor-dump detector (flags
  `repo-master`/`repo-main`-style GitHub download folders). Confirmed items move to a quarantine
  folder you specify, never deleted directly.
- **Reorg** (`--reorg-report` / `--apply-reorg`) — detects thin single-child folder chains (nesting
  that adds depth with no organizational value) and proposes flattening them.
- **Recon** (`--recon-report`) — the fastest, lightest pass: no index, no model, **no file content read
  at all**. Walks every file and folder *name* in the tree and suggests a high-level STREAM/SUBJECT from
  the name alone, for a quick structural overview before running anything else. Optional
  `pip install "docsort[recon]"` extra adds a real GPU-capable embedding model (auto CUDA/CPU); without
  it, recon still works via the same built-in embedder Clean's near-duplicate layer uses.

Full design: `docs/superpowers/specs/2026-07-01-v0.13-drive-organizer-design.md`.

## 3. The tag scheme — known + discovered
- **Prefix `[STREAM-SUBJECT]`** is the only thing added to the name. STREAM peels GATE/PROJ/RES/REC
  from CW; SUBJECT unifies coursework by topic. TYPE/CONF go to the log only.
- **Known tags** live in `TAGS.md` (6 streams · 17 subjects + NA/99UNS · 11 types). The model is
  constrained to these → mutually exclusive, decisive.
- **Discovered tags**: a coherent subject not in the list → `99UNS PROPOSE:<LABEL>` → file written
  `[STREAM-~LABEL]` (the `~` = pending review, **not auto-moved**). `--review` tallies them; promote a
  recurring one into `TAGS.md`, then `--retag` re-files the `~LABEL` files into the new real code.

## 4. Full workflow
```
0. DEDUP         dupeGuru: Scan Type Folders, then Contents; Re-Prioritize (suffix down);
                 Move Marked to quarantine. Kill copies BEFORE tagging.
1. CONFIG        %APPDATA%\docsort\config.json: host -> your LM Studio; locations -> folder(s)
2. TAG dry-run   docsort --location academics            (or a raw path)
                 -> review _doc_handler_log.csv   (or: --review -> TAG-REVIEW.md)
3. TAG apply     docsort --location academics --copy --apply    (--copy keeps originals safe)
4. (optional)    promote any ~PROPOSE tags via --edit-tags, then:  ... --retag --apply
5. MOVE          docsort --location academics --move @archive          (dry-run)
                 docsort --location academics --move @archive --apply
6. SPECIAL       handle <archive>/{GATE,PROJ,RES,REC} folders separately
```
GUI equivalent: `docsort-gui` — a Flet app with a nav rail (Run / Tags / Stats — Folders and Reports
live inside Stats as of v0.12.3, the run-option toggles live on Tags), live progress + per-file feed
+ verbose log, and an **Apply audited** button that runs `--apply-journal` (rename the reviewed
dry-run results without re-classifying).

## 5. Flags
| Flag | Purpose |
|---|---|
| `--location NAME` / `root` | folder from config, or a raw path |
| `--host NAME\|URL` | model endpoint (config `hosts` name or URL) |
| `--vision [--vision-model M]` | enable image tier for no-text PDFs (config default: on) |
| `--copy` | copy the folder to `<name>COPY` and tag the copy (originals untouched) |
| `--apply` | rename (default is dry-run) |
| `--misc` / `--no-misc` | sweep `99UNS` files into a `misc\` subfolder (**default ON**) |
| `--skip-unknown` | leave `99UNS` (unknown) files completely untouched — no rename, no move |
| `--move DEST` / `--move @archive` | relocate prefixed files into DEST/STREAM/SUBJECT |
| `--edit-tags` | open your `TAGS.md` in an editor, then exit |
| `--review` | aggregate log → TAG-REVIEW.md (offline) |
| `--retag` | re-classify already-prefixed files (after tuning/promoting) |
| `--frontier claude\|cmd` | hard-99UNS fallback (see §6); `claude` is bound to haiku |
| `--backend local` | main backend |
| `--resume` | skip files already `done` in the run journal (after a pause/crash) |
| `--retry-failed` | re-process only files marked `failed` in the journal |
| `--undo` | reverse the renames/moves recorded in the journal (restore originals) |
| `--apply-journal` | apply a prior dry-run's audited decisions from the journal (rename/move only, **no model calls**); skips files changed since the audit. The fast counterpart to `--apply` after you've reviewed a dry-run |
| `--exclude PATH` / `--include PATH` | skip / restrict-to folders (repeatable; also config `exclude`/`include`) |
| `--report` | (re)build `DOCSORT-REPORT.md` from the journal + update the global index (offline) |
| `--stats` | print lifetime totals from `%APPDATA%/docsort/index.jsonl`, then exit |
| `--list-models` | list models loaded in LM Studio (at `--host`), then exit |
| `--edit-tags` | open your `TAGS.md` in an editor, then exit |
| `--stream-threshold` / `--subject-threshold` | EMBED-tier confidence cutoffs (0.0-1.0), one per axis (config defaults: 0.3 / 0.45 — see §7 for why they're separate) |
| `--scan` | build/refresh the ground-truth index (`_docsort_index.db`) for root, then exit — no model, no classification |
| `--clean-report` | index (if needed) + print a dedup/vendor-dump report (exact-hash, duplicate-subtree, near-duplicate, vendor-dump groups), then exit |
| `--apply-clean DIR` | apply the Clean report's findings — quarantine-move confirmed items into `DIR`, journal-backed (`_docsort_clean_log.jsonl`) |
| `--reorg-report` | index (if needed) + print thin single-child-folder-chain flatten proposals, then exit |
| `--apply-reorg` | apply the reorg-suggester's flatten proposals, journal-backed (`_docsort_reorg_log.jsonl`) |
| `--recon-report` | **no index, no model, no content read at all** — walks every file/folder *name* in root and suggests a high-level STREAM/SUBJECT per entry, before Scan/Clean/Classify touch anything (see §2.5) |

**Robustness:** runs are crash-safe — a journal (`_docsort_state.jsonl`) is written per file. Ctrl-C
pauses gracefully (`--resume` continues). If LM Studio drops mid-run, docsort stops with a resume
hint instead of mislabeling the rest `99UNS`. Each run also emits `PROGRESS i/N … tps=… eta=…s` lines
(the GUI turns these into a progress bar + tok/s + ETA).

## 6. Backends (all key-free)
- **local** — LM Studio (default). Free, no key. The recommended main backend.
- **frontier claude** — Claude Code CLI on your **Claude subscription, NO API key**. Bound to the
  **haiku** model (standard context, sub-covered). Slower (~30 s/file) — use only for hard cases.
- **frontier cmd** — `--frontier-cmd "<shell template>"`, prompt piped via stdin → wire ANY local/
  sub CLI without a key.
- *(No OpenAI/ChatGPT backend — the API path was removed; a ChatGPT web sub is not an API.)*

## 7. Tuning
- Add/edit tags in **`TAGS.md`** only — via **Edit Tags** (GUI) or `docsort --edit-tags`.
  Changes flow to both the script and the model prompt. Sharpen rules/examples in `system_prompt.md`.
- User files live in `%APPDATA%\docsort\` (Windows) / `~/.docsort/`. `config.json` holds
  endpoints, named hosts, locations, archive_root, and `min_text/deep_pages/dpi`. Reinstalling never
  overwrites your edited copies.
- **Models auto-resolve for any user:** if the model id in config isn't loaded in LM Studio, the app
  picks whatever VL model *is* loaded (see the `[model] ->` / `[vision] ->` line). You rarely need to
  set the exact id.
- **EMBED thresholds are two separate knobs, not one, deliberately.** Real testing against the full
  `TAGS.md` vocabulary found STREAM and SUBJECT scores don't move together — e.g. BJT-heavy text scores
  ~0.7 on SUBJECT but only ~0.25 on STREAM, since STREAM's descriptions are short/generic and SUBJECT's
  are technical/specific. A shared threshold systematically rejected one axis. Config defaults
  (`stream_embed_threshold: 0.3`, `subject_embed_threshold: 0.45`) are a starting point — retune against
  your own corpus via `--report`/`TAG-REVIEW.md`, the same workflow already used to promote `~LABEL`
  proposals. More files landing in `99UNS` than expected usually means one threshold is too strict for
  your material, not a bug.

## 8. Reviewing & reversibility
- `--review` → TAG-REVIEW.md: distribution, proposed (`~`) tags, low-confidence list.
- Eyeball `conf=low`, `source=filename/vision/frontier`, `subject=99UNS`.
- Renames reversible via the log `old`/`new`; moves via `_move_log.csv` (`from`/`to`).

## 9. Troubleshooting
| Symptom | Fix |
|---|---|
| Server unreachable / hangs | start LM Studio; enable LAN + firewall TCP 1234 (see TROUBLESHOOTING.md) |
| Every file `99UNS` | weak model — use a 7B/8B vision model, or `--frontier claude` |
| Configured model not used | not loaded; auto-resolve picked a loaded one (see `[model] ->` line) |
| PDFs skipped | `pip install pymupdf` (bundled as a dependency; reinstall if missing) |
| `.docx/.pptx` skipped | `pip install "docsort[office]"` |
| `.doc` filename-only | needs Word + `pip install "docsort[doc]"` (pywin32), or convert .doc→.docx |
| frontier claude empty / not found | install Claude Code, run `claude` once to log in; it uses `--model haiku` |
| GUI won't start | needs the `[gui]` extra (Flet): `pip install "docsort[gui]"`. The prebuilt `docsort-gui.exe` already bundles it. |
