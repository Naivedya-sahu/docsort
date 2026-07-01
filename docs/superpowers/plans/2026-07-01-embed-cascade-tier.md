# EMBED Cascade Tier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Plan 5 of v0.13.x (spec §3.4). Insert a cheap embedding-based pre-filter before the existing
TEXT tier in `classify()` — resolves the bulk of files with zero LLM calls, only the ambiguous tail falls
through to the existing TEXT→ESCALATE→VISION→FRONTIER chain unchanged.

**Risk note:** `classify()` in `docsort/cli.py` is live production code with no existing unit-test
coverage of its tier branching (tests mock `classify()` entirely — see `tests/test_core.py:55`). This
plan is deliberately **opt-in / default-off**: the new `--embed-threshold` flag defaults to `None`
(disabled), so behavior is byte-for-byte unchanged for every existing user/test until someone explicitly
sets a threshold. The centroid math itself (Task 1) is fully unit-tested in isolation with zero model
dependency.

**Architecture:** New `docsort/cascade.py` builds per-label centroids from the STREAM/SUBJECT
*descriptions* already in `TAGS.md` (zero-shot — no example files needed, `load_tags()` already parses
these) and classifies new text against them via `embed.cosine_similarity`. `classify()` calls it once,
before the TEXT-tier branch, only when enabled.

**Tech Stack:** Python stdlib + `docsort/embed.py` (Plan 3). No new dependency.

---

### Task 1: `docsort/cascade.py` — `build_centroids()` + `classify_by_embed()`

**Files:** Create `docsort/cascade.py`, Create `tests/test_cascade.py`

- [ ] **Step 1: failing test**

```python
# tests/test_cascade.py
from docsort.cascade import build_centroids, classify_by_embed

STREAM_DESC = {
    "CW": "CW coursework / college degree material (BTech notes, assignments, lab)",
    "REC": "REC records / admin marksheet admit card certificate ID exam form fee receipt",
}
SUBJECT_DESC = {
    "04BJT": "04BJT BJT bipolar biasing CE CB CC h-params",
    "09SNS": "09SNS Signals Systems DSP fourier laplace z-transform convolution sampling",
}


def test_build_centroids_returns_one_vector_per_label():
    centroids = build_centroids(STREAM_DESC)
    assert set(centroids.keys()) == {"CW", "REC"}


def test_classify_by_embed_returns_none_below_threshold():
    stream_c = build_centroids(STREAM_DESC)
    subject_c = build_centroids(SUBJECT_DESC)
    result = classify_by_embed("completely unrelated gibberish zzq xkcd", stream_c, subject_c, threshold=0.9)
    assert result is None


def test_classify_by_embed_matches_confident_text():
    stream_c = build_centroids(STREAM_DESC)
    subject_c = build_centroids(SUBJECT_DESC)
    result = classify_by_embed(
        "BJT transistor CE biasing lab assignment coursework notes",
        stream_c, subject_c, threshold=0.05,
    )
    assert result is not None
    stream, subject, stream_score, subject_score = result
    assert stream == "CW"
    assert subject == "04BJT"
    assert 0.0 <= stream_score <= 1.0
    assert 0.0 <= subject_score <= 1.0
```

- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_cascade.py -v` — expect FAIL,
  `ModuleNotFoundError: No module named 'docsort.cascade'`

- [ ] **Step 3: implementation**

```python
# docsort/cascade.py
from docsort.embed import embed_text, classify_by_centroid


def build_centroids(label_descriptions):
    """label_descriptions: {code: description_text} (e.g. from TAGS.md via load_tags()).
    Zero-shot — one description per label is the centroid seed, no example files needed."""
    return {code: embed_text(desc) for code, desc in label_descriptions.items()}


def classify_by_embed(text, stream_centroids, subject_centroids, threshold):
    """Returns (stream, subject, stream_score, subject_score) if BOTH axes clear threshold,
    else None (caller falls through to the existing TEXT tier)."""
    vec = embed_text(text)
    stream, stream_score = classify_by_centroid(vec, stream_centroids)
    subject, subject_score = classify_by_centroid(vec, subject_centroids)
    if stream_score < threshold or subject_score < threshold:
        return None
    return stream, subject, stream_score, subject_score
