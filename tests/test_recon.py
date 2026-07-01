import os

from docsort.recon import NameEmbedder, recon_scan, classify_names
from docsort.cascade import build_centroids


def test_name_embedder_falls_back_to_stdlib_without_sentence_transformers():
    """sentence-transformers is not installed in this environment -- this exercises
    the real fallback path, not a simulated one."""
    embedder = NameEmbedder()
    assert embedder.backend == "stdlib"
    vec = embedder.embed("BJT transistor notes")
    assert isinstance(vec, tuple)
    assert len(vec) == 128   # embed.DIMS, the stdlib fallback's dimensionality


def test_recon_scan_collects_files_and_folders_no_content_read(tmp_path):
    root = tmp_path / "data"
    (root / "GATE_Prep").mkdir(parents=True)
    (root / "GATE_Prep" / "syllabus.pdf").write_bytes(b"pdf bytes never read by recon")
    (root / "_docsort_index.db").write_bytes(b"should be skipped")

    entries = recon_scan(str(root))
    names = {(e["name"], e["is_dir"]) for e in entries}
    assert ("GATE_Prep", True) in names
    assert ("syllabus.pdf", False) in names
    assert not any(e["name"].startswith("_docsort") for e in entries)


def test_classify_names_suggests_stream_and_subject_from_name_alone(tmp_path):
    root = tmp_path / "data"
    (root / "GATE_EC_Syllabus").mkdir(parents=True)
    (root / "GATE_EC_Syllabus" / "formula_book.pdf").write_bytes(b"never read")

    entries = recon_scan(str(root))
    stream_centroids = build_centroids({
        "CW": "CW coursework degree material notes assignments lab",
        "GATE": "GATE competitive exam prep syllabus formula book previous year questions",
    })
    subject_centroids = build_centroids({
        "10CTRL": "10CTRL control systems transfer function bode root locus",
        "99UNS": "unsure unknown",
    })
    embedder = NameEmbedder()

    results = classify_names(entries, stream_centroids, subject_centroids, embedder)
    by_name = {r["name"]: r for r in results}
    assert by_name["GATE_EC_Syllabus"]["stream"] == "GATE"
    assert "stream_score" in by_name["GATE_EC_Syllabus"]
    assert "subject_score" in by_name["GATE_EC_Syllabus"]
