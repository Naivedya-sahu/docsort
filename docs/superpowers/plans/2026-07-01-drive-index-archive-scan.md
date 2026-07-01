# Drive Index + Archive-Aware Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the ground-truth SQLite index (`docsort/index.py`) that scans a root folder — including recursing into zip archives, nested zips included — and records path/size/hash/mtime/archive-depth for every file found. This is Plan 1 of the v0.13.x design (`docs/superpowers/specs/2026-07-01-v0.13-drive-organizer-design.md`, §3.1–3.2); dedup, classify-tier, and reorg plans build on top of this index and follow as separate plans.

**Architecture:** A single new module, `docsort/index.py`, owns a SQLite schema and two scan entry points: a plain directory walker and a zip-aware walker that treats archive-internal files as virtual index rows (`archive.zip::inner/path`). Nesting is bounded by a depth cap and a per-archive extraction-size budget, both of which surface as visible rows rather than silent truncation. No existing file is modified except `docsort/cli.py` for one new `--scan` flag.

**Tech Stack:** Python stdlib only — `sqlite3`, `hashlib`, `zipfile`, `os`. No new dependencies.

---

### Task 1: Index schema + open_index()

**Files:**
- Create: `docsort/index.py`
- Test: `tests/test_index.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_index.py
import sqlite3
from docsort.index import open_index, SCHEMA

def test_open_index_creates_files_table(tmp_path):
    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files'")
    assert cur.fetchone() is not None
    cols = {row[1] for row in conn.execute("PRAGMA table_info(files)")}
    assert cols == {
        "path", "size", "hash", "mtime", "archive_depth", "source_archive"
    }
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_index.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'docsort.index'`

- [ ] **Step 3: Write minimal implementation**

```python
# docsort/index.py
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    size INTEGER,
    hash TEXT,
    mtime REAL,
    archive_depth INTEGER DEFAULT 0,
    source_archive TEXT
);
"""

def open_index(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_index.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docsort/index.py tests/test_index.py
git commit -m "feat(index): add SQLite schema + open_index()"
```

---

### Task 2: hash_file() + plain directory scan

**Files:**
- Modify: `docsort/index.py`
- Test: `tests/test_index.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_index.py
from docsort.index import hash_file, scan_directory

def test_hash_file_is_stable(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello world")
    h1 = hash_file(str(f))
    h2 = hash_file(str(f))
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest

def test_scan_directory_indexes_all_files(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.txt").write_bytes(b"one")
    (tmp_path / "sub" / "b.txt").write_bytes(b"two")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(tmp_path))

    rows = conn.execute("SELECT path, size, archive_depth FROM files ORDER BY path").fetchall()
    assert len(rows) == 2
    assert all(r[2] == 0 for r in rows)  # archive_depth 0 for plain files
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_index.py -v`
Expected: FAIL with `ImportError: cannot import name 'hash_file'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to docsort/index.py
import hashlib
import os
import time

def hash_file(path, chunk_size=65536):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def _upsert(conn, path, size, filehash, mtime, archive_depth=0, source_archive=None):
    conn.execute(
        "INSERT OR REPLACE INTO files(path,size,hash,mtime,archive_depth,source_archive) "
        "VALUES (?,?,?,?,?,?)",
        (path, size, filehash, mtime, archive_depth, source_archive),
    )

def scan_directory(conn, root):
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(full)
                mtime = os.path.getmtime(full)
                filehash = hash_file(full)
            except OSError:
                continue
            _upsert(conn, full, size, filehash, mtime)
    conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_index.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add docsort/index.py tests/test_index.py
git commit -m "feat(index): add hash_file() and scan_directory()"
```

---

### Task 3: Archive-aware zip scanning (nested, depth-capped, budget-capped)

