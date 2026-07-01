import hashlib
import io
import os
import sqlite3
import time
import zipfile

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


def open_index(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


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


MAX_ARCHIVE_DEPTH = 6


def _hash_bytes(data):
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


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
                filehash = _hash_bytes(data)
                _upsert(conn, vpath, info.file_size, filehash, time.time(),
                        archive_depth=depth, source_archive=str(zip_source))
                if info.filename.lower().endswith(".zip"):
                    budget = scan_zip(conn, io.BytesIO(data), vpath, depth + 1, budget)
    except zipfile.BadZipFile:
        pass
    conn.commit()
    return budget


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
