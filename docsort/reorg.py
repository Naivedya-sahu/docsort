import os

from docsort.index import list_directories


def _children_of(all_dirs, d):
    return [x for x in all_dirs if os.path.dirname(x) == d]


def find_thin_chains(conn, root, min_length=3):
    """Detect runs of directories where each has exactly one subdirectory child.
    Scoped to `root` (and its descendants) — list_directories() also returns filesystem
    ancestors above the scanned root, which must not be treated as reorg candidates.
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
                cur = nxt
                length += 1
                break
        if length >= min_length:
            chains.append({"start": start, "end": cur, "length": length})
    return chains
