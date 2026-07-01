import os

from docsort.embed import embed_text as _stdlib_embed_text, classify_by_centroid


class NameEmbedder:
    """Embeds short strings (file/folder names) for the recon pass. Uses a real
    GPU-capable sentence-transformer model when the `recon` extra is installed
    (device auto-selected: CUDA if available, else CPU), falling back to the
    stdlib hashing-trick embedder (the same one classify()'s EMBED tier uses)
    otherwise. Recon always works — the extra only makes it faster/more accurate,
    it is never required."""

    def __init__(self, model_name="all-MiniLM-L6-v2", device=None):
        self._model = None
        self._model_name = model_name
        self._device = device

    def _load(self):
        if self._model is not None:
            return
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError:
            self._model = False   # sentinel: fall back to the stdlib embedder
            return
        device = self._device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._model = SentenceTransformer(self._model_name, device=device)

    def embed(self, text):
        self._load()
        if self._model is False:
            return _stdlib_embed_text(text)
        return tuple(self._model.encode(text).tolist())

    @property
    def backend(self):
        self._load()
        return "stdlib" if self._model is False else "sentence-transformers"


def recon_scan(root):
    """Walk root; collect every file AND folder name. No content is ever read —
    recon is a name-only, whole-tree pre-pass, distinct from the per-file
    Scan/Clean/Classify pipeline."""
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames:
            entries.append({"path": os.path.join(dirpath, name), "name": name, "is_dir": True})
        for name in filenames:
            if name.lower().startswith("_docsort"):
                continue
            entries.append({"path": os.path.join(dirpath, name), "name": name, "is_dir": False})
    return entries


def classify_names(entries, stream_centroids, subject_centroids, embedder):
    """High-level classification suggestion for every entry, from its name alone."""
    results = []
    for entry in entries:
        vec = embedder.embed(entry["name"])
        stream, stream_score = classify_by_centroid(vec, stream_centroids)
        subject, subject_score = classify_by_centroid(vec, subject_centroids)
        results.append({
            **entry,
            "stream": stream, "stream_score": stream_score,
            "subject": subject, "subject_score": subject_score,
        })
    return results
