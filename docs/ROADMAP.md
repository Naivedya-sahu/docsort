# docsort — Roadmap

Living document. Tracks what's shipped, what's planned, and what is a *separate* project vs. in-repo work.
Full historical state lives in [`HANDOFF.md`](../HANDOFF.md); per-release detail in
[`CHANGELOG.md`](../CHANGELOG.md).

## Shipped

| Version | Gist |
|---|---|
| 0.8.0 | Rename to `docsort`, pip package, per-user data dir, dark GUI, model picker, `--copy`, `--misc`. |
| 0.9.0 | Run journal, `--resume`, server-health guard, live progress GUI. |
| 0.10.0 | Exclude/include, reports + lifetime stats, `--undo`, `--retry-failed`, structured tag editor, MODEL-GUIDE, tests, exe release. |
| 0.10.1 | `--skip-unknown` toggle (leave `99UNS` untouched). |
| 0.10.2 | **Docs only** — design notes (council, taxonomy generator, GUI vision), this roadmap, source-path update. No code changes. |

## Planned — v0.11.0 (visual overhaul only)

In planning. The next version is a **pure visual/UX overhaul** of the GUI on **Flet** (Python) — a
Discord-like dark look with small minimal animations, tuned to keep the user engaged through long
patience-heavy runs, surfacing progress + time/ETA + throughput + per-file indicators prominently. **No
engine or behaviour changes**; the Flet UI drives the existing CLI via subprocess. See
[`design/gui-vision.md`](design/gui-vision.md).

## Planned — later versions (post-v0.11.0)

- **Background processing + system tray** — run minimized / keep working from the tray so a long batch
  doesn't tie up a window. (Out of scope for the v0.11.0 visual overhaul.)
- **Single unified Windows package** — one Windows release artifact (installer/package) instead of the
  current two PyInstaller exes. Ties into the Flet build/packaging story.
- **Taxonomy Generator** — interactive wizard: tree → generated `TAGS.md` / `system_prompt.md`, on a small
  CPU-capable text model via LM Studio. De-personalizes the taxonomy (public blocker #2). Designed and
  deferred; its wizard dialog plugs into the Flet shell. See
  [`design/taxonomy-generator.md`](design/taxonomy-generator.md).
- **Engine debt** — transient single-retry (one retry on an empty model reply before `99UNS`), GUI config
  persistence (Host/Model fields), and the in-process engine boundary (replace subprocess + line parsing).

## Separate projects (not docsort work)

- **LLM Council** — universal API endpoints + central controller model managing other models
  ("poor man's MoE", accuracy over speed). A standalone project in development; docsort will consume its
  endpoint as a future `99UNS` escalation tier once integration is defined. See
  [`design/council.md`](design/council.md).

## Public-release blockers (tracking)

1. **Accuracy unproven at scale** — only run on a small sample. Benchmark on 50–100 hand-labelled files
   via the auto-`DOCSORT-REPORT.md`. (Renaming-only + untouched unknowns keep real runs low-risk in the
   meantime.) Method in [`MODEL-GUIDE.md`](MODEL-GUIDE.md).
2. **Personalized taxonomy** — addressed by the Taxonomy Generator above.
3. **Effectively Windows-only** (.doc COM, exe, paths). Mac/Linux untested.
4. **Unsigned exe** — SmartScreen warnings for public downloaders.
