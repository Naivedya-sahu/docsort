import json
import os

from docsort.index import open_index, scan_directory, embed_index
from docsort.clean import generate_clean_report, apply_clean


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

    report = generate_clean_report(conn, str(root))
    assert set(report.keys()) == {"exact_duplicates", "duplicate_subtrees", "near_duplicates", "vendor_dumps"}
    assert len(report["exact_duplicates"]) == 1
    assert len(report["vendor_dumps"]) == 1
    conn.close()


def test_apply_clean_dry_run_moves_nothing(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "a.txt").write_bytes(b"same")
    (root / "b.txt").write_bytes(b"same")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))
    embed_index(conn)
    report = generate_clean_report(conn, str(root))

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
    report = generate_clean_report(conn, str(root))

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
