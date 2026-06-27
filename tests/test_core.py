"""Pure-logic tests for docsort — no model, no network."""
import os, json
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
    pytest.importorskip("tkinter")
    from docsort.gui import App
    txt = open(config._bundled("TAGS.md"), encoding="utf-8").read()
    subs = App._tag_block(txt, "SUBJECTS")
    subs.append("93TEST  a new subject")
    new = App._replace_block(txt, "SUBJECTS", subs)
    _, su, _ = cli.load_tags(_tmp(new, tmp_path))
    assert "93TEST" in su


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
