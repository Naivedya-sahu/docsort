import json
import os
import shutil
import time

from docsort.tree import DirectoryTree


def find_thin_chains(conn, root, min_length=3):
    """Detect runs of directories where each has exactly one child total — a
    subdirectory, with no loose files of its own. A folder with a subdir AND its
    own files is not a pure pass-through wrapper even though it has only one
    subdirectory; the chain must stop there, not walk past it (see DirectoryTree).
    Returns [{"start": path, "end": path, "length": N}, ...] for chains >= min_length."""
    tree = DirectoryTree.from_index(conn, root)
    all_dirs = tree.all_dirs()
    thin = {d for d in all_dirs
            if tree.child_count(d) == 1 and len(tree.child_dirs(d)) == 1}
    chain_starts = [d for d in thin if os.path.dirname(d) not in thin]

    chains = []
    for start in chain_starts:
        length = 1
        cur = start
        while True:
            kids = tree.child_dirs(cur)
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


def propose_flatten(conn, chains):
    """Dry-run move list: for each chain, move the terminal folder's direct files up to
    the chain's start folder, collapsing the thin wrappers in between. Caller applies via
    the existing shutil.move + journal pattern — this function only proposes."""
    moves = []
    rows = conn.execute("SELECT path FROM files").fetchall()
    all_files = [p for (p,) in rows]
    for chain in chains:
        end = chain["end"]
        start = chain["start"]
        prefix = end + os.sep
        for f in all_files:
            if f.startswith(prefix):
                rel = f[len(prefix):]
                dst = os.path.join(start, rel)
                moves.append((f, dst))
    return moves


def apply_moves(moves, dry_run=True, log_path=None):
    """Execute a (src, dst) move list, logging each move as JSONL. dry_run=True is a no-op
    that just returns the list unchanged (same dry-run-by-default pattern as clean.apply_clean)."""
    if dry_run:
        return moves

    log_f = open(log_path, "a", encoding="utf-8") if log_path else None
    applied = []
    try:
        for src, dst in moves:
            if not os.path.exists(src):
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            applied.append((src, dst))
            if log_f:
                log_f.write(json.dumps({"src": src, "dst": dst, "ts": time.time()}) + "\n")
    finally:
        if log_f:
            log_f.close()
    return applied
