#!/usr/bin/env python3
"""
config — settings + file locations for docsort.

Works two ways with no user effort:
  * cloned repo (not installed) — bundled defaults read from docsort/data/.
  * pip-installed             — same defaults read from package data.

User-editable files (config.json, TAGS.md, system_prompt.md) live in a per-user
data dir (Windows: %APPDATA%\\docsort, else ~/.docsort) and are seeded from
the bundled templates on first use. So any machine works out of the box, and the
user edits their own tag lists without touching the install.

Precedence: CLI flag  >  user config.json  >  built-in DEFAULTS.
"""
from __future__ import annotations
import os, json, copy

APP = "docsort"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")          # bundled templates (packaged as package-data)

DEFAULTS = {
    "model": {
        "host": "localhost",               # which entry in "hosts" to call
        "model": "local-model",            # text model id in LM Studio (auto-resolves to a loaded VL model)
        "vision_model": "local-vision",    # vision model id (auto-resolves to a loaded VL model)
        "backend": "local",                # local
        "frontier": "none",                # none | claude | cmd  (hard-99UNS fallback; claude=haiku)
        "timeout": 180,
    },
    "hosts": {                             # name -> OpenAI-compatible chat/completions URL
        "localhost": "http://localhost:1234/v1/chat/completions",
    },
    "locations": {},                       # name -> {type: local|mount|ssh, path, note}
    "exclude": [],                         # folders to skip (path prefix / segment, relative to root or absolute)
    "include": [],                         # if non-empty, ONLY process these folders
    "folder_tags": {},                     # future: {folder: "STREAM-SUBJECT"} -> direct tag, no model
    "archive_root": "",                    # default destination for --move @archive
    "options": {
        "vision": True, "apply": False,
        "min_text": 80, "deep_pages": 5, "deep_cap": 4000, "dpi": 120,
        # Confidence cutoffs for the model-free EMBED classifier (0.0-1.0), one per axis.
        # Non-vision files are classified by EMBED alone, no model call — below either
        # cutoff the file is marked 99UNS for human review instead of escalating to an LLM.
        # Separate thresholds because the two axes score on different scales: STREAM
        # descriptions are short/generic (real scores ~0.2-0.7), SUBJECT descriptions are
        # technical/specific (real correct-match scores usually >0.7). See docsort/cascade.py.
        #
        # Known limitation: real testing (realistic filenames, not just long content samples)
        # found a hard precision/recall ceiling with this stdlib embedding -- there is no single
        # threshold pair that both accepts most real content AND rejects gibberish; the semantic
        # separation just isn't clean enough. These values (0.2/0.3) are chosen to eliminate
        # total-classification-failures (every file landing on a hardcoded 99UNS) at the cost of
        # occasionally tagging noise with unwarranted confidence -- the review/promote workflow
        # (--report/TAG-REVIEW.md) is the safety net for that, same as for ~LABEL proposals.
        # Retune against your own corpus; these are a considered starting point, not "the" answer.
        "stream_embed_threshold": 0.2,
        "subject_embed_threshold": 0.3,
    },
}

# ---------- file locations ----------
def user_dir():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"))
    d = os.path.join(base, APP)
    os.makedirs(d, exist_ok=True)
    return d

def _bundled(name):
    return os.path.join(DATA, name)

def user_file(name, seed_from=None):
    """Path to a user-editable file; seed it from the bundled template on first use."""
    p = os.path.join(user_dir(), name)
    if not os.path.exists(p):
        src = _bundled(seed_from or name)
        try:
            with open(src, encoding="utf-8") as f:
                data = f.read()
            with open(p, "w", encoding="utf-8") as f:
                f.write(data)
        except Exception:
            pass
    return p

def tags_path():    return user_file("TAGS.md")
def prompt_path():  return user_file("system_prompt.md")
def config_path():  return user_file("config.json", seed_from="config.example.json")

# ---------- config ----------
def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out

def load_config(path=None):
    cfg = copy.deepcopy(DEFAULTS)
    for p in (path, config_path()):
        if p and os.path.isfile(p):
            try:
                cfg = _merge(cfg, json.load(open(p, encoding="utf-8")))
            except Exception as e:
                print(f"[config] ignored {p}: {e}")
            break
    return cfg

def resolve_api(cfg, host=None):
    h = host or cfg["model"]["host"]
    if isinstance(h, str) and h.startswith("http"):
        return h                                   # host given as a raw URL
    return cfg["hosts"].get(h, DEFAULTS["hosts"]["localhost"])

def resolve_location(cfg, name):
    """Return a filesystem path for a named location (or treat name as a raw path)."""
    loc = cfg["locations"].get(name)
    if not loc:
        return name                                # not a named location -> raw path
    t = loc.get("type", "local")
    if t in ("local", "mount"):
        return loc["path"]                         # 'mount' must already be OS-mounted
    if t == "ssh":
        raise SystemExit(f"[config] location '{name}' is ssh — mount it first (see GUIDE).")
    return loc.get("path", name)

def arg_defaults(cfg):
    """(argparse defaults dict, globals dict) derived from config."""
    m, o = cfg["model"], cfg["options"]
    args = {
        "api": resolve_api(cfg), "model": m["model"], "vision_model": m["vision_model"],
        "backend": m["backend"], "frontier": m["frontier"],
        "vision": bool(o.get("vision", False)), "apply": bool(o.get("apply", False)),
        "stream_threshold": o.get("stream_embed_threshold", 0.2),
        "subject_threshold": o.get("subject_embed_threshold", 0.3),
    }
    glob = {"MIN_TEXT": o.get("min_text", 80), "DEEP_PAGES": o.get("deep_pages", 5),
            "DEEP_CAP": o.get("deep_cap", 4000), "DPI": o.get("dpi", 120)}
    return args, glob
