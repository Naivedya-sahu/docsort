"""UI-agnostic run core for docsort: parse the engine's stdout contract,
build the CLI command, and drive the run as a subprocess. No UI imports."""
from __future__ import annotations
import sys, subprocess, threading


def parse_progress(line):
    """Parse a 'PROGRESS i/N done= failed= tps= toks= eta=Es' line. None if not one."""
    parts = line.split()
    if not parts or parts[0] != "PROGRESS" or len(parts) < 2 or "/" not in parts[1]:
        return None
    try:
        i_s, n_s = parts[1].split("/")
        i, n = int(i_s), int(n_s)
    except ValueError:
        return None
    kv = dict(p.split("=", 1) for p in parts[2:] if "=" in p)
    pct = int(100 * i / n) if n else 0
    return {"i": i, "n": n, "pct": pct,
            "done": int(kv.get("done", 0) or 0), "failed": int(kv.get("failed", 0) or 0),
            "tps": kv.get("tps", ""), "toks": kv.get("toks", ""),
            "eta": kv.get("eta", "").rstrip("s")}


_MARKERS = {"->misc", "->skip", "FAIL"}


def parse_result_row(line, streams, subjects):
    """Parse a per-file result row into a dict, or None if the line isn't one.
    Recognised by: first token is a known STREAM and second a known SUBJECT."""
    toks = line.split()
    if len(toks) < 6:
        return None
    st, su, ty, cf, src = toks[0], toks[1], toks[2], toks[3], toks[4]
    if st not in streams or su not in subjects:
        return None
    rest = toks[5:]
    skipped = "->skip" in rest
    failed = "FAIL" in rest
    while rest and rest[-1] in _MARKERS:
        rest.pop()
    return {"stream": st, "subject": su, "type": ty, "conf": cf, "source": src,
            "name": " ".join(rest), "tag": f"[{st}-{su}]", "skipped": skipped,
            "failed": failed}


def build_run_cmd(opts, python=None, folder=None):
    """Build the `python -m docsort.cli <folder> ...` command from UI options.
    Mirrors the existing gui.run() flag mapping exactly. `misc` defaults ON."""
    cmd = [python or sys.executable, "-m", "docsort.cli", folder]
    if opts.get("host"):
        cmd += ["--host", opts["host"]]
    model = opts.get("model", "auto")
    if model and model != "auto":
        cmd += ["--model", model, "--vision-model", model]
    if opts.get("vision"):
        cmd.append("--vision")
    if opts.get("apply"):
        cmd.append("--apply")
    if opts.get("copy"):
        cmd.append("--copy")
    if not opts.get("misc", True):
        cmd.append("--no-misc")
    if opts.get("skip_unknown"):
        cmd.append("--skip-unknown")
    fr = opts.get("frontier", "none")
    if fr and fr != "none":
        cmd += ["--frontier", fr]
    return cmd
