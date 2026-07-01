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


def test_classify_by_embed_returns_none_below_threshold():
    stream_c = build_centroids(STREAM_DESC)
    subject_c = build_centroids(SUBJECT_DESC)
    result = classify_by_embed("completely unrelated gibberish zzq xkcd", stream_c, subject_c, threshold=0.9)
    assert result is None


def test_classify_by_embed_matches_confident_text():
    stream_c = build_centroids(STREAM_DESC)
    subject_c = build_centroids(SUBJECT_DESC)
    result = classify_by_embed(
        "BJT transistor CE biasing lab assignment coursework notes",
        stream_c, subject_c, threshold=0.05,
    )
    assert result is not None
    stream, subject, stream_score, subject_score = result
    assert stream == "CW"
    assert subject == "04BJT"
    assert 0.0 <= stream_score <= 1.0
    assert 0.0 <= subject_score <= 1.0
