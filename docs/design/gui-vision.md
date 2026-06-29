# Design note — GUI visual overhaul (v0.11.0)

> Status: **v0.11.0 — in planning.** Scope is a **visual/UX overhaul only**: reskin and restructure the
> existing GUI on a modern framework. **No engine or behaviour changes** this version.
> Today's GUI is a functional but stale, fixed Tkinter app.

## Why a visual overhaul matters here

A docsort run requires **patience** — classifying a large archive is minutes of waiting while the model
works. A stale, fixed UI lets attention drift and the user walks away, leaving the batch half-done. The
overhaul's job is to keep the UI **alluring enough that the user stays cognitively engaged** through the
wait and sees the run to completion. This is a retention/completion concern, not decoration.

## Scope (locked)

- **Visual overhaul only.** Modern look, layout, and motion. Same features, same engine, same CLI behind it.
- **Framework: Flet** (Flutter, Python) — stay in one language, native animations, modern look, lighter than
  Electron. Chosen over Tauri (adds Rust/JS) and customtkinter (too limited).
- **UI ↔ engine: subprocess.** The Flet UI spawns the existing `docsort` CLI and parses its `PROGRESS`
  stream, exactly as today. No engine refactor — de-risks the migration. CLI stays the clean programmatic surface.
- **Low system resources.** The same box feeds an LM Studio VL model (4 GB VRAM / 16 GB RAM). Animations
  stay cheap (implicit/CSS-style, no busy loops); Electron-class footprint is a non-goal even though the
  desired *look* is Discord-like.

## Look & motion

- **Discord-like dark aesthetic** — left navigation rail (Run / Tags / Folders / Reports / Stats) + a focused
  main panel. Clean hierarchy, one accent colour.
- **Small, minimal animations** tuned for a calm, positive effect: eased progress fill, per-file rows that
  fade/slide in as they finish, a soft spinner on the active file, quick fades between rail sections, and a
  calm completion summary card. Subtle, never flashy.
- **Safety stays visible** — Stop always present; dry-run/apply, copy, skip-unknown surfaced up front so the
  user trusts the automation.

## Information the run view must surface prominently

Because the user is waiting, the live state must be legible at a glance:

- **Progress** — percent + file *i* of *N*, with an eased bar.
- **Time** — elapsed and estimated remaining (ETA), shown plainly.
- **Throughput** — tok/s.
- **Counters** — done / failed / skipped.
- **Current file + tier indicator** — what's being read now and which tier (text / vision / frontier).
- **Live feed** — recently completed files with their assigned `[STREAM-SUBJECT]` tag.
- **Completion** — a summary card (counts, proposals, low-confidence, failures) that closes the loop.

## Carry-over requirements (must not regress)

The new GUI keeps everything the current one does: folder picker, host + live model picker, run toggles
(copy / misc / vision / apply / skip-unknown), frontier dropdown, Run/Stop, the live progress + stats strip,
live log pane, structured tag editor, Folders (exclude/include) dialog, and the Report viewer. A future
**Taxonomy Generator** dialog ([taxonomy-generator.md](taxonomy-generator.md)) will plug into this Flet shell.

## Open questions (for the planning pass)
- Exact rail sections + whether Stats/Reports merge.
- Accent colour and density.
- Packaging: Flet desktop build vs. the current two PyInstaller exes (ties into the future single-Windows-
  package roadmap item).

## Explicitly out of scope (deferred to roadmap)
- Background processing and a system-tray presence (run minimized / keep working in the tray).
- A single unified Windows package as the release artifact.
- Engine-side debt (e.g. transient single-retry) and the in-process engine boundary.
These are tracked in [`../ROADMAP.md`](../ROADMAP.md), not this version.
