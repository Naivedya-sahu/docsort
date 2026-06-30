"""UI-agnostic run core for docsort: parse the engine's stdout contract,
build the CLI command, and drive the run as a subprocess. No UI imports."""
from __future__ import annotations
import os, sys, subprocess, threading

# On Windows, a windowed (no-console) app spawning a child process pops a console
# window unless this flag is set. No-op on other platforms.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


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


def cli_prefix(python=None):
    """Argv prefix that invokes the docsort CLI engine.

    From source: ``python -m docsort.cli``. When frozen (the packaged GUI exe),
    ``sys.executable`` is the GUI exe itself and ``-m`` is ignored, so we re-invoke
    the same exe with a ``--run-cli`` sentinel that run_gui.py routes to cli.main."""
    exe = python or sys.executable
    if getattr(sys, "frozen", False):
        return [exe, "--run-cli"]
    return [exe, "-m", "docsort.cli"]


def build_run_cmd(opts, python=None, folder=None):
    """Build the docsort CLI command from UI options. Mirrors gui.run()'s flag
    mapping exactly. `misc` defaults ON."""
    cmd = cli_prefix(python) + [folder]
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


class RunController:
    """Runs the docsort CLI as a subprocess in a background thread and emits
    typed events to `on_event`: ('progress', dict) | ('file', dict) |
    ('log', str) | ('done', None). Thread-safe stop via terminate()."""

    def __init__(self, streams, subjects, on_event):
        self.streams = set(streams)
        self.subjects = set(subjects)
        self.on_event = on_event
        self.proc = None
        self._thread = None

    def start(self, cmd, cwd):
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, args=(cmd, cwd), daemon=True)
        self._thread.start()

    def _run(self, cmd, cwd):
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, creationflags=_NO_WINDOW)
            for line in self.proc.stdout:
                if "MuPDF error" in line:
                    continue
                s = line.rstrip("\n")
                prog = parse_progress(s)
                if prog is not None:
                    self.on_event(("progress", prog)); continue
                row = parse_result_row(s, self.streams, self.subjects)
                if row is not None:
                    self.on_event(("file", row)); continue
                self.on_event(("log", s))
            self.proc.wait()
        except Exception as e:
            self.on_event(("log", f"[gui] error: {e}\n"))
        finally:
            self.proc = None
            self.on_event(("done", None))

    def stop(self):
        p = self.proc
        if p:
            try:
                p.terminate()
            except Exception:
                pass

    @property
    def running(self):
        return self.proc is not None
