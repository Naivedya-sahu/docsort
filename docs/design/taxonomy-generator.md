# Design note — Taxonomy Generator (sub-project)

> Status: **designed, deferred to a future version** (after the GUI overhaul / v0.11.0).
> Solves docsort public-release blocker #2 (the taxonomy is personalized).
> This note records the brainstormed design so it's ready to plan when scheduled.

## The problem

docsort's classification is steered by three personalized files:

- `TAGS.md` — the controlled vocabulary (STREAMS / SUBJECTS / TYPES),
- `system_prompt.md` — the model's rules and worked examples,
- the taxonomy choices baked into both.

Today these encode **one user's Electronics-Engineering academic schema**. Anyone else has to hand-edit
them to match their own domain before docsort is useful. That is the main thing blocking a broad release.

## The approach (chosen)

Build a **Taxonomy Generator**: a tool that takes a **folder tree shared by the user** (their existing,
manually-organized archive) and uses an **LLM to generate the two filter files** — `TAGS.md` and
`system_prompt.md` — derived from that tree. Onboarding becomes: *point it at your folder tree → confirm
the proposed taxonomy → docsort runs steered to your domain.*

**Hard constraint:** docsort's whole engine + filename prefix is built on the **two-axis STREAM × SUBJECT**
model (STREAM = "what the file is for", SUBJECT = "topic"). The generator must produce *that* shape with the
`NA` / `99UNS` sentinels preserved — it must not invent arbitrary axis structures.

## Brainstormed design

**Module & surfaces**
- New engine module `docsort/taxonomy.py` (pure-ish, testable, no UI).
- **GUI:** a separate "Generate Taxonomy" dialog (own window), launchable from the main window / first run.
- **CLI:** `docsort --gen-taxonomy PATH`. Both surfaces drive the same engine.

**Pipeline**
1. **Walk** the target tree → collect folder paths + filenames only (no file contents); respect a depth cap
   and the existing exclude list. Build a compact "tree digest" (folders, sample filenames, counts).
2. **First pass:** a small text model reads the digest → proposes draft STREAMS, SUBJECTS, TYPES, and flags a
   small `ambiguous[]` set of folders it couldn't confidently place.
3. **Ambiguous resolution:** re-prompt with the *full* filename list of just those folders (still text-only);
   optionally escalate to a larger text model if one is loaded (mirrors docsort's tier philosophy).
4. **Interactive wizard:** present each block for the user to confirm/edit in order —
   STREAMS → SUBJECTS → TYPES → examples. This edit step is the real quality gate.
5. **Examples:** the model maps a handful of representative files → `STREAM SUBJECT TYPE CONF` lines for
   `system_prompt.md`.
6. **Render + write:** build `TAGS.md` (```tags blocks) and `system_prompt.md` (rules template + injected
   examples), validate via docsort's own tag parser (round-trip safe), back up any existing files as `.bak`,
   write to the per-user data dir.

**Model handling**
- Reuse the LM Studio OpenAI endpoint. New resolver picks the smallest loaded **non-vision, non-embedding**
  chat model (`prefer_vision=False`, exclude `*embed*`). The classifier's GPU-bound VLMs are *not* used here —
  taxonomy parsing is text-only and can run on a small CPU-capable model; LM Studio handles CPU/GPU offload.
  If only a VL model is loaded, fall back to it with a notice. (Embedding models can't generate text, so they
  are explicitly excluded.) Model returns **structured JSON**, not free text → deterministic rendering.

**Error tolerance**
- Generation needn't be perfect. The wizard edit gate plus docsort's downstream rename / `--retag` /
  `~PROPOSE` mechanisms absorb taxonomy drift. TYPES is seeded from current defaults and the model may extend it.

**Testing**
- Hermetic: synthetic tree digest + a mocked model JSON response → assert the rendered `TAGS.md` parses back
  to the expected codes and `system_prompt.md` fills its placeholders. No live LM Studio needed.

## Open questions (for the eventual planning pass)
- Wizard step UI once the GUI framework is decided (this depends on the GUI overhaul outcome).
- How deep to walk very large trees; sampling strategy for filename lists.
- Whether the generator ever ships as a standalone package vs. staying in the docsort repo.
