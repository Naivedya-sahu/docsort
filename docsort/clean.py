import hashlib
import json
import os
import shutil
import time

from docsort.dedup import find_exact_duplicates, find_duplicate_subtrees, find_near_duplicates
from docsort.vendor import find_vendor_dumps


def generate_clean_report(conn, root, near_dup_threshold=0.8):
    return {
        "exact_duplicates": find_exact_duplicates(conn),
        "duplicate_subtrees": find_duplicate_subtrees(conn, root),
        "near_duplicates": find_near_duplicates(conn, threshold=near_dup_threshold),
        "vendor_dumps": find_vendor_dumps(conn, root),
    }


def _quarantine_dest(quarantine_dir, src):
    # flatten into quarantine_dir using a hash of the original path to avoid collisions
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