```

- [ ] **Step 4:** Run tests — expect PASS (3 tests)

- [ ] **Step 5: commit**

```bash
git add docsort/cascade.py tests/test_cascade.py
git commit -m "feat(cascade): add build_centroids() + classify_by_embed()"
```

---

### Task 2: wire `--embed-threshold` into `classify()` (opt-in, default off)

**Files:** Modify `docsort/config.py`, `docsort/cli.py`

- [ ] **Step 1:** In `docsort/config.py`, add the config default. In the `DEFAULTS["options"]` dict
  (currently `{"vision": True, "apply": False, "min_text": 80, ...}`), add:

```python
        "embed_threshold": None,   # None = disabled; set 0.0-1.0 to enable the EMBED cascade tier
```

  And in `arg_defaults()`, add to the `args` dict (alongside `"frontier": m["frontier"]`):

```python
        "embed_threshold": o.get("embed_threshold"),
```

- [ ] **Step 2:** In `docsort/cli.py`, add the CLI flag near `--frontier` in `add_args()`:

```python
    ap.add_argument("--embed-threshold",dest="embed_threshold",type=float,default=None,
                    help="enable the EMBED cascade tier at this cosine-similarity threshold (0.0-1.0); unset = disabled")
```

- [ ] **Step 3:** In `docsort/cli.py`, modify `setup()` to also build centroids when enabled:

```python
def setup(a):
    global STREAMS,SUBJECTS,TYPES,STREAM_CENTROIDS,SUBJECT_CENTROIDS
    s,su,ty=load_tags(a.tags); STREAMS=set(s); SUBJECTS=set(su); TYPES=set(ty)
    STREAM_CENTROIDS,SUBJECT_CENTROIDS={},{}
    if getattr(a,"embed_threshold",None) is not None:
        from docsort.cascade import build_centroids
        STREAM_CENTROIDS=build_centroids(s); SUBJECT_CENTROIDS=build_centroids(su)
    return build_system(a.prompt,s,su,ty)
```

  Add the two new globals near the existing `STREAMS=set(); SUBJECTS=set(); TYPES=set()` line:

```python
STREAMS=set(); SUBJECTS=set(); TYPES=set()   # filled from TAGS.md
STREAM_CENTROIDS={}; SUBJECT_CENTROIDS={}    # filled from TAGS.md when --embed-threshold is set
```

- [ ] **Step 4:** In `docsort/cli.py`'s `classify()`, insert the EMBED check as the very first branch,
  before the existing `if len(snip.strip())>=MIN_TEXT:` line:

```python
def classify(a,sysp,full,fn,rel):
    ispdf=full.lower().endswith(".pdf")
    snip=doc_text(full)
    if a.embed_threshold is not None and STREAM_CENTROIDS and SUBJECT_CENTROIDS:
        from docsort.cascade import classify_by_embed
        r=classify_by_embed(f"{fn} {rel} {snip}",STREAM_CENTROIDS,SUBJECT_CENTROIDS,a.embed_threshold)
        if r is not None:
            st,su,_,_=r
            return st,su,"misc","high","embed"
    u=lambda txt:f"Filename: {fn}\nFolder: {rel}\nText:\n{txt[:DEEP_CAP]}\n\nAnswer (STREAM SUBJECT TYPE CONF):"
    if len(snip.strip())>=MIN_TEXT:
```

  (the rest of `classify()` — the TEXT/VISION/FILENAME branches — is unchanged; this only adds the new
  branch above the existing first `if`.)

- [ ] **Step 5:** Verify nothing broke — run the full existing suite:

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: all existing tests still PASS (this change is additive-only and gated by a default-`None` flag
that no existing test sets, so no existing behavior path is touched).

- [ ] **Step 6: commit**

```bash
git add docsort/config.py docsort/cli.py
git commit -m "feat(cli): wire opt-in --embed-threshold cascade tier into classify()"
```

---

## Self-review

**Spec coverage (§3.4):** EMBED tier inserted before TEXT, zero-shot centroids, falls through to existing
chain unchanged when not confident ✅ Tasks 1–2. "Same call, richer schema" hybrid multi-tag output for
VISION/FRONTIER tiers is a **separate follow-up plan** (touches the VISION/FRONTIER prompt+parser, a
different piece of `classify()` than this plan touches) — not included here to keep this plan's blast
radius to the EMBED insertion only.

**Placeholder scan:** none — all code real, all file:line locations exact (verified via Grep/Read against
the actual file before writing this plan, not assumed).

**Type consistency:** `classify_by_embed()` returns the same 4-tuple shape
`(stream, subject, stream_score, subject_score)` used consistently in both the cascade.py tests and the
`classify()` call site.

**Safety:** default-off via `None` sentinel is load-bearing — do not change the default in this plan.
