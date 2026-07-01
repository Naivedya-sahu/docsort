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
