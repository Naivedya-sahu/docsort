from docsort.cascade import build_centroids, classify_by_embed

STREAM_DESC = {
    "CW": "CW coursework / college degree material (BTech notes, assignments, lab)",
    "REC": "REC records / admin marksheet admit card certificate ID exam form fee receipt",
}
SUBJECT_DESC = {
    "04BJT": "04BJT BJT bipolar biasing CE CB CC h-params",
    "09SNS": "09SNS Signals Systems DSP fourier laplace z-transform convolution sampling",
}


def test_build_centroids_returns_one_vector_per_label():
    centroids = build_centroids(STREAM_DESC)
    assert set(centroids.keys()) == {"CW", "REC"}


def test_classify_by_embed_returns_none_below_either_threshold():
    stream_c = build_centroids(STREAM_DESC)
    subject_c = build_centroids(SUBJECT_DESC)
    result = classify_by_embed("completely unrelated gibberish zzq xkcd", stream_c, subject_c,
                                stream_threshold=0.9, subject_threshold=0.9)
    assert result is None


def test_classify_by_embed_matches_confident_text():
    stream_c = build_centroids(STREAM_DESC)
    subject_c = build_centroids(SUBJECT_DESC)
    result = classify_by_embed(
        "BJT transistor CE biasing lab assignment coursework notes",
        stream_c, subject_c, stream_threshold=0.05, subject_threshold=0.05,
    )
    assert result is not None
    stream, subject, stream_score, subject_score = result
    assert stream == "CW"
    assert subject == "04BJT"
    assert 0.0 <= stream_score <= 1.0
    assert 0.0 <= subject_score <= 1.0


def test_classify_by_embed_independent_axis_thresholds():
    """Real TAGS.md-scale evidence: a strong SUBJECT match (BJT-specific terms) often
    comes with a weak STREAM match (STREAM descriptions are generic wording) and vice
    versa. Independent per-axis thresholds must let a strong-one/weak-other case through
    when each axis clears its OWN bar, not a shared one."""
    stream_c = build_centroids(STREAM_DESC)
    subject_c = build_centroids(SUBJECT_DESC)
    # Strong SUBJECT (BJT jargon), weak-but-still-real STREAM signal.
    text = "BJT bipolar transistor biasing CE CB CC h-params amplifier lab report"
    result = classify_by_embed(text, stream_c, subject_c, stream_threshold=0.05, subject_threshold=0.5)
    assert result is not None
    stream, subject, stream_score, subject_score = result
    assert subject == "04BJT"
    assert subject_score > stream_score   # the asymmetry this test exists to catch
