from docsort.cascade import build_centroids, classify_by_embed

STREAM_DESC = {
    "CW": "CW coursework / college degree material (BTech notes, assignments, lab)",
    "GATE": "GATE competitive exam prep syllabus formula book previous year questions",
    "REC": "REC records / admin marksheet admit card certificate ID exam form fee receipt",
}
SUBJECT_DESC = {
    "04BJT": "04BJT BJT bipolar biasing CE CB CC h-params",
    "09SNS": "09SNS Signals Systems DSP fourier laplace z-transform convolution sampling",
    "10CTRL": "10CTRL control systems transfer function bode root locus state space",
}


def test_build_centroids_returns_one_vector_per_label():
    centroids = build_centroids(STREAM_DESC)
    assert set(centroids.keys()) == {"CW", "GATE", "REC"}


def test_classify_by_embed_neither_axis_confident(tmp_path=None):
    stream_c = build_centroids(STREAM_DESC)
    subject_c = build_centroids(SUBJECT_DESC)
    stream, subject, s_score, su_score, s_ok, su_ok = classify_by_embed(
        "completely unrelated gibberish zzq xkcd", stream_c, subject_c,
        stream_threshold=0.9, subject_threshold=0.9,
    )
    assert s_ok is False
    assert su_ok is False


def test_classify_by_embed_matches_confident_text():
    stream_c = build_centroids(STREAM_DESC)
    subject_c = build_centroids(SUBJECT_DESC)
    stream, subject, s_score, su_score, s_ok, su_ok = classify_by_embed(
        "BJT transistor CE biasing lab assignment coursework notes",
        stream_c, subject_c, stream_threshold=0.05, subject_threshold=0.05,
    )
    assert s_ok and su_ok
    assert stream == "CW"
    assert subject == "04BJT"
    assert 0.0 <= s_score <= 1.0
    assert 0.0 <= su_score <= 1.0


def test_classify_by_embed_independent_axis_thresholds():
    """Real TAGS.md-scale evidence: a strong SUBJECT match (BJT-specific terms) often
    comes with a weak STREAM match (STREAM descriptions are generic wording) and vice
    versa. Independent per-axis thresholds must let a strong-one/weak-other case through
    when each axis clears its OWN bar, not a shared one."""
    stream_c = build_centroids(STREAM_DESC)
    subject_c = build_centroids(SUBJECT_DESC)
    text = "BJT bipolar transistor biasing CE CB CC h-params amplifier lab report"
    stream, subject, s_score, su_score, s_ok, su_ok = classify_by_embed(
        text, stream_c, subject_c, stream_threshold=0.05, subject_threshold=0.5,
    )
    assert su_ok
    assert subject == "04BJT"
    assert su_score > s_score   # the asymmetry this test exists to catch


def test_classify_by_embed_never_discards_a_confident_axis():
    """The actual bug: a real-world run found a confident STREAM guess (score above its
    threshold) getting silently discarded whenever SUBJECT alone missed its bar, with the
    caller falling back to a hardcoded ("CW", "99UNS") regardless of what STREAM correctly
    found. classify_by_embed must report each axis's own confidence independently, never
    an all-or-nothing None -- the caller decides what to do with a per-axis miss, but the
    confident axis's real value must survive."""
    stream_c = build_centroids(STREAM_DESC)
    subject_c = build_centroids(SUBJECT_DESC)
    # GATE-flavoured text with no clear subject -- mirrors "GATE_EC_Formula_Book.pdf" from
    # the real reproduction: stream confidently GATE, subject nowhere near confident.
    text = "GATE EC formula book previous year questions exam prep syllabus"
    stream, subject, s_score, su_score, s_ok, su_ok = classify_by_embed(
        text, stream_c, subject_c, stream_threshold=0.3, subject_threshold=0.45,
    )
    assert s_ok is True
    assert stream == "GATE"          # the real, confident answer -- must not be thrown away
    assert su_ok is False            # subject genuinely isn't confident here, that's fine