**Files:**
- Modify: `docsort/index.py`
- Test: `tests/test_index.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_index.py
import io
import zipfile
from docsort.index import scan_zip, MAX_ARCHIVE_DEPTH

def _make_zip(path, entries):
    """entries: dict of {internal_name: bytes}"""
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)

def test_scan_zip_indexes_internal_files(tmp_path):
    zpath = tmp_path / "outer.zip"
    _make_zip(zpath, {"a.txt": b"one", "sub/b.txt": b"two"})

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_zip(conn, str(zpath), str(zpath), depth=0, budget=10**9)

    rows = conn.execute("SELECT path, archive_depth, source_archive FROM files ORDER BY path").fetchall()
    assert len(rows) == 2
    assert rows[0][0] == f"{zpath}::a.txt"
    assert rows[0][1] == 0
    assert rows[0][2] == str(zpath)
    conn.close()

def test_scan_zip_recurses_into_nested_zip(tmp_path):
    inner_bytes = io.BytesIO()
    with zipfile.ZipFile(inner_bytes, "w") as zf:
        zf.writestr("deep.txt", b"deep content")

    outer_path = tmp_path / "outer.zip"
    _make_zip(outer_path, {"inner.zip": inner_bytes.getvalue()})

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_zip(conn, str(outer_path), str(outer_path), depth=0, budget=10**9)

    rows = conn.execute("SELECT path, archive_depth FROM files ORDER BY path").fetchall()
    paths = [r[0] for r in rows]
    assert f"{outer_path}::inner.zip::deep.txt" in paths
    deep_row = [r for r in rows if r[0].endswith("deep.txt")][0]
    assert deep_row[1] == 1
    conn.close()

def test_scan_zip_stops_at_max_depth(tmp_path):
    # build a chain of MAX_ARCHIVE_DEPTH + 2 nested zips
    payload = b"bottom"
    for _ in range(MAX_ARCHIVE_DEPTH + 2):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("next.zip" if payload != b"bottom" else "bottom.txt", payload)
        payload = buf.getvalue()

    outer_path = tmp_path / "chain.zip"
    outer_path.write_bytes(payload)

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_zip(conn, str(outer_path), str(outer_path), depth=0, budget=10**9)

    exceeded = conn.execute(
        "SELECT path FROM files WHERE path LIKE '%DEPTH_EXCEEDED%'"
    ).fetchall()
    assert len(exceeded) >= 1
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_index.py -v`
Expected: FAIL with `ImportError: cannot import name 'scan_zip'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to docsort/index.py
import io
import zipfile

MAX_ARCHIVE_DEPTH = 6

def scan_zip(conn, zip_source, virtual_prefix, depth, budget):
    """zip_source: a path (str) or a file-like object (io.BytesIO) opened as a zip."""
    if depth > MAX_ARCHIVE_DEPTH:
        _upsert(conn, f"{virtual_prefix}!!DEPTH_EXCEEDED", 0, None, time.time(),
                archive_depth=depth, source_archive=str(zip_source))
        conn.commit()
        return budget

    try:
        with zipfile.ZipFile(zip_source) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if info.file_size > budget:
                    _upsert(conn, f"{virtual_prefix}::{info.filename}!!BUDGET_EXCEEDED",
                            info.file_size, None, time.time(),
                            archive_depth=depth, source_archive=str(zip_source))
                    continue
                data = zf.read(info)
                budget -= len(data)
                vpath = f"{virtual_prefix}::{info.filename}"
                filehash = hash_bytes_(data)
                _upsert(conn, vpath, info.file_size, filehash, time.time(),
                        archive_depth=depth, source_archive=str(zip_source))
                if info.filename.lower().endswith(".zip"):
                    budget = scan_zip(conn, io.BytesIO(data), vpath, depth + 1, budget)
    except zipfile.BadZipFile:
        pass
    conn.commit()
    return budget

def hash_bytes_(data):
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_index.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add docsort/index.py tests/test_index.py
git commit -m "feat(index): archive-aware zip scan, nested + depth-capped"
```

---

### Task 4: scan_root() — combined entry point

