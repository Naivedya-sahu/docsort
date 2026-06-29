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
