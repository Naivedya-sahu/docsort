import os
import re

from docsort.tree import DirectoryTree

_VENDOR_SUFFIX = re.compile(r"-(master|main)$", re.IGNORECASE)


def is_vendor_dump_dir(dirname):
    """Heuristic: GitHub zip-download naming convention (repo-master / repo-main)."""
    return bool(_VENDOR_SUFFIX.search(os.path.basename(dirname.rstrip(os.sep))))


def find_vendor_dumps(conn, root):
    """Scoped to `root` via DirectoryTree — an unscoped directory listing also
    returns filesystem ancestors above the scanned root."""
    tree = DirectoryTree.from_index(conn, root)
    return [d for d in tree.all_dirs() if is_vendor_dump_dir(d)]
