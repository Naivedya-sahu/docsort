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


def find_near_duplicates(conn, threshold=0.8):
    """Cluster files whose embeddings exceed threshold cosine similarity.
    Review-only signal — highest false-positive risk of the three dedup layers,
    never auto-applied. O(n^2) pairwise; fine at personal-drive scale, revisit
    with an ANN index if this ever needs to run over millions of files."""
    from docsort.embed import cosine_similarity

    rows = conn.execute(
        "SELECT path, embedding FROM files WHERE embedding IS NOT NULL"
    ).fetchall()
    items = [(path, tuple(float(x) for x in emb.split(","))) for path, emb in rows]

    parent = {path: path for path, _ in items}

    def find(p):
        while parent[p] != p:
            parent[p] = parent[parent[p]]
            p = parent[p]
        return p

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            path_a, vec_a = items[i]
            path_b, vec_b = items[j]
            if cosine_similarity(vec_a, vec_b) >= threshold:
                union(path_a, path_b)

    groups = {}
    for path, _ in items:
        root = find(path)
        groups.setdefault(root, []).append(path)
    return [paths for paths in groups.values() if len(paths) >= 2]
