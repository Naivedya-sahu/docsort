from docsort.embed import embed_text, classify_by_centroid


def build_centroids(label_descriptions):
    """label_descriptions: {code: description_text} (e.g. from TAGS.md via load_tags()).
    Zero-shot — one description per label is the centroid seed, no example files needed."""
    return {code: embed_text(desc) for code, desc in label_descriptions.items()}


def classify_by_embed(text, stream_centroids, subject_centroids, threshold):
    """Returns (stream, subject, stream_score, subject_score) if BOTH axes clear threshold,
    else None (caller falls through to the existing TEXT tier)."""
    vec = embed_text(text)
    stream, stream_score = classify_by_centroid(vec, stream_centroids)
    subject, subject_score = classify_by_centroid(vec, subject_centroids)
    if stream_score < threshold or subject_score < threshold:
        return None
    return stream, subject, stream_score, subject_score
