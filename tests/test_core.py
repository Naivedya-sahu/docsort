"""Pure-logic tests for docsort — no model, no network."""
import argparse, os, json
import pytest
from docsort import cli, config


def _tmp(text, tmp_path, name="TAGS.md"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_load_tags_bundled():
    s, su, ty = cli.load_tags(config._bundled("TAGS.md"))
    assert "CW" in s and "GATE" in s
    assert "99UNS" in su and "08DIG" in su
    assert "notes" in ty and "misc" in ty


def test_passes_filter():
    P = cli.passes_filter
    root, f = "C:/d", "C:/d/GATE/notes/x.pdf"
    assert P(f, root, [], []) is True
    assert P(f, root, [], ["GATE"]) is False          # excluded
    assert P(f, root, ["GATE"], []) is True            # included
    assert P(f, root, ["RES"], []) is False            # include miss
    assert P(f, root, [], ["GATE/notes"]) is False     # nested segment


def test_decide_and_proposal():
    s, su, ty = cli.load_tags(config._bundled("TAGS.md"))
    cli.STREAMS, cli.SUBJECTS, cli.TYPES = set(s), set(su), set(ty)
    assert cli.decide("CW 08DIG notes high") == ("CW", "08DIG", "notes", "high")
    st, sub, _, _ = cli.decide("CW 99UNS notes high PROPOSE:THERMO")
    assert sub == "~THERMO"


def test_tag_editor_roundtrip(tmp_path):
    from docsort import tagsio
    txt = open(config._bundled("TAGS.md"), encoding="utf-8").read()
    subs = tagsio.tag_block(txt, "SUBJECTS")
    subs.append("93TEST  a new subject")
    new = tagsio.replace_block(txt, "SUBJECTS", subs)
    _, su, _ = cli.load_tags(_tmp(new, tmp_path))
    assert "93TEST" in su


def test_run_continues_without_model_server_when_vision_not_needed(tmp_path, monkeypatch):
    """Real bug: main()'s pre-flight model check called ap.error() (hard sys.exit) whenever
    the model server was unreachable -- unconditionally, even though EMBED-tier
    classification (the default for every non-vision file) needs no model at all. This
    aborted the entire run with zero files processed if LM Studio wasn't running,
    contradicting the whole point of the EMBED-only design. vision defaults ON from
    config, so this is the exact default scenario, not an edge case."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    d = tmp_path / "run"; d.mkdir()
    (d / "known.pdf").write_text("x", encoding="utf-8")

    def fake_classify(a, sysp, full, fn, rel):
        return ("CW", "08DIG", "notes", "high", "embed")
    monkeypatch.setattr(cli, "classify", fake_classify)
    monkeypatch.setattr(cli, "resolve_model", lambda *a, **k: ("m", False))  # server unreachable

    cli.main([str(d), "--apply"])   # no SystemExit -- run must complete via EMBED alone
    assert (d / "[CW-08DIG] known.pdf").exists()


def test_skip_unknown(tmp_path, monkeypatch):
    """--skip-unknown leaves 99UNS files untouched; known files still rename."""
    monkeypatch.setenv("APPDATA", str(tmp_path))                 # isolate journal/index
    d = tmp_path / "run"; d.mkdir()
    (d / "unknown.pdf").write_text("x", encoding="utf-8")
    (d / "known.pdf").write_text("x", encoding="utf-8")

    def fake_classify(a, sysp, full, fn, rel):
        return ("CW", "99UNS", "misc", "low", "text") if "unknown" in fn \
            else ("CW", "08DIG", "notes", "high", "text")
    monkeypatch.setattr(cli, "classify", fake_classify)
    monkeypatch.setattr(cli, "resolve_model", lambda *a, **k: ("m", True))

    cli.main([str(d), "--apply", "--skip-unknown", "--no-misc"])
    assert (d / "unknown.pdf").exists()                          # untouched
    assert not (d / "[CW-99UNS] unknown.pdf").exists()           # NOT renamed
    assert (d / "[CW-08DIG] known.pdf").exists()                 # known still renamed


def test_report_and_undo(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))          # isolate the global index
    d = str(tmp_path / "run"); os.makedirs(os.path.join(d, "misc"))
    open(os.path.join(d, "[CW-08DIG] a.pdf"), "w").close()
    open(os.path.join(d, "misc", "[CW-99UNS] b.pdf"), "w").close()
    rows = [
        {"rel": "a.pdf", "name": "a.pdf", "status": "done", "stream": "CW", "subject": "08DIG",
         "type": "notes", "conf": "high", "source": "text", "dst": "[CW-08DIG] a.pdf", "error": ""},
        {"rel": "b.pdf", "name": "b.pdf", "status": "done", "stream": "CW", "subject": "99UNS",
         "type": "misc", "conf": "low", "source": "vision", "dst": "misc/[CW-99UNS] b.pdf", "error": ""},
    ]
    with open(os.path.join(d, "_docsort_state.jsonl"), "w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    assert cli.report(d)
    assert os.path.exists(os.path.join(d, "DOCSORT-REPORT.md"))
    cli.undo(d)
    assert os.path.exists(os.path.join(d, "a.pdf"))       # rename reversed
    assert os.path.exists(os.path.join(d, "b.pdf"))       # misc move reversed


def test_apply_journal(tmp_path, monkeypatch):
    """--apply-journal replays a dry-run's recorded decisions as renames, with
    no model calls; files changed since the audit (mtime mismatch) are skipped."""
    monkeypatch.setenv("APPDATA", str(tmp_path))          # isolate the global index
    d = tmp_path / "run"; d.mkdir()
    f_ok = d / "a.pdf"; f_ok.write_text("x", encoding="utf-8")
    f_stale = d / "b.pdf"; f_stale.write_text("y", encoding="utf-8")
    f_unk = d / "c.pdf"; f_unk.write_text("z", encoding="utf-8")
    mt_ok = int(os.path.getmtime(f_ok))
    mt_unk = int(os.path.getmtime(f_unk))
    rows = [
        {"rel": "a.pdf", "name": "a.pdf", "mtime": mt_ok, "status": "done", "stream": "CW",
         "subject": "08DIG", "type": "notes", "conf": "high", "source": "text", "dst": "a.pdf", "error": ""},
        {"rel": "b.pdf", "name": "b.pdf", "mtime": 1, "status": "done", "stream": "CW",          # mtime mismatch
         "subject": "10CTRL", "type": "notes", "conf": "high", "source": "text", "dst": "b.pdf", "error": ""},
        {"rel": "c.pdf", "name": "c.pdf", "mtime": mt_unk, "status": "done", "stream": "CW",
         "subject": "99UNS", "type": "misc", "conf": "low", "source": "vision", "dst": "c.pdf", "error": ""},
    ]
    with open(d / "_docsort_state.jsonl", "w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r) + "\n")

    cli.apply_journal(str(d), misc=True, skip_unknown=False)

    assert (d / "[CW-08DIG] a.pdf").exists()              # applied from journal
    assert not (d / "a.pdf").exists()
    assert (d / "b.pdf").exists()                         # stale (mtime) -> untouched
    assert not (d / "[CW-10CTRL] b.pdf").exists()
    assert (d / "misc" / "[CW-99UNS] c.pdf").exists()     # 99UNS swept to misc (misc=True)


def test_classify_non_vision_uses_embed_only_no_model_call(tmp_path, monkeypatch):
    """Non-vision files: EMBED tier alone decides, zero model calls."""
    from docsort.cascade import build_centroids
    monkeypatch.setattr(cli, "STREAM_CENTROIDS",
                         build_centroids({"CW": "CW coursework degree material notes assignments lab"}))
    monkeypatch.setattr(cli, "SUBJECT_CENTROIDS",
                         build_centroids({"04BJT": "04BJT BJT bipolar biasing CE CB CC h-params transistor"}))

    def boom(*args, **kwargs):
        raise AssertionError("llm() must not be called for non-vision files")
    monkeypatch.setattr(cli, "llm", boom)

    f = tmp_path / "bjt_notes.txt"
    f.write_text("BJT bipolar transistor biasing CE CB CC lab assignment notes " * 3, encoding="utf-8")
    a = argparse.Namespace(vision=False, stream_threshold=0.05, subject_threshold=0.05, backend="local", frontier="none")

    st, su, ty, cf, src = cli.classify(a, "sysprompt", str(f), "bjt_notes.txt", "")
    assert su == "04BJT"
    assert src == "embed"


def test_classify_non_vision_low_confidence_marks_99uns_no_model_call(tmp_path, monkeypatch):
    """Below the EMBED confidence threshold -> 99UNS for review, still zero model calls."""
    from docsort.cascade import build_centroids
    monkeypatch.setattr(cli, "STREAM_CENTROIDS", build_centroids({"CW": "CW coursework"}))
    monkeypatch.setattr(cli, "SUBJECT_CENTROIDS", build_centroids({"04BJT": "04BJT bjt transistor"}))

    def boom(*args, **kwargs):
        raise AssertionError("llm() must not be called for non-vision files")
    monkeypatch.setattr(cli, "llm", boom)

    f = tmp_path / "random.txt"
    f.write_text("zzz qqq xkcd unrelated gibberish " * 3, encoding="utf-8")
    a = argparse.Namespace(vision=False, stream_threshold=0.99, subject_threshold=0.99, backend="local", frontier="none")

    st, su, ty, cf, src = cli.classify(a, "sysprompt", str(f), "random.txt", "")
    assert su == "99UNS"
    assert src == "embed-unsure"


def test_classify_keeps_confident_stream_when_subject_unsure(tmp_path, monkeypatch):
    """Real bug found in production: a confident STREAM guess was silently discarded and
    replaced with a hardcoded ("CW","99UNS") whenever SUBJECT alone missed its threshold --
    even when STREAM was clearly right. GATE-flavoured text with no clear EE subject must
    tag as GATE-99UNS (partial, still flagged for review), not CW-99UNS."""
    from docsort.cascade import build_centroids
    monkeypatch.setattr(cli, "STREAM_CENTROIDS", build_centroids({
        "CW": "CW coursework degree material notes assignments lab",
        "GATE": "GATE competitive exam prep syllabus formula book previous year questions",
    }))
    monkeypatch.setattr(cli, "SUBJECT_CENTROIDS", build_centroids({
        "04BJT": "04BJT bjt bipolar biasing CE CB CC h-params transistor",
    }))

    def boom(*args, **kwargs):
        raise AssertionError("llm() must not be called for non-vision files")
    monkeypatch.setattr(cli, "llm", boom)

    f = tmp_path / "gate_formula_book.txt"
    f.write_text("GATE EC formula book previous year questions exam prep syllabus", encoding="utf-8")
    a = argparse.Namespace(vision=False, stream_threshold=0.3, subject_threshold=0.45,
                           backend="local", frontier="none")

    st, su, ty, cf, src = cli.classify(a, "sysprompt", str(f), "gate_formula_book.txt", "")
    assert st == "GATE"       # the real, confident answer -- must survive
    assert su == "99UNS"      # subject genuinely unclear here, correctly flagged
    assert "partial" in src


def test_classify_vision_path_still_calls_model(tmp_path, monkeypatch):
    """Vision tier (scanned/handwritten, no extractable text) is the one exception —
    still model-based, per the "non-vision runs only" scope of the no-model change."""
    monkeypatch.setattr(cli, "STREAMS", {"CW"})
    monkeypatch.setattr(cli, "SUBJECTS", {"08DIG"})
    monkeypatch.setattr(cli, "TYPES", ["notes"])
    calls = []

    def fake_llm(a, backend, system, user_text, image_png=None):
        calls.append(image_png is not None)
        return "CW 08DIG notes HIGH"
    monkeypatch.setattr(cli, "llm", fake_llm)
    monkeypatch.setattr(cli, "page_png", lambda path, page=0, dpi=None: b"fakepng")
    monkeypatch.setattr(cli, "doc_text", lambda path, cap=2000: "")   # no extractable text -> vision path

    f = tmp_path / "scanned.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    a = argparse.Namespace(vision=True, stream_threshold=0.3, subject_threshold=0.45, backend="local", frontier="none")

    st, su, ty, cf, src = cli.classify(a, "sysprompt", str(f), "scanned.pdf", "")
    assert src == "vision"
    assert su == "08DIG"
    assert calls and calls[0] is True
