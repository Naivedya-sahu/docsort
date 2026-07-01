from docsort.dedup import find_exact_duplicates, find_duplicate_subtrees, find_near_duplicates
from docsort.vendor import find_vendor_dumps


def generate_clean_report(conn, near_dup_threshold=0.8):
    return {
        "exact_duplicates": find_exact_duplicates(conn),
        "duplicate_subtrees": find_duplicate_subtrees(conn),
        "near_duplicates": find_near_duplicates(conn, threshold=near_dup_threshold),
        "vendor_dumps": find_vendor_dumps(conn),
    }
