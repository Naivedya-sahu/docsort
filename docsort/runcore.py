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
