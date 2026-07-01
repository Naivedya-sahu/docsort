import os


def find_exact_duplicates(conn):
    """Group indexed files by content hash; return {hash: [paths]} for hashes with 2+ files."""
    rows = conn.execute(
        "SELECT hash, path FROM files WHERE hash IS NOT NULL"
    ).fetchall()
    by_hash = {}
    for filehash, path in rows:
        by_hash.setdefault(filehash, []).append(path)
    return {h: paths for h, paths in by_hash.items() if len(paths) >= 2}


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
