# Embedding Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Plan 3 of v0.13.x. Build the shared embedding primitive (`docsort/embed.py`) that both the EMBED
classify tier (Plan 5) and the near-dup dedup layer (Plan 4) will consume, plus the index-schema storage
for computed vectors.

**Architecture decision (deviation from spec wording):** spec §3.4 suggested "a static embedding model"
as an example. Implementing instead as a pure-stdlib **feature-hashing bag-of-words vectorizer**
(the "hashing trick") — deterministic, zero new dependency, no model download/load step. This is the
same requirement (cheap, fast, CPU-only, no LLM call) satisfied without adding a torch/sentence-transformers
dependency, which would conflict with docsort's existing low-VRAM/low-resource design constraint.
Swappable later behind the same `embed_text()` signature if a real model is ever wanted.

**Tech Stack:** Python stdlib only (`hashlib`, `re`, `math`).

---

### Task 1: `embed_text()` + `cosine_similarity()`

**Files:** Create `docsort/embed.py`, Create `tests/test_embed.py`

- [ ] **Step 1: failing test**

```python
# tests/test_embed.py
from docsort.embed import embed_text, cosine_similarity

def test_embed_text_is_deterministic():
    v1 = embed_text("Calculus notes linear algebra")
    v2 = embed_text("Calculus notes linear algebra")
    assert v1 == v2

def test_embed_text_similar_text_scores_higher_than_unrelated():
    a = embed_text("BJT bipolar transistor biasing CE CB CC")
    b = embed_text("BJT transistor bias CE amplifier")
    c = embed_text("Fourier transform laplace signals systems")
    assert cosine_similarity(a, b) > cosine_similarity(a, c)

def test_cosine_similarity_identical_vectors_is_one():
    v = embed_text("same text same text")
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-9
```

- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_embed.py -v` — expect FAIL,
  `ModuleNotFoundError: No module named 'docsort.embed'`

- [ ] **Step 3: implementation**

```python
# docsort/embed.py
import hashlib
import math
import re

DIMS = 128
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _bucket(token):
    return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % DIMS


def embed_text(text):
    """Deterministic fixed-size vector via the hashing trick (stdlib-only bag-of-words)."""
    vec = [0.0] * DIMS
    for token in _TOKEN_RE.findall(text.lower()):
        vec[_bucket(token)] += 1.0
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return tuple(vec)


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
```

- [ ] **Step 4:** Run tests — expect PASS (3 tests)

- [ ] **Step 5: commit**

```bash
git add docsort/embed.py tests/test_embed.py
git commit -m "feat(embed): add stdlib hashing-trick embed_text() + cosine_similarity()"
```

---

### Task 2: `centroid()` + `classify_by_centroid()`

**Files:** Modify `docsort/embed.py`, `tests/test_embed.py`

- [ ] **Step 1: failing test**

```python
# append to tests/test_embed.py
from docsort.embed import centroid, classify_by_centroid

def test_centroid_averages_vectors():
    a = embed_text("bjt transistor")
    b = embed_text("bjt bias")
    c = centroid([a, b])
    assert len(c) == len(a)
    # centroid should be closer to both inputs than an unrelated vector is
    unrelated = embed_text("fourier laplace signals")
    assert cosine_similarity(c, a) > cosine_similarity(unrelated, a)

def test_classify_by_centroid_picks_nearest_label():
    centroids = {
        "04BJT": centroid([embed_text("bjt transistor biasing ce cb cc")]),
        "09SNS": centroid([embed_text("fourier laplace transform signals systems")]),
    }
    label, score = classify_by_centroid(embed_text("bjt bias amplifier ce"), centroids)
    assert label == "04BJT"
    assert 0.0 <= score <= 1.0
```

- [ ] **Step 2:** Run tests — expect FAIL, `ImportError: cannot import name 'centroid'`

- [ ] **Step 3: implementation**

```python
# add to docsort/embed.py
def centroid(vectors):
    if not vectors:
        return tuple([0.0] * DIMS)
    n = len(vectors)
    dims = len(vectors[0])
    return tuple(sum(v[i] for v in vectors) / n for i in range(dims))


def classify_by_centroid(vector, centroids):
    """Return (best_label, best_score) — nearest centroid by cosine similarity."""
    best_label, best_score = None, -1.0
    for label, c in centroids.items():
        score = cosine_similarity(vector, c)
        if score > best_score:
            best_label, best_score = label, score
    return best_label, best_score
```

- [ ] **Step 4:** Run tests — expect PASS (5 tests)

- [ ] **Step 5: commit**

```bash
git add docsort/embed.py tests/test_embed.py
git commit -m "feat(embed): add centroid() and classify_by_centroid()"
```

---

### Task 3: index-schema embedding storage

**Files:** Modify `docsort/index.py`, `tests/test_index.py`

- [ ] **Step 1: failing test**

```python
# append to tests/test_index.py
from docsort.index import set_embedding, get_embedding

def test_set_and_get_embedding_roundtrip(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "a.txt").write_bytes(b"content")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(data_root))

    path = str(data_root / "a.txt")
    vec = (0.1, 0.2, 0.3)
    set_embedding(conn, path, vec)
    result = get_embedding(conn, path)
    assert result == vec
    conn.close()
```

- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_index.py -v` — expect FAIL,
  `ImportError: cannot import name 'set_embedding'` (schema also lacks the column yet)

- [ ] **Step 3: implementation**

```python
# in docsort/index.py, update SCHEMA to add the column:
SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    size INTEGER,
    hash TEXT,
    mtime REAL,
    archive_depth INTEGER DEFAULT 0,
    source_archive TEXT,
    embedding TEXT
);
"""

# add functions:
def set_embedding(conn, path, vector):
    conn.execute(
        "UPDATE files SET embedding=? WHERE path=?",
        (",".join(str(x) for x in vector), path),
    )
    conn.commit()


def get_embedding(conn, path):
    row = conn.execute("SELECT embedding FROM files WHERE path=?", (path,)).fetchone()
    if row is None or row[0] is None:
        return None
    return tuple(float(x) for x in row[0].split(","))
```

Also update `test_open_index_creates_files_table`'s expected column set (Task 1 of Plan 1) to include
`"embedding"`:

```python
    assert cols == {
        "path", "size", "hash", "mtime", "archive_depth", "source_archive", "embedding"
    }
```

- [ ] **Step 4:** Run full `tests/test_index.py` — expect PASS (all tests, including the updated column-set
  assertion)

- [ ] **Step 5: commit**

```bash
git add docsort/index.py tests/test_index.py
git commit -m "feat(index): add embedding column + set_embedding()/get_embedding()"
```

---

## Self-review

**Spec coverage:** EMBED-tier vector primitive + centroid classification ✅ Tasks 1–2. Storage for reuse
across classify/dedup (§3.4/§3.5's "reuses EMBED-tier vectors") ✅ Task 3. Actual wiring into `classify()`
tier chain and into `dedup.py`'s near-dup layer are separate follow-up plans (integration, not primitive-
building) — consistent with keeping each plan independently testable.

**Placeholder scan:** none.

**Type consistency:** `embed_text` returns a `tuple[float,...]` throughout; `centroid`/`cosine_similarity`/
`classify_by_centroid`/`set_embedding`/`get_embedding` all consume/produce that same shape.
