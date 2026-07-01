from docsort.index import open_index, scan_directory
from docsort.reorg import find_thin_chains, propose_flatten


def test_find_thin_chains_detects_single_child_nesting(tmp_path):
    root = tmp_path / "data"
    (root / "A" / "B" / "C").mkdir(parents=True)
    (root / "A" / "B" / "C" / "file.txt").write_bytes(b"content")
    (root / "Normal").mkdir(parents=True)
    (root / "Normal" / "x.txt").write_bytes(b"x")
    (root / "Normal" / "y.txt").write_bytes(b"y")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))

    chains = find_thin_chains(conn, str(root), min_length=2)
    assert len(chains) == 1
    chain = chains[0]
    assert chain["start"] == str(root / "A")
    assert chain["end"] == str(root / "A" / "B" / "C")
    assert chain["length"] == 3
    conn.close()


def test_find_thin_chains_respects_min_length(tmp_path):
    root = tmp_path / "data"
    # only 2 directories in the chain (data -> A) — below min_length=3
    (root / "A").mkdir(parents=True)
    (root / "A" / "file.txt").write_bytes(b"content")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))

    chains = find_thin_chains(conn, str(root), min_length=3)
    assert chains == []
    conn.close()


def test_propose_flatten_moves_end_contents_to_start(tmp_path):
    root = tmp_path / "data"
    # root itself has only one child (A) -> the whole chain, including root, is thin
    (root / "A" / "B" / "C").mkdir(parents=True)
    (root / "A" / "B" / "C" / "file.txt").write_bytes(b"content")

    db_path = tmp_path / "index.db"
    conn = open_index(str(db_path))
    scan_directory(conn, str(root))

    chains = find_thin_chains(conn, str(root), min_length=2)
    moves = propose_flatten(conn, chains)

    assert len(moves) == 1
    src, dst = moves[0]
    assert src == str(root / "A" / "B" / "C" / "file.txt")
    assert dst == str(root / "file.txt")
    conn.close()
