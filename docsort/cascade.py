from docsort.embed import embed_text, classify_by_centroid


def build_centroids(label_descriptions):
    """label_descriptions: {code: description_text} (e.g. from TAGS.md via load_tags()).
    Zero-shot — one description per label is the centroid seed, no example files needed."""
    return {code: embed_text(desc) for code, desc in label_descriptions.items()}


def classify_by_embed(text, stream_centroids, subject_centroids, stream_threshold, subject_threshold):
    """Returns (stream, subject, stream_score, subject_score, stream_confident, subject_confident)
    -- always, never an all-or-nothing None. Each axis's own guess and confidence are
    reported independently; a real, confident answer on one axis must never be discarded
    just because the other axis missed its bar (a real bug: a caller that only accepted a
    joint AND of both axes was silently replacing a confident STREAM guess with a hardcoded
    default whenever SUBJECT alone was unsure).

    Independent per-axis thresholds, not a shared one: STREAM descriptions are short and
    generic (real STREAM scores run ~0.2-0.7), SUBJECT descriptions are technical and
    specific (real SUBJECT scores run ~0.2-0.8 with correct matches usually >0.7) — a
    shared threshold systematically rejects one axis or over-admits the other."""
    vec = embed_text(text)
    stream, stream_score = classify_by_centroid(vec, stream_centroids)
    subject, subject_score = classify_by_centroid(vec, subject_centroids)
    return (stream, subject, stream_score, subject_score,
            stream_score >= stream_threshold, subject_score >= subject_threshold)
