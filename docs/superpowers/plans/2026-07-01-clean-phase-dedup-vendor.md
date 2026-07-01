# Clean-Phase Dedup + Vendor-Dump Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Plan 2 of v0.13.x (spec §3.5). Build the two non-ML Clean-phase dedup layers (exact-hash, subtree-signature) plus the vendor-dump detector, all as pure query functions over the `docsort/index.py` table built in Plan 1. The third dedup layer (near-duplicate embedding) needs the embedding infra and is its own later plan.

**Architecture:** Two new modules, `docsort/dedup.py` and `docsort/vendor.py`, both read-only queries over the existing SQLite index — no schema change, no new dependency. A shared `list_directories()` helper lives in `index.py` since it derives directly from indexed paths.

**Tech Stack:** Python stdlib only.

---

### Task 1: `index.list_directories()`

**Files:** Modify `docsort/index.py`, Test `tests/test_index.py`

- [ ] **Step 1: failing test**

```python
# append to tests/test_index.py
from docsort.index import list_directories

def test_list_directories_derives_from_file_paths(tmp_path):
    data_root = tmp_path / "data"
    (data_root / "sub").mkdir(parents=True)
    (data_root / "a.txt").write_bytes(b"1")
    (data_root / "sub" / "b.txt").write_bytes(b"2")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(data_root))

    dirs = list_directories(conn)
    assert str(data_root) in dirs
    assert str(data_root / "sub") in dirs
    conn.close()
```

- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_index.py -v` — expect FAIL, `ImportError: cannot import name 'list_directories'`

- [ ] **Step 3: implementation**

```python
# add to docsort/index.py
def list_directories(conn):
    dirs = set()
    for (path,) in conn.execute("SELECT path FROM files"):
        d = os.path.dirname(path)
        while d and d not in dirs:
            dirs.add(d)
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    return dirs
```

- [ ] **Step 4:** Run tests — expect PASS (9 tests)

- [ ] **Step 5: commit**

```bash
git add docsort/index.py tests/test_index.py
git commit -m "feat(index): add list_directories()"
```

---

### Task 2: `dedup.find_exact_duplicates()`

**Files:** Create `docsort/dedup.py`, Create `tests/test_dedup.py`

- [ ] **Step 1: failing test**

```python
# tests/test_dedup.py
from docsort.index import open_index, scan_directory
from docsort.dedup import find_exact_duplicates

def test_find_exact_duplicates_groups_identical_content(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "a.txt").write_bytes(b"same content")
    (data_root / "b.txt").write_bytes(b"same content")
    (data_root / "c.txt").write_bytes(b"different")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(data_root))

    groups = find_exact_duplicates(conn)
    assert len(groups) == 1
    group = list(groups.values())[0]
    assert len(group) == 2
    assert all(p.endswith(("a.txt", "b.txt")) for p in group)
    conn.close()
```

- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_dedup.py -v` — expect FAIL, `ModuleNotFoundError: No module named 'docsort.dedup'`

- [ ] **Step 3: implementation**

```python
# docsort/dedup.py

def find_exact_duplicates(conn):
    """Group indexed files by content hash; return {hash: [paths]} for hashes with 2+ files."""
    rows = conn.execute(
        "SELECT hash, path FROM files WHERE hash IS NOT NULL"
    ).fetchall()
    by_hash = {}
    for filehash, path in rows:
        by_hash.setdefault(filehash, []).append(path)
    return {h: paths for h, paths in by_hash.items() if len(paths) >= 2}
```

- [ ] **Step 4:** Run tests — expect PASS

- [ ] **Step 5: commit**

```bash
git add docsort/dedup.py tests/test_dedup.py
git commit -m "feat(dedup): add find_exact_duplicates()"
```

---

### Task 3: `dedup.subtree_signature()` + `find_duplicate_subtrees()`

**Files:** Modify `docsort/dedup.py`, `tests/test_dedup.py`

- [ ] **Step 1: failing test**

```python
# append to tests/test_dedup.py
from docsort.index import list_directories
from docsort.dedup import subtree_signature, find_duplicate_subtrees

def test_subtree_signature_matches_for_identical_trees(tmp_path):
    root = tmp_path / "data"
    (root / "TreeA").mkdir(parents=True)
    (root / "TreeA" / "x.txt").write_bytes(b"content-x")
    (root / "TreeA" / "y.txt").write_bytes(b"content-y")
    (root / "TreeB").mkdir(parents=True)
    (root / "TreeB" / "x.txt").write_bytes(b"content-x")
    (root / "TreeB" / "y.txt").write_bytes(b"content-y")
    (root / "TreeC").mkdir(parents=True)
    (root / "TreeC" / "z.txt").write_bytes(b"unrelated")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))

    sig_a = subtree_signature(conn, str(root / "TreeA"))
    sig_b = subtree_signature(conn, str(root / "TreeB"))
    sig_c = subtree_signature(conn, str(root / "TreeC"))
    assert sig_a == sig_b
    assert sig_a != sig_c
    conn.close()

def test_find_duplicate_subtrees_groups_identical_dirs(tmp_path):
    root = tmp_path / "data"
    (root / "TreeA").mkdir(parents=True)
    (root / "TreeA" / "x.txt").write_bytes(b"content-x")
    (root / "TreeB").mkdir(parents=True)
    (root / "TreeB" / "x.txt").write_bytes(b"content-x")
    (root / "TreeC").mkdir(parents=True)
    (root / "TreeC" / "z.txt").write_bytes(b"unrelated")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))

    groups = find_duplicate_subtrees(conn)
    matched = [g for g in groups if len(g) >= 2]
    assert len(matched) == 1
    assert {os.path.basename(p) for p in matched[0]} == {"TreeA", "TreeB"}
    conn.close()
```