**Files:**
- Modify: `docsort/index.py`
- Test: `tests/test_index.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_index.py
from docsort.index import scan_root

def test_scan_root_indexes_files_and_zips_together(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"loose file")
    _make_zip(tmp_path / "archive.zip", {"in.txt": b"in zip"})

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    count = scan_root(conn, str(tmp_path))

    assert count == 3  # a.txt, archive.zip itself, archive.zip::in.txt
    paths = [r[0] for r in conn.execute("SELECT path FROM files").fetchall()]
    assert any(p.endswith("a.txt") for p in paths)
    assert any(p.endswith("archive.zip") for p in paths)
    assert any(p.endswith("archive.zip::in.txt") for p in paths)
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_index.py -v`
Expected: FAIL with `ImportError: cannot import name 'scan_root'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to docsort/index.py
MAX_ARCHIVE_EXTRACT_BYTES = 500 * 1024 * 1024  # 500MB per top-level archive

def scan_root(conn, root):
    """Walk root; index every plain file, and descend into every .zip found."""
    count = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(full)
                mtime = os.path.getmtime(full)
                filehash = hash_file(full)
            except OSError:
                continue
            _upsert(conn, full, size, filehash, mtime)
            count += 1
            if name.lower().endswith(".zip"):
                before = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
                scan_zip(conn, full, full, depth=0, budget=MAX_ARCHIVE_EXTRACT_BYTES)
                after = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
                count += (after - before)
    conn.commit()
    return count
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_index.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add docsort/index.py tests/test_index.py
git commit -m "feat(index): scan_root() combined directory+archive entry point"
```

---

### Task 5: Wire `docsort --scan PATH` CLI flag

**Files:**
- Modify: `docsort/cli.py` (add argparse flag + handler; append near existing `--report`/`--stats` flag handling)
- Test: `tests/test_index.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_index.py
import subprocess
import sys

def test_cli_scan_flag_reports_count(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x")
    (tmp_path / "b.txt").write_bytes(b"y")
    result = subprocess.run(
        [sys.executable, "-m", "docsort.cli", str(tmp_path), "--scan"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    assert "indexed" in result.stdout.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_index.py -v`
Expected: FAIL — `--scan` not a recognized argument (argparse error, nonzero exit)

- [ ] **Step 3: Write minimal implementation**

In `docsort/cli.py`, find the `argparse.ArgumentParser()` block where existing flags like `--report`,
`--undo`, `--stats` are added, and add:

```python
    ap.add_argument("--scan", action="store_true",
                     help="Build/refresh the ground-truth index for root, then exit (no classification).")
```

Then, in `main()`, before the classification loop begins (alongside the existing early-exit branches for
`--report`/`--undo`/`--stats`), add:

```python
    if a.scan:
        from docsort.index import open_index, scan_root
        import os
        db_path = os.path.join(a.root, "_docsort_index.db")
        conn = open_index(db_path)
        count = scan_root(conn, a.root)
        conn.close()
        print(f"Indexed {count} entries into {db_path}")
        return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_index.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add docsort/cli.py tests/test_index.py
git commit -m "feat(cli): wire --scan flag to index.scan_root()"
```

---

## Self-review

**Spec coverage (§3.1–3.2 of the design doc):**
- Ground-truth index, SQLite, path/size/hash/mtime/archive_depth/source_archive schema → Task 1. ✅
  (`embedding`, `tags`, `dupe_group`, `subtree_signature` columns are added by the Classify/Dedup plans
  that build on this index — not needed until those plans touch them; adding unused columns now would be
  speculative schema per YAGNI.)
- Plain directory scan → Task 2. ✅
- Zip recursion, nested zips, depth cap (default 6), extraction-size budget, overflow reported not
  silently dropped → Task 3, `test_scan_zip_stops_at_max_depth`. ✅
- Combined scan entry point, "applies across every root and subfolder" → Task 4. ✅
- `docsort --scan PATH`, cheap/no-LLM, re-runnable → Task 5. ✅

**Placeholder scan:** no TBD/TODO; every step has runnable code and an exact expected-output line.

**Type consistency:** `open_index`, `hash_file`, `scan_directory`, `scan_zip`, `scan_root` signatures used
consistently task to task; `_upsert` internal helper introduced in Task 2, reused unchanged in Tasks 3–4.

---

Plan complete and saved to `docs/superpowers/plans/2026-07-01-drive-index-archive-scan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
