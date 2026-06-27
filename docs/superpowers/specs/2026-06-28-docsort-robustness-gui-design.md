# docsort — Robustness + GUI overhaul (design/spec)

Date: 2026-06-28 · Status: approved, building Phase 1+2

## Goal
Make runs observable, interruptible, and crash-safe, with a GUI that shows live
progress / token-speed / ETA. CLI stays the clean programmatic surface; GUI is the
UX focus. Fixes a real bug: if LM Studio drops mid-run, every remaining file is
silently mislabeled `99UNS`.

## Backbone: run journal (Approach 2)
`_docsort_state.jsonl` in the working dir. One flushed line per file:
`{rel, name, mtime, size, status, stream, subject, type, conf, source, error, ts}`
`status ∈ done | failed | skipped | excluded`. Source of truth; CSV/report derived.

## Phase 1 — CLI backend (feeds the GUI)
- Materialize target list → know `N` up front.
- Per-file: time `classify()`, accumulate completion tokens from LM Studio response
  `usage`. Append a journal line (flushed). On exception → `status=failed`, continue.
- Emit one machine-parseable line per file:
  `PROGRESS i/N done=D failed=F tps=T toks=K eta=Es`
  (tps = rolling tok/s; eta = remaining × avg time; best-effort, `—` if unknown).
- **Server-health guard:** track files where the model returned nothing. After 3
  consecutive dead files, re-ping `/v1/models`; if down, print
  `server unreachable — D done, resume with --resume`, flush, exit 3 (no mislabel).
- `--resume`: skip files already `done` in journal (match rel+mtime).
- Journal lives in the processed dir (the COPY when `--copy`).

## Phase 2 — GUI overhaul (primary)
- Parse `PROGRESS` lines from the streamed subprocess stdout.
- **Stats strip:** progress bar `i/N` + %, tok/s (rolling), total tokens, done/failed,
  elapsed, `~ETA`. Missing value → `—`, never blocks.
- **Stop** button: terminate subprocess (per-file flush = resumable). Re-enables Run.
- Keep existing log pane below the strip.

## Deferred (later phases, designed not built)
- Phase 3: Exclude/Include folder tabs (config `exclude`/`include` + CLI + filter;
  excluded files logged `status=excluded`). Hook: `folder_tags` map for direct tagging.
- Phase 4: `DOCSORT-REPORT.md` per run + global `%APPDATA%/docsort/index.jsonl` +
  `--undo` / `--retry-failed` / `--stats` / `--report`, and a GUI Report tab.

## Non-goals
ETA accuracy (psychological only). No dedicated OCR pipeline. No OpenAI backend.
