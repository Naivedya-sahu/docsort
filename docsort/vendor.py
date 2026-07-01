import os
import re

from docsort.index import list_directories

_VENDOR_SUFFIX = re.compile(r"-(master|main)$", re.IGNORECASE)


def is_vendor_dump_dir(dirname):
    """Heuristic: GitHub zip-download naming convention (repo-master / repo-main)."""
    return bool(_VENDOR_SUFFIX.search(os.path.basename(dirname.rstrip(os.sep))))


def find_vendor_dumps(conn):
    return [d for d in list_directories(conn) if is_vendor_dump_dir(d)]
