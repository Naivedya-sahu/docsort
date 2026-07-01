# Near-Duplicate Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Plan 4 of v0.13.x (spec §3.5, 3rd Clean-phase layer). Populate path/filename-derived embeddings
for every indexed file, then find near-duplicate clusters via cosine similarity — catches scattered
content-duplicates with no matching structure (the "dupe hell at scale" gap identified from real-data
review). Full-text embeddings (from extracted document content) enrich this later once the classify-tier
integration lands (separate plan, touches `cli.py`'s tier chain) — this plan is scoped to what's testable
standalone: index + embed + dedup, no `cli.py` changes.

**Architecture:** `embed_index()` (in `docsort/index.py`) fills any missing `embedding` column using
`embed.embed_text()` on each file's basename + parent-folder name (available for every file today, no
text-extraction dependency). `dedup.find_near_duplicates()` clusters files whose embeddings exceed a
similarity threshold, using union-find to merge transitively-similar pairs into clusters.

**Tech Stack:** Python stdlib only.

---

### Task 1: `index.embed_index()`

**Files:** Modify `docsort/index.py`, `tests/test_index.py`

- [ ] **Step 1: failing test**

```python
# append to tests/test_index.py
from docsort.index import embed_index

def test_embed_index_fills_missing_embeddings(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "a.txt").write_bytes(b"x")
    (data_root / "b.txt").write_bytes(b"y")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(data_root))

    count = embed_index(conn)
    assert count == 2
    vec = get_embedding(conn, str(data_root / "a.txt"))
    assert vec is not None
    assert len(vec) == 128  # embed.DIMS
    conn.close()

def test_embed_index_skips_already_embedded(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "a.txt").write_bytes(b"x")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(data_root))
    embed_index(conn)

    second_pass_count = embed_index(conn)
    assert second_pass_count == 0
    conn.close()
```

- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_index.py -v` — expect FAIL,
  `ImportError: cannot import name 'embed_index'`

- [ ] **Step 3: implementation**

```python
# add to docsort/index.py
def embed_index(conn):
    """Fill the embedding column for every file that doesn't have one yet.
    Uses filename + parent folder name — available for every file with no
    text-extraction dependency. Returns the number of files newly embedded."""
    from docsort.embed import embed_text
    rows = conn.execute(
        "SELECT path FROM files WHERE embedding IS NULL"
    ).fetchall()
    count = 0
    for (path,) in rows:
        basename = os.path.basename(path)
        parent = os.path.basename(os.path.dirname(path))
        vec = embed_text(f"{parent} {basename}")
        set_embedding(conn, path, vec)
        count += 1
    return count
```

- [ ] **Step 4:** Run tests — expect PASS (12 tests)

- [ ] **Step 5: commit**

```bash
git add docsort/index.py tests/test_index.py
git commit -m "feat(index): add embed_index() to fill path-derived embeddings"
```

---

### Task 2: `dedup.find_near_duplicates()`

**Files:** Modify `docsort/dedup.py`, `tests/test_dedup.py`

- [ ] **Step 1: failing test**

```python
# append to tests/test_dedup.py
from docsort.index import embed_index
from docsort.dedup import find_near_duplicates

def test_find_near_duplicates_clusters_similar_filenames(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "Calculus_Notes.pdf").write_bytes(b"a")
    (root / "Calculus_Notes_v2.pdf").write_bytes(b"b")
    (root / "Fourier_Transform.pdf").write_bytes(b"c")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))
    embed_index(conn)

    clusters = find_near_duplicates(conn, threshold=0.5)
    matched = [c for c in clusters if len(c) >= 2]
    assert len(matched) >= 1
    names = {os.path.basename(p) for p in matched[0]}
    assert "Calculus_Notes.pdf" in names or "Calculus_Notes_v2.pdf" in names
    conn.close()

def test_find_near_duplicates_empty_below_threshold(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "Calculus.pdf").write_bytes(b"a")
    (root / "Fourier.pdf").write_bytes(b"b")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))
    embed_index(conn)

    clusters = find_near_duplicates(conn, threshold=0.999)
    matched = [c for c in clusters if len(c) >= 2]
    assert matched == []
    conn.close()
```

- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_dedup.py -v` — expect FAIL,
  `ImportError: cannot import name 'find_near_duplicates'`

- [ ] **Step 3: implementation**

```python
# add to docsort/dedup.py
def find_near_duplicates(conn, threshold=0.8):
    """Cluster files whose embeddings exceed threshold cosine similarity.
    Review-only signal — highest false-positive risk of the three dedup layers,
    never auto-applied. O(n^2) pairwise; fine at personal-drive scale, revisit
    with an ANN index if this ever needs to run over millions of files."""
    from docsort.embed import cosine_similarity

    rows = conn.execute(
        "SELECT path, embedding FROM files WHERE embedding IS NOT NULL"
    ).fetchall()
    items = [(path, tuple(float(x) for x in emb.split(","))) for path, emb in rows]

    parent = {path: path for path, _ in items}

    def find(p):
        while parent[p] != p:
            parent[p] = parent[parent[p]]
            p = parent[p]
        return p

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            path_a, vec_a = items[i]
            path_b, vec_b = items[j]
            if cosine_similarity(vec_a, vec_b) >= threshold:
                union(path_a, path_b)

    groups = {}
    for path, _ in items:
        root = find(path)
        groups.setdefault(root, []).append(path)
    return [paths for paths in groups.values() if len(paths) >= 2]
```

- [ ] **Step 4:** Run tests — expect PASS

- [ ] **Step 5: commit**

```bash
git add docsort/dedup.py tests/test_dedup.py
git commit -m "feat(dedup): add find_near_duplicates() via union-find over embeddings"
```

---

## Self-review

**Spec coverage:** 3rd Clean-phase layer (near-dup, global, review-only) ✅ Task 2. Embedding population
✅ Task 1. Docstring explicitly notes review-only/false-positive caveat from the spec.

**Placeholder scan:** none.

**Type consistency:** `find_near_duplicates(conn, threshold=0.8)` matches `find_exact_duplicates(conn)` /
`find_duplicate_subtrees(conn)` calling convention (conn-first, returns list-of-groups) established in
Plan 2 — all three Clean-phase detectors are now callable the same way.

**Known limitation, not a gap:** embeddings here are path/filename-derived only (no document text yet) —
correctly scoped per this plan's stated boundary; full-text embeddings arrive with the classify-tier
integration plan and will naturally improve near-dup accuracy without changing this function's signature.
