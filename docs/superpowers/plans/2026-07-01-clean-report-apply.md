# Clean-Phase Report + Apply Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Plan 6 of v0.13.x. The 4 Clean-phase detectors (Plan 2/4: exact-hash, subtree-signature,
near-dup, vendor-dump) exist but have no CLI surface — nothing invokes them yet. This plan wires
`--clean-report` (combines all 4, dry-run, prints/saves a report) and `--apply-clean QUARANTINE_DIR`
(moves confirmed delete-candidates, journal-backed with its own dedicated JSONL log distinct from the
classify-run journal, since Clean-phase actions — quarantine moves — are a different action type than
renames/tags and don't fit the existing journal's STREAM/SUBJECT-shaped schema).

**Architecture:** New `docsort/clean.py`: `generate_clean_report(conn)` returns one structured dict
combining all 4 detectors' output; `apply_clean(conn, report, quarantine_dir, dry_run=True)` decides one
"keep" item per group (the first/canonical one) and moves the rest, writing `_docsort_clean_log.jsonl`
(one line per move: `{src, dst, reason, group_id, ts}`) so the moves are auditable and reversible by hand
or a future `--undo-clean`.

**Tech Stack:** Python stdlib (`shutil`, `json`) + the existing `docsort/index.py`/`dedup.py`/`vendor.py`.

---

### Task 1: `clean.generate_clean_report()`

**Files:** Create `docsort/clean.py`, Create `tests/test_clean.py`

- [ ] **Step 1: failing test**

```python
# tests/test_clean.py
from docsort.index import open_index, scan_directory, embed_index
from docsort.clean import generate_clean_report

def test_generate_clean_report_combines_all_four_detectors(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "a.txt").write_bytes(b"same")
    (root / "b.txt").write_bytes(b"same")  # exact dup of a.txt
    (root / "vendor-master").mkdir()
    (root / "vendor-master" / "lib.c").write_bytes(b"vendored")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))
    embed_index(conn)

    report = generate_clean_report(conn)
    assert set(report.keys()) == {"exact_duplicates", "duplicate_subtrees", "near_duplicates", "vendor_dumps"}
    assert len(report["exact_duplicates"]) == 1
    assert len(report["vendor_dumps"]) == 1
    conn.close()
```

- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_clean.py -v` — expect FAIL,
  `ModuleNotFoundError: No module named 'docsort.clean'`

- [ ] **Step 3: implementation**

```python
# docsort/clean.py
from docsort.dedup import find_exact_duplicates, find_duplicate_subtrees, find_near_duplicates
from docsort.vendor import find_vendor_dumps


def generate_clean_report(conn, near_dup_threshold=0.8):
    return {
        "exact_duplicates": find_exact_duplicates(conn),
        "duplicate_subtrees": find_duplicate_subtrees(conn),
        "near_duplicates": find_near_duplicates(conn, threshold=near_dup_threshold),
        "vendor_dumps": find_vendor_dumps(conn),
    }
```

- [ ] **Step 4:** Run tests — expect PASS

- [ ] **Step 5: commit**

```bash
git add docsort/clean.py tests/test_clean.py
git commit -m "feat(clean): add generate_clean_report() combining all 4 detectors"
```

---

### Task 2: `clean.apply_clean()` — quarantine move, dry-run by default

**Files:** Modify `docsort/clean.py`, `tests/test_clean.py`

- [ ] **Step 1: failing test**

```python
# append to tests/test_clean.py
import json
import os

from docsort.clean import apply_clean

def test_apply_clean_dry_run_moves_nothing(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "a.txt").write_bytes(b"same")
    (root / "b.txt").write_bytes(b"same")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))
    embed_index(conn)
    report = generate_clean_report(conn)

    quarantine = tmp_path / "quarantine"
    moves = apply_clean(conn, report, str(quarantine), dry_run=True)

    assert len(moves) == 1  # one of the two dup files would move, keeping the other
    assert not quarantine.exists()  # dry-run: nothing actually moved
    assert (root / "a.txt").exists() and (root / "b.txt").exists()
    conn.close()

def test_apply_clean_real_run_moves_and_logs(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "a.txt").write_bytes(b"same")
    (root / "b.txt").write_bytes(b"same")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))
    embed_index(conn)
    report = generate_clean_report(conn)

    quarantine = tmp_path / "quarantine"
    log_path = tmp_path / "_docsort_clean_log.jsonl"
    moves = apply_clean(conn, report, str(quarantine), dry_run=False, log_path=str(log_path))

    assert len(moves) == 1
    src, dst = moves[0]
    assert not os.path.exists(src)
    assert os.path.exists(dst)
    assert log_path.exists()
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["src"] == src and row["dst"] == dst and row["reason"] == "exact_duplicate"
    conn.close()
```

- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_clean.py -v` — expect FAIL,
  `ImportError: cannot import name 'apply_clean'`

- [ ] **Step 3: implementation**

