# docsort — Roadmap

Living document. Tracks what's shipped, what's planned, and what is a *separate* project vs. in-repo work.
Full historical state lives in [`HANDOFF.md`](HANDOFF.md); per-release detail in
[`CHANGELOG.md`](CHANGELOG.md).

## Shipped

| Version | Gist |
|---|---|
| 0.8.0 | Rename to `docsort`, pip package, per-user data dir, dark GUI, model picker, `--copy`, `--misc`. |
| 0.9.0 | Run journal, `--resume`, server-health guard, live progress GUI. |
| 0.10.0 | Exclude/include, reports + lifetime stats, `--undo`, `--retry-failed`, structured tag editor, MODEL-GUIDE, tests, exe release. |
| 0.10.1 | `--skip-unknown` toggle (leave `99UNS` untouched). |
| 0.10.2 | **Docs only** — design notes (council, taxonomy generator, GUI vision), this roadmap, source-path update. No code changes. |
| 0.11.0 | **GUI rebuilt on Flet** — nav rail + Run view (progress/time/ETA/counters/feed/log) + Tags/Folders/Reports/Stats. New `runcore.py` + `tagsio.py`. Engine unchanged. |
| 0.11.1 | GUI hotfixes — FilePicker as a Flet service (picker timeout), dropdown labels, threaded model refresh; exe bundling fix (`flet pack` + `--add-data`/`--paths`). |
| 0.12.0 | **`--apply-journal` (fast apply)** — replay a dry-run's journal decisions as renames, no model calls; + GUI "Apply audited" button. |

## Next — low priority

- **Sub-file progress** — intra-file % while the model works (e.g. LM Studio prompt-eval). Not exposed by the
  OpenAI HTTP API docsort uses (only final `usage`); would need `stream:true` (little value — tiny generation)
  or tailing LM Studio's log (fragile, version-specific). Deferred.
- **GUI visual verification** — the Flet GUI is validated by headless control-tree construction + unit tests;
  a full visual/interaction smoke-test on each release is still a manual step.

## Planned — later versions

- **Background processing + system tray** — run minimized / keep working from the tray so a long batch
  doesn't tie up a window. (Out of scope for the v0.11.0 visual overhaul.)
- **Single unified Windows package** — one Windows release artifact (installer/package) instead of the
  current two PyInstaller exes. Ties into the Flet build/packaging story.
- **Taxonomy Generator** — interactive wizard: tree → generated `TAGS.md` / `system_prompt.md`, on a small
  CPU-capable text model via LM Studio. De-personalizes the taxonomy (public blocker #2). Designed and
  deferred; its wizard dialog plugs into the Flet shell. See
  [`archive/taxonomy-generator.md`](archive/taxonomy-generator.md).
- **Engine debt** — transient single-retry (one retry on an empty model reply before `99UNS`), GUI config
  persistence (Host/Model fields), and the in-process engine boundary (replace subprocess + line parsing).

## Separate projects (not docsort work)

- **LLM Council** — universal API endpoints + central controller model managing other models
  ("poor man's MoE", accuracy over speed). A standalone project in development; docsort will consume its
  endpoint as a future `99UNS` escalation tier once integration is defined. See
  [`archive/council.md`](archive/council.md).

## Public-release blockers (tracking)

1. **Accuracy unproven at scale** — only run on a small sample. Benchmark on 50–100 hand-labelled files
   via the auto-`DOCSORT-REPORT.md`. (Renaming-only + untouched unknowns keep real runs low-risk in the
   meantime.) Method in [`MODEL-GUIDE.md`](MODEL-GUIDE.md).
2. **Personalized taxonomy** — addressed by the Taxonomy Generator above.
3. **Effectively Windows-only** (.doc COM, exe, paths). Mac/Linux untested.
4. **Unsigned exe** — SmartScreen warnings for public downloaders.
