import io
import sqlite3
import subprocess
import sys
import zipfile
import pytest
from docsort.index import (
    open_index, SCHEMA, hash_file, scan_directory, scan_zip, MAX_ARCHIVE_DEPTH, scan_root,
    set_embedding, get_embedding, embed_index, index_session,
)


def test_open_index_creates_files_table(tmp_path):
    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files'")
    assert cur.fetchone() is not None
    cols = {row[1] for row in conn.execute("PRAGMA table_info(files)")}
    assert cols == {
        "path", "size", "hash", "mtime", "archive_depth", "source_archive", "embedding"
    }
    conn.close()


def test_hash_file_is_stable(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello world")
    h1 = hash_file(str(f))
    h2 = hash_file(str(f))
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest


def test_scan_directory_indexes_all_files(tmp_path):
    data_root = tmp_path / "data"
    (data_root / "sub").mkdir(parents=True)
    (data_root / "a.txt").write_bytes(b"one")
    (data_root / "sub" / "b.txt").write_bytes(b"two")

    db_path = tmp_path / "index.db"  # deliberately outside data_root
    conn = open_index(str(db_path))
    scan_directory(conn, str(data_root))

    rows = conn.execute("SELECT path, size, archive_depth FROM files ORDER BY path").fetchall()
    assert len(rows) == 2
    assert all(r[2] == 0 for r in rows)  # archive_depth 0 for plain files
    conn.close()


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


def test_scan_root_indexes_files_and_zips_together(tmp_path):
    data_root = tmp_path / "data"  # separate from db_path — db must not self-index
    data_root.mkdir()
    (data_root / "a.txt").write_bytes(b"loose file")
    _make_zip(data_root / "archive.zip", {"in.txt": b"in zip"})

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    count = scan_root(conn, str(data_root))

    assert count == 3  # a.txt, archive.zip itself, archive.zip::in.txt
    paths = [r[0] for r in conn.execute("SELECT path FROM files").fetchall()]
    assert any(p.endswith("a.txt") for p in paths)
    assert any(p.endswith("archive.zip") for p in paths)
    assert any(p.endswith("archive.zip::in.txt") for p in paths)
    conn.close()


def test_cli_scan_flag_reports_count(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x")
    (tmp_path / "b.txt").write_bytes(b"y")
    result = subprocess.run(
        [sys.executable, "-m", "docsort.cli", str(tmp_path), "--scan"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    assert "indexed" in result.stdout.lower()


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
    assert len(vec) == 128
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


def test_scan_root_does_not_index_its_own_db_file(tmp_path):
    """Real bug found via index_session: cli.py puts _docsort_index.db INSIDE the
    scanned root for every index-backed command. scan_root must not index its own
    database as if it were data — it would grow every re-scan since the db file's
    own size/hash changes each time it's rewritten."""
    root = tmp_path / "data"
    root.mkdir()
    (root / "a.txt").write_bytes(b"1")
    (root / "b.txt").write_bytes(b"2")

    db_path = root / "_docsort_index.db"   # deliberately inside root, matching cli.py
    conn = open_index(str(db_path))
    count = scan_root(conn, str(root))

    assert count == 2   # not 3 — the db file itself must be excluded
    paths = [p for (p,) in conn.execute("SELECT path FROM files").fetchall()]
    assert not any("_docsort_index.db" in p for p in paths)
    conn.close()


def test_index_session_opens_scans_and_closes(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "a.txt").write_bytes(b"1")
    (root / "b.txt").write_bytes(b"2")

    with index_session(str(root)) as conn:
        count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        assert count == 2
        assert get_embedding(conn, str(root / "a.txt")) is None   # no embeddings unless requested

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")   # closed on exit


def test_index_session_embeds_when_requested(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "a.txt").write_bytes(b"1")

    with index_session(str(root), need_embeddings=True) as conn:
        assert get_embedding(conn, str(root / "a.txt")) is not None