```python
# add to docsort/clean.py
import json
import os
import shutil
import time


def _quarantine_dest(quarantine_dir, src):
    # flatten into quarantine_dir using a hash of the original path to avoid collisions
    import hashlib
    tag = hashlib.md5(src.encode("utf-8")).hexdigest()[:10]
    return os.path.join(quarantine_dir, f"{tag}_{os.path.basename(src)}")


def apply_clean(conn, report, quarantine_dir, dry_run=True, log_path=None):
    """Move all-but-one of each exact/near-dup group, and every vendor-dump dir, into
    quarantine_dir. Returns [(src, dst), ...]. dry_run=True computes the move list only."""
    moves = []
    reasons = []

    for group in report["exact_duplicates"].values():
        for src in sorted(group)[1:]:  # keep the first, quarantine the rest
            moves.append((src, _quarantine_dest(quarantine_dir, src)))
            reasons.append("exact_duplicate")

    for group in report["duplicate_subtrees"]:
        for src in sorted(group)[1:]:
            moves.append((src, _quarantine_dest(quarantine_dir, src)))
            reasons.append("duplicate_subtree")

    for group in report["near_duplicates"]:
        for src in sorted(group)[1:]:
            moves.append((src, _quarantine_dest(quarantine_dir, src)))
            reasons.append("near_duplicate")

    for src in report["vendor_dumps"]:
        moves.append((src, _quarantine_dest(quarantine_dir, src)))
        reasons.append("vendor_dump")

    if dry_run:
        return moves

    os.makedirs(quarantine_dir, exist_ok=True)
    log_f = open(log_path, "a", encoding="utf-8") if log_path else None
    try:
        for (src, dst), reason in zip(moves, reasons):
            if not os.path.exists(src):
                continue
            shutil.move(src, dst)
            if log_f:
                log_f.write(json.dumps({
                    "src": src, "dst": dst, "reason": reason, "ts": time.time(),
                }) + "\n")
    finally:
        if log_f:
            log_f.close()
    return moves
```

- [ ] **Step 4:** Run tests — expect PASS

- [ ] **Step 5: commit**

```bash
git add docsort/clean.py tests/test_clean.py
git commit -m "feat(clean): add apply_clean() quarantine move, dry-run by default"
```

---

### Task 3: wire `--clean-report` and `--apply-clean` CLI flags

**Files:** Modify `docsort/cli.py`

- [ ] **Step 1:** Add flags in `add_args()`, near `--scan`:

```python
    ap.add_argument("--clean-report",dest="clean_report",action="store_true",
                    help="build the index (if needed) and print a dedup/vendor-dump report, then exit")
    ap.add_argument("--apply-clean",dest="apply_clean_dir",default=None,metavar="QUARANTINE_DIR",
                    help="apply a prior --clean-report's findings: move confirmed items into QUARANTINE_DIR")
```

- [ ] **Step 2:** Add handlers in `main()`, alongside the existing `if a.scan:` branch:

```python
    if a.clean_report:
        from docsort.index import open_index, scan_root, embed_index
        from docsort.clean import generate_clean_report
        db_path=os.path.join(a.root,"_docsort_index.db")
        conn=open_index(db_path)
        scan_root(conn,a.root); embed_index(conn)
        report=generate_clean_report(conn)
        conn.close()
        print(f"Exact-duplicate groups: {len(report['exact_duplicates'])}")
        print(f"Duplicate subtree groups: {len(report['duplicate_subtrees'])}")
        print(f"Near-duplicate groups: {len(report['near_duplicates'])}")
        print(f"Vendor-dump dirs: {len(report['vendor_dumps'])}")
        return
    if a.apply_clean_dir:
        from docsort.index import open_index, scan_root, embed_index
        from docsort.clean import generate_clean_report, apply_clean
        db_path=os.path.join(a.root,"_docsort_index.db")
        conn=open_index(db_path)
        scan_root(conn,a.root); embed_index(conn)
        report=generate_clean_report(conn)
        log_path=os.path.join(a.root,"_docsort_clean_log.jsonl")
        moves=apply_clean(conn,report,a.apply_clean_dir,dry_run=False,log_path=log_path)
        conn.close()
        print(f"Moved {len(moves)} items to {a.apply_clean_dir} (log: {log_path})")
        return
```

  Place both branches after `if a.scan: ...; return` (same offline-early-exit group, before the
  model-dependent classify loop begins).

- [ ] **Step 3:** Run full suite + a real smoke test:

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: all PASS (additive-only, new flags default to falsy/None).

- [ ] **Step 4: commit**

```bash
git add docsort/cli.py
git commit -m "feat(cli): wire --clean-report and --apply-clean flags"
```

---

## Self-review

**Spec coverage:** Clean-phase review report (§3.5, "all three dedup layers + vendor detection land in
one combined review report") ✅ Task 1/3. Quarantine-move apply, "nothing auto-deleted," own audit log ✅
Task 2. This is the CLI surface; the Reports-tab GUI rendering of the same report is §3.9's remaining
GUI plan, not this one.

**Placeholder scan:** none.

**Design choice worth flagging:** the "keep first, quarantine rest" policy (`sorted(group)[1:]`) is a
simple deterministic default — sorted order, not "newest" or "shortest path." Fine for a dry-run-reviewed
quarantine move (nothing is destructive, everything sits in quarantine for the DupeGuru/manual review
step per spec §3.8), but call this out if a smarter "which copy is canonical" heuristic is ever wanted.