- [ ] **Step 2:** Run tests — expect FAIL, `ImportError: cannot import name 'subtree_signature'`

- [ ] **Step 3: implementation**

```python
# add to docsort/dedup.py
import os

def subtree_signature(conn, dirpath):
    """Frozenset of (relative_path, hash) for every file under dirpath (recursive)."""
    prefix = dirpath + os.sep
    rows = conn.execute(
        "SELECT path, hash FROM files WHERE path LIKE ? AND hash IS NOT NULL",
        (prefix + "%",),
    ).fetchall()
    return frozenset((path[len(prefix):], filehash) for path, filehash in rows)


def find_duplicate_subtrees(conn):
    """Group directories sharing an identical (non-empty) subtree signature."""
    from docsort.index import list_directories
    by_signature = {}
    for d in list_directories(conn):
        sig = subtree_signature(conn, d)
        if not sig:
            continue
        by_signature.setdefault(sig, []).append(d)
    return [dirs for dirs in by_signature.values() if len(dirs) >= 2]
```

- [ ] **Step 4:** Run tests — expect PASS

- [ ] **Step 5: commit**

```bash
git add docsort/dedup.py tests/test_dedup.py
git commit -m "feat(dedup): add subtree_signature() and find_duplicate_subtrees()"
```

---

### Task 4: `vendor.find_vendor_dumps()`

**Files:** Create `docsort/vendor.py`, Create `tests/test_vendor.py`

- [ ] **Step 1: failing test**

```python
# tests/test_vendor.py
from docsort.index import open_index, scan_directory
from docsort.vendor import find_vendor_dumps

def test_find_vendor_dumps_matches_master_main_suffix(tmp_path):
    root = tmp_path / "data"
    (root / "eagle_libraries-master").mkdir(parents=True)
    (root / "eagle_libraries-master" / "ac_dc.lbr").write_bytes(b"lib")
    (root / "my-project-main").mkdir(parents=True)
    (root / "my-project-main" / "readme.md").write_bytes(b"readme")
    (root / "MyNotes").mkdir(parents=True)
    (root / "MyNotes" / "notes.txt").write_bytes(b"notes")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))

    flagged = find_vendor_dumps(conn)
    names = {os.path.basename(p) for p in flagged}
    assert names == {"eagle_libraries-master", "my-project-main"}
    conn.close()
```

- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_vendor.py -v` — expect FAIL, `ModuleNotFoundError: No module named 'docsort.vendor'`

- [ ] **Step 3: implementation**

```python
# docsort/vendor.py
import os
import re

from docsort.index import list_directories

_VENDOR_SUFFIX = re.compile(r"-(master|main)$", re.IGNORECASE)


def is_vendor_dump_dir(dirname):
    """Heuristic: GitHub zip-download naming convention (repo-master / repo-main)."""
    return bool(_VENDOR_SUFFIX.search(os.path.basename(dirname.rstrip(os.sep))))


def find_vendor_dumps(conn):
    return [d for d in list_directories(conn) if is_vendor_dump_dir(d)]
```

- [ ] **Step 4:** Run tests — expect PASS

- [ ] **Step 5: commit**

```bash
git add docsort/vendor.py tests/test_vendor.py
git commit -m "feat(vendor): add find_vendor_dumps() heuristic detector"
```

---

## Self-review

**Spec coverage (§3.5):** exact-hash grouping ✅ Task 2, subtree-signature grouping (the Remarkable-2
case) ✅ Task 3, vendor-dump detector ✅ Task 4. Near-dup embedding layer explicitly deferred to the
embedding-infra plan — not a gap, a stated dependency ordering choice.

**Placeholder scan:** none — all code real and runnable.

**Type consistency:** `find_exact_duplicates`, `subtree_signature`, `find_duplicate_subtrees`,
`find_vendor_dumps` signatures consistent across tasks; `list_directories` from Plan 1's `index.py`
reused unchanged.

Note: this plan only builds detection (read-only queries). The `--apply-clean` quarantine-move CLI wiring
is a follow-up task once this + the near-dup layer both exist, so the Reports-tab review can show all
three categories together (per spec §3.9) rather than shipping the button ahead of full detection.
