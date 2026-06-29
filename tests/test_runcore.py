from docsort import runcore


def test_parse_progress_basic():
    d = runcore.parse_progress("PROGRESS 34/50 done=33 failed=1 tps=41 toks=1234 eta=26s")
    assert d == {"i": 34, "n": 50, "pct": 68, "done": 33, "failed": 1,
                 "tps": "41", "toks": "1234", "eta": "26"}


def test_parse_progress_zero_total():
    d = runcore.parse_progress("PROGRESS 0/0 done=0 failed=0 tps=0 toks=0 eta=0s")
    assert d["pct"] == 0 and d["n"] == 0


def test_parse_progress_rejects_other_lines():
    assert runcore.parse_progress("[model] 'x' not loaded -> 'y'") is None
    assert runcore.parse_progress("CW 08DIG notes high text a.pdf") is None


STREAMS = {"CW", "GATE", "PROJ", "RES", "REC", "REF"}
SUBJECTS = {"08DIG", "10CTRL", "99UNS", "NA"}


def test_parse_result_row_basic():
    line = "CW   08DIG  notes     high text          control_bode_notes.pdf"
    r = runcore.parse_result_row(line, STREAMS, SUBJECTS)
    assert r["stream"] == "CW" and r["subject"] == "08DIG"
    assert r["type"] == "notes" and r["conf"] == "high" and r["source"] == "text"
    assert r["name"] == "control_bode_notes.pdf"
    assert r["tag"] == "[CW-08DIG]" and r["skipped"] is False


def test_parse_result_row_strips_markers():
    line = "GATE 99UNS  pyq       high text          gate_2024_ec_paper.pdf  ->skip"
    r = runcore.parse_result_row(line, STREAMS, SUBJECTS)
    assert r["name"] == "gate_2024_ec_paper.pdf" and r["skipped"] is True


def test_parse_result_row_rejects_non_rows():
    assert runcore.parse_result_row("PROGRESS 1/2 done=1 failed=0", STREAMS, SUBJECTS) is None
    assert runcore.parse_result_row("[model] note", STREAMS, SUBJECTS) is None
    assert runcore.parse_result_row("ZZ 08DIG notes high text x.pdf", STREAMS, SUBJECTS) is None


def test_build_run_cmd_defaults():
    cmd = runcore.build_run_cmd({}, python="PY", folder="F")
    assert cmd == ["PY", "-m", "docsort.cli", "F"]


def test_build_run_cmd_all_toggles():
    opts = {"host": "HOME", "model": "qwen", "vision": True, "apply": True,
            "copy": True, "misc": False, "skip_unknown": True, "frontier": "claude"}
    cmd = runcore.build_run_cmd(opts, python="PY", folder="F")
    assert cmd == ["PY", "-m", "docsort.cli", "F",
                   "--host", "HOME", "--model", "qwen", "--vision-model", "qwen",
                   "--vision", "--apply", "--copy", "--no-misc",
                   "--skip-unknown", "--frontier", "claude"]


def test_build_run_cmd_model_auto_and_misc_default():
    cmd = runcore.build_run_cmd({"model": "auto", "misc": True}, python="PY", folder="F")
    assert "--model" not in cmd and "--no-misc" not in cmd
