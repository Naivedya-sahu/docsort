# Design note — the LLM Council (separate project)

> Status: **separate project, in development.** Not implemented inside docsort.
> Integration surface will be defined once the council project is complete.
> This note records the intent and the design conclusions reached so far, so docsort
> can slot it in cleanly later.

## What it is

The **LLM Council** is its own project — not a docsort feature. In a nutshell it aims to expose
**universal API endpoints** that can be tied to *any* kind of system, and let a **central controller
model manage other models** to produce an adequate combined output.

Think of it as a **"poor man's Mixture-of-Experts"** — but potentially *more accurate* than a
single MoE if you accept the trade-off of **no hard limit on the number of models or the time spent**.
Diversity of independently-trained models, judged and reconciled by a controller, is the source of the
accuracy gain.

## Design conclusions reached so far

These were worked out while discussing docsort's `99UNS` escalation, and carry over to the council
project as a standalone system:

- **Code schedules, a model judges.** Don't make a model orchestrate other models. A deterministic
  loop dispatches work; one model acts as the **judge** that scores candidate answers and either
  approves one or mints a new option.
- **Serial council is nearly free with JIT model loading.** LM Studio's just-in-time model loading
  means each request can name a different `model` id and the server swaps it in — no custom
  orchestrator, no requirement to hold multiple models in VRAM at once. On constrained hardware
  (e.g. 4 GB) this makes a serial ensemble feasible; on more VRAM, keep the judge + one worker
  resident to cut swap overhead.
- **Diversity must be real.** The accuracy benefit only appears if members are genuinely different
  models (different training), not multiple quantizations of one model.
- **Universal endpoints = the integration contract.** The council should present a stable endpoint that
  any consumer (docsort being one) can call without knowing the internal model roster.

## How docsort will consume it (future)

When the council project exposes its endpoint, docsort plans to wire it in as a **new escalation tier
after VISION**, gated strictly to:

- `99UNS` (unknown) files only,
- **opt-in** (a `--council` flag),
- **overnight / accuracy-over-speed** runs (it is minutes per file).

Council-minted tags reuse docsort's existing **`~LABEL` proposal mechanism** (pending sub-tag under
unknown), tallied by `--report` and promotable via the tag editor + `--retag`. No new tag system needed.
The run journal would record `source=council`.

## Open until the council project lands

- The exact endpoint shape / request + response contract (defined by the council project).
- Whether docsort calls it directly or through an adapter.
- Member roster and the judge model choice (council-side concern).
