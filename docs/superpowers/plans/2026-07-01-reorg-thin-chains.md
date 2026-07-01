# Reorg-Suggester: Thin-Chain Flattening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Plan 7 of v0.13.x (spec §3.6). `docsort/cli.py` already has `move_by_prefix()`, which flattens
*already-tagged* files (`[STREAM-SUBJECT] name`) into a `STREAM/SUBJECT/` tree via `--move` — that already
covers "propose a flatter structure" for tagged content. The remaining gap, found directly in the real
`Drive_D.txt` review, is **thin single-child folder chains** (e.g. `.../INCAM 2024 Backups/INCAM 2024/`,
`.../New folder/ULTIBOARD/ULTIBOARD/`) — folders nested purely because each level has exactly one child,
adding depth with zero organizational value. This plan detects those chains and proposes collapsing them,
independent of whether files are tagged yet.

**Architecture:** New `docsort/reorg.py`: `find_thin_chains()` walks `index.list_directories()` looking
for directories with exactly one child, chains them via the same single-child-child-count logic used in
the original `Drive_D.txt` analysis; `propose_flatten()` turns each chain into a dry-run move list (move
the chain's terminal folder's contents up to the chain's start, collapsing the empty wrappers in between).

**Tech Stack:** Python stdlib only, reuses `docsort/index.py`.

---

### Task 1: `reorg.find_thin_chains()`

**Files:** Create `docsort/reorg.py`, Create `tests/test_reorg.py`

- [ ] **Step 1: failing test**

```python
# tests/test_reorg.py
from docsort.index import open_index, scan_directory
from docsort.reorg import find_thin_chains

def test_find_thin_chains_detects_single_child_nesting(tmp_path):
    root = tmp_path / "data"
    # thin chain: A -> B -> C, each with exactly one child, C has the real content
    (root / "A" / "B" / "C").mkdir(parents=True)
    (root / "A" / "B" / "C" / "file.txt").write_bytes(b"content")
    # a normal, non-thin folder (2 children) should NOT be flagged
    (root / "Normal").mkdir(parents=True)
    (root / "Normal" / "x.txt").write_bytes(b"x")
    (root / "Normal" / "y.txt").write_bytes(b"y")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))

    chains = find_thin_chains(conn, min_length=2)
    assert len(chains) == 1
    chain = chains[0]
    assert chain["start"] == str(root / "A")
    assert chain["end"] == str(root / "A" / "B" / "C")
    assert chain["length"] == 3
    conn.close()

def test_find_thin_chains_respects_min_length(tmp_path):
    root = tmp_path / "data"
    (root / "A" / "B").mkdir(parents=True)  # only 2 deep, below min_length=3
    (root / "A" / "B" / "file.txt").write_bytes(b"content")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))

    chains = find_thin_chains(conn, min_length=3)
    assert chains == []
    conn.close()
```

- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_reorg.py -v` — expect FAIL,
  `ModuleNotFoundError: No module named 'docsort.reorg'`

- [ ] **Step 3: implementation**

```python
# docsort/reorg.py
import os

from docsort.index import list_directories


def _children_of(all_dirs, d):
    return [x for x in all_dirs if os.path.dirname(x) == d]


def find_thin_chains(conn, root, min_length=3):
    """Detect runs of directories where each has exactly one subdirectory child.
    Scoped to `root` — list_directories() also returns filesystem ancestors above the
    scanned root, which must not be treated as reorg candidates.
    Returns [{"start": path, "end": path, "length": N}, ...] for chains >= min_length."""
    root_prefix = root + os.sep
    all_dirs = {d for d in list_directories(conn) if d == root or d.startswith(root_prefix)}
    child_count = {d: len(_children_of(all_dirs, d)) for d in all_dirs}

    thin = {d for d in all_dirs if child_count[d] == 1}
    chain_starts = [d for d in thin if os.path.dirname(d) not in thin]

    chains = []
    for start in chain_starts:
        length = 1
        cur = start
        while True:
            kids = _children_of(all_dirs, cur)
            if len(kids) != 1:
                break
            nxt = kids[0]
            if nxt in thin:
                length += 1
                cur = nxt
            else:
                # the single child is the terminal folder (not itself thin, e.g. it has files+no subdirs)
                cur = nxt
                length += 1
                break
        if length >= min_length:
            chains.append({"start": start, "end": cur, "length": length})
    return chains
```

- [ ] **Step 4:** Run tests — expect PASS

- [ ] **Step 5: commit**

```bash
git add docsort/reorg.py tests/test_reorg.py
git commit -m "feat(reorg): add find_thin_chains() single-child folder detection"
```

---

### Task 2: `reorg.propose_flatten()`

**Files:** Modify `docsort/reorg.py`, `tests/test_reorg.py`

- [ ] **Step 1: failing test**

```python
# append to tests/test_reorg.py
from docsort.reorg import propose_flatten

def test_propose_flatten_moves_end_contents_to_start(tmp_path):
    root = tmp_path / "data"
    (root / "A" / "B" / "C").mkdir(parents=True)
    (root / "A" / "B" / "C" / "file.txt").write_bytes(b"content")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))

    chains = find_thin_chains(conn, min_length=2)
    moves = propose_flatten(conn, chains)

    assert len(moves) == 1
    src, dst = moves[0]
    assert src == str(root / "A" / "B" / "C" / "file.txt")
    assert dst == str(root / "A" / "file.txt")
    conn.close()
```

- [ ] **Step 2:** Run tests — expect FAIL, `ImportError: cannot import name 'propose_flatten'`

- [ ] **Step 3: implementation**

```python
# add to docsort/reorg.py
def propose_flatten(conn, chains):
    """Dry-run move list: for each chain, move the terminal folder's direct files up to
    the chain's start folder, collapsing the thin wrappers in between. Caller applies via
    the existing shutil.move + journal pattern — this function only proposes."""
    moves = []
    rows = conn.execute("SELECT path FROM files").fetchall()
    all_files = [p for (p,) in rows]
    for chain in chains:
        end = chain["end"]
        start = chain["start"]
        prefix = end + os.sep
        for f in all_files:
            if f.startswith(prefix):
                rel = f[len(prefix):]
                dst = os.path.join(start, rel)
                moves.append((f, dst))
    return moves
```

- [ ] **Step 4:** Run tests — expect PASS

- [ ] **Step 5: commit**

```bash
git add docsort/reorg.py tests/test_reorg.py
git commit -m "feat(reorg): add propose_flatten() dry-run move list"
```

---

## Self-review

**Spec coverage:** thin-chain detection (the 3 real chains found in `Drive_D.txt` review) ✅ Task 1.
Dry-run move-list proposal, same pattern as every other mutating feature in this codebase ✅ Task 2.
Embedding-based clustering for *untagged* content beyond simple thin-chains, and the CLI/apply wiring, are
follow-ups — this plan covers the specific gap identified from real data, not a full reorg engine
rewrite (`move_by_prefix` already handles the tagged-content case).

**Placeholder scan:** none.

**Type consistency:** `find_thin_chains()` returns `[{"start","end","length"}, ...]`;
`propose_flatten(conn, chains)` consumes that exact shape.
