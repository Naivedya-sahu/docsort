import os

from docsort.index import open_index, scan_directory, embed_index
from docsort.dedup import (
    find_exact_duplicates, subtree_signature, find_duplicate_subtrees, find_near_duplicates,
)


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

    groups = find_duplicate_subtrees(conn, str(root))
    matched = [g for g in groups if len(g) >= 2]
    assert len(matched) == 1
    assert {os.path.basename(p) for p in matched[0]} == {"TreeA", "TreeB"}
    conn.close()


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
