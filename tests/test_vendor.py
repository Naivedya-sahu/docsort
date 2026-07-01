import os

from docsort.index import open_index, scan_directory
from docsort.vendor import find_vendor_dumps


def test_find_vendor_dumps_matches_master_main_suffix(tmp_path):
    root = tmp_path / "data"
    (root / "eagle_libraries-master").mkdir(parents=True)
    (root / "eagle_libraries-master" / "ac_dc.lbr").write_bytes(b"lib")
    (root / "my-project-main").mkdir(parents=True)
    (root / "my-project-main" / "readme.md").write_bytes(b"readme")
    (root / "MyNotes").mkdir(parents=True)
    (root / "MyNotes" / "notes.txt").write_bytes(b"notes")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))

    flagged = find_vendor_dumps(conn, str(root))
    names = {os.path.basename(p) for p in flagged}
    assert names == {"eagle_libraries-master", "my-project-main"}
    conn.close()
