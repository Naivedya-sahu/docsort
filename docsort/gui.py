#!/usr/bin/env python3
"""
docsort.gui — modern dark Tkinter front-end.

Pick a folder, set toggles, hit Run. The classifier runs as a subprocess
(`python -m docsort.cli ...`) using the same interpreter, so it inherits the
environment that launched the GUI (e.g. the project .venv with pymupdf). Output
streams live into the dark log pane. An in-app editor lets you edit the tag lists.

  docsort-gui          (or: run.bat gui)
Tkinter ships with standard CPython on Windows; no extra install.
"""
from __future__ import annotations
import os, sys, time, subprocess, threading, queue
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    from . import config
    from .cli import available_models
except ImportError:
    import config  # loose-script fallback
    from cli import available_models

# repo root / site-packages dir that contains the docsort package — so `-m docsort.cli` resolves
PKG_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- dark palette ----
BG      = "#1b1b27"
PANEL   = "#232334"
PANEL2  = "#2a2a3d"
FG      = "#e6e6ef"
MUTED   = "#9aa0b4"
ACCENT  = "#7c5cff"
ACCENT2 = "#5b8cff"
OK      = "#3ddc84"
ENTRY   = "#15151f"
FONT    = ("Segoe UI", 10)
FONT_B  = ("Segoe UI Semibold", 11)
MONO    = ("Consolas", 9)


class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.proc = None
        self._cfg = config.load_config()
        root.title("docsort")
        root.geometry("820x600")
        root.configure(bg=BG)
        root.minsize(640, 480)

        # --- header ---
        head = tk.Frame(root, bg=BG)
        head.pack(fill="x", padx=18, pady=(16, 6))
        tk.Label(head, text="docsort", bg=BG, fg=FG, font=("Segoe UI Semibold", 18)).pack(side="left")
        tk.Label(head, text="local-LLM document tagger", bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=10, pady=(8, 0))

        # --- folder card ---
        card = self._card(root)
        row = tk.Frame(card, bg=PANEL); row.pack(fill="x", padx=14, pady=12)
        tk.Label(row, text="Folder", bg=PANEL, fg=MUTED, font=FONT, width=7, anchor="w").pack(side="left")
        self.folder = tk.StringVar()
        ent = tk.Entry(row, textvariable=self.folder, bg=ENTRY, fg=FG, insertbackground=FG,
                       relief="flat", font=FONT, highlightthickness=1, highlightbackground=PANEL2,
                       highlightcolor=ACCENT)
        ent.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self._btn(row, "Browse", self.browse, accent=False).pack(side="left")

        # --- options card ---
        opt = self._card(root)
        self.copy   = tk.BooleanVar(value=True)
        self.misc   = tk.BooleanVar(value=True)
        self.vision = tk.BooleanVar(value=True)
        self.apply  = tk.BooleanVar(value=False)
        self.frontier = tk.StringVar(value="none")
        self.host   = tk.StringVar(value=config.resolve_api(self._cfg))
        self.model  = tk.StringVar(value="auto")

        g0 = tk.Frame(opt, bg=PANEL); g0.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(g0, text="Host", bg=PANEL, fg=MUTED, font=FONT).pack(side="left")
        tk.Entry(g0, textvariable=self.host, bg=ENTRY, fg=FG, insertbackground=FG, relief="flat",
                 font=FONT, width=40, highlightthickness=1, highlightbackground=PANEL2,
                 highlightcolor=ACCENT).pack(side="left", ipady=3, padx=6)
        tk.Label(g0, text="Model", bg=PANEL, fg=MUTED, font=FONT).pack(side="left", padx=(10, 0))
        self.model_om = tk.OptionMenu(g0, self.model, "auto")
        self.model_om.configure(bg=PANEL2, fg=FG, activebackground=ACCENT, activeforeground="#fff",
                                relief="flat", highlightthickness=0, font=FONT, width=22)
        self.model_om["menu"].configure(bg=PANEL2, fg=FG, activebackground=ACCENT, activeforeground="#fff")
        self.model_om.pack(side="left", padx=6)
        self._btn(g0, "List models", self.refresh_models, accent=False).pack(side="left")

        g1 = tk.Frame(opt, bg=PANEL); g1.pack(fill="x", padx=14, pady=4)
        self._check(g1, "Create copy folder (originals untouched)", self.copy).pack(side="left", padx=(0, 18))
        self._check(g1, "Move 99UNS -> misc subfolder", self.misc).pack(side="left")

        g2 = tk.Frame(opt, bg=PANEL); g2.pack(fill="x", padx=14, pady=4)
        self._check(g2, "Vision model for no-text PDFs", self.vision).pack(side="left", padx=(0, 18))
        self._check(g2, "Apply (rename for real)", self.apply).pack(side="left")

        g3 = tk.Frame(opt, bg=PANEL); g3.pack(fill="x", padx=14, pady=(4, 12))
        tk.Label(g3, text="Frontier on hard 99UNS", bg=PANEL, fg=MUTED, font=FONT).pack(side="left")
        om = tk.OptionMenu(g3, self.frontier, "none", "claude")
        om.configure(bg=PANEL2, fg=FG, activebackground=ACCENT, activeforeground="#fff",
                     relief="flat", highlightthickness=0, font=FONT, width=8)
        om["menu"].configure(bg=PANEL2, fg=FG, activebackground=ACCENT, activeforeground="#fff")
        om.pack(side="left", padx=8)
        tk.Label(g3, text="claude = haiku, uses your Claude subscription", bg=PANEL, fg=MUTED, font=FONT).pack(side="left")

        # --- action buttons ---
        bar = tk.Frame(root, bg=BG); bar.pack(fill="x", padx=18, pady=(10, 6))
        self.run_btn = self._btn(bar, "Run", self.run, accent=True)
        self.run_btn.pack(side="left")
        self.stop_btn = self._btn(bar, "Stop", self.stop, accent=False)
        self.stop_btn.configure(state="disabled"); self.stop_btn.pack(side="left", padx=8)
        self._btn(bar, "Edit Tags", self.edit_tags, accent=False).pack(side="left", padx=8)
        self._btn(bar, "Clear log", lambda: self.log_box.delete("1.0", "end"), accent=False).pack(side="left")
        self.status = tk.Label(bar, text="idle", bg=BG, fg=MUTED, font=FONT)
        self.status.pack(side="right")

        # --- progress + live stats strip ---
        st = self._card(root)
        self.pbar = tk.Canvas(st, height=16, bg=PANEL2, highlightthickness=0, bd=0)
        self.pbar.pack(fill="x", padx=14, pady=(12, 4))
        self.pbar_fill = self.pbar.create_rectangle(0, 0, 0, 16, fill=ACCENT, width=0)
        self.var_prog = tk.StringVar(value="0 / 0  0%")
        self.var_tps  = tk.StringVar(value="— tok/s")
        self.var_toks = tk.StringVar(value="0 tok")
        self.var_df   = tk.StringVar(value="done 0 / fail 0")
        self.var_el   = tk.StringVar(value="0s")
        self.var_eta  = tk.StringVar(value="~—")
        srow = tk.Frame(st, bg=PANEL); srow.pack(fill="x", padx=14, pady=(0, 12))
        for v, w in ((self.var_prog, 12), (self.var_tps, 12), (self.var_toks, 12),
                     (self.var_df, 16), (self.var_el, 8), (self.var_eta, 8)):
            tk.Label(srow, textvariable=v, bg=PANEL, fg=MUTED, font=FONT, width=w, anchor="w").pack(side="left")
        self._run_t0 = 0.0

        # --- log pane ---
        logwrap = tk.Frame(root, bg=PANEL2, bd=0); logwrap.pack(fill="both", expand=True, padx=18, pady=(6, 16))
        self.log_box = tk.Text(logwrap, wrap="none", bg=ENTRY, fg="#d6d6e0", insertbackground=FG,
                               relief="flat", font=MONO, padx=10, pady=8, bd=0)
        sb = tk.Scrollbar(logwrap, command=self.log_box.yview, bg=PANEL2, troughcolor=ENTRY, bd=0)
        self.log_box.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); self.log_box.pack(side="left", fill="both", expand=True)

        self.root.after(100, self.drain)
        self.root.after(400, self.refresh_models)   # pre-fill the model list from the configured host

    # ---- styled-widget helpers ----
    def _card(self, parent):
        c = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=PANEL2)
        c.pack(fill="x", padx=18, pady=6)
        return c

    def _check(self, parent, text, var):
        return tk.Checkbutton(parent, text=text, variable=var, bg=PANEL, fg=FG, font=FONT,
                              selectcolor=ENTRY, activebackground=PANEL, activeforeground=FG,
                              highlightthickness=0, anchor="w", takefocus=0)

    def _btn(self, parent, text, cmd, accent=False):
        b = tk.Button(parent, text=text, command=cmd, font=FONT_B if accent else FONT,
                      bg=ACCENT if accent else PANEL2, fg="#ffffff" if accent else FG,
                      activebackground=ACCENT2 if accent else PANEL, activeforeground="#fff",
                      relief="flat", bd=0, padx=18 if accent else 12, pady=6, cursor="hand2")
        return b

    # ---- actions ----
    def browse(self):
        d = filedialog.askdirectory(title="Select folder to tag")
        if d: self.folder.set(d)

    def refresh_models(self):
        host = self.host.get().strip()
        self.status.config(text="listing models...", fg=ACCENT2)
        def work():
            try: ms = available_models(host)
            except Exception: ms = []
            self.q.put(("__models__", ms))
        threading.Thread(target=work, daemon=True).start()

    def _populate_models(self, ms):
        opts = ["auto"] + list(ms or [])
        menu = self.model_om["menu"]; menu.delete(0, "end")
        for o in opts:
            menu.add_command(label=o, command=tk._setit(self.model, o))
        if self.model.get() not in opts: self.model.set("auto")
        n = len(ms or [])
        self.status.config(text=f"{n} model(s) loaded" if n else "no models / host down", fg=OK if n else MUTED)
        self.log("[gui] models @ %s -> %s\n" % (self.host.get(), ", ".join(ms) if ms else "(none — is LM Studio up?)"))

    def log(self, line):
        self.log_box.insert("end", line); self.log_box.see("end")

    def run(self):
        if self.proc: return
        folder = self.folder.get().strip()
        if not os.path.isdir(folder):
            self.log("[gui] not a folder: %r\n" % folder); return
        cmd = [sys.executable, "-m", "docsort.cli", folder]
        host = self.host.get().strip()
        if host:                          cmd += ["--host", host]
        if self.model.get() != "auto":    cmd += ["--model", self.model.get(), "--vision-model", self.model.get()]
        if self.vision.get():             cmd.append("--vision")
        if self.apply.get():              cmd.append("--apply")
        if self.copy.get():               cmd.append("--copy")
        if not self.misc.get():           cmd.append("--no-misc")     # engine default is ON
        if self.frontier.get() != "none": cmd += ["--frontier", self.frontier.get()]
        self.log("[gui] $ %s\n" % " ".join(cmd[2:]))
        self._run_t0 = time.time()
        self.var_prog.set("0 / 0  0%"); self.var_tps.set("— tok/s"); self.var_toks.set("0 tok")
        self.var_df.set("done 0 / fail 0"); self.var_eta.set("~—")
        self.pbar.coords(self.pbar_fill, 0, 0, 0, 16)
        self.run_btn.config(state="disabled"); self.stop_btn.config(state="normal")
        self.status.config(text="running...", fg=ACCENT2)
        threading.Thread(target=self._worker, args=(cmd,), daemon=True).start()

    def stop(self):
        if self.proc:
            try: self.proc.terminate()
            except Exception: pass
            self.status.config(text="stopping...", fg=MUTED)

    def _set_progress(self, s):
        try:
            parts = s.split()
            i, N = parts[1].split("/"); i, N = int(i), int(N)
            kv = dict(p.split("=") for p in parts[2:] if "=" in p)
            pct = int(100 * i / N) if N else 0
            w = self.pbar.winfo_width() or 1
            self.pbar.coords(self.pbar_fill, 0, 0, w * pct / 100, 16)
            self.var_prog.set(f"{i} / {N}  {pct}%")
            self.var_tps.set(f"{kv.get('tps','—')} tok/s")
            self.var_toks.set(f"{kv.get('toks','0')} tok")
            self.var_df.set(f"done {kv.get('done','0')} / fail {kv.get('failed','0')}")
            self.var_eta.set("~" + kv.get("eta", "—"))
        except Exception:
            pass

    def _worker(self, cmd):
        try:
            self.proc = subprocess.Popen(cmd, cwd=PKG_PARENT, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in self.proc.stdout:
                if "MuPDF error" in line:    # benign render warnings -> drop
                    continue
                if line.startswith("PROGRESS "):
                    self.q.put(("__progress__", line.strip()))
                else:
                    self.q.put(line)
            self.proc.wait()
        except Exception as e:
            self.q.put("[gui] error: %s\n" % e)
        finally:
            self.q.put(None)

    def drain(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item is None:
                    self.proc = None
                    self.run_btn.config(state="normal"); self.stop_btn.config(state="disabled")
                    self.status.config(text="done", fg=OK)
                elif isinstance(item, tuple) and item[0] == "__models__":
                    self._populate_models(item[1])
                elif isinstance(item, tuple) and item[0] == "__progress__":
                    self._set_progress(item[1])
                else:
                    self.log(item)
        except queue.Empty:
            pass
        if self.proc and self._run_t0:                  # live elapsed clock while running
            self.var_el.set(f"{int(time.time() - self._run_t0)}s")
        self.root.after(100, self.drain)

    # ---- in-app tag editor ----
    def edit_tags(self):
        path = config.tags_path()
        try:
            text = open(path, encoding="utf-8").read()
        except Exception as e:
            messagebox.showerror("Edit Tags", f"Could not read {path}\n{e}"); return
        win = tk.Toplevel(self.root); win.title("Edit Tags  -  TAGS.md"); win.configure(bg=BG)
        win.geometry("720x600")
        tk.Label(win, text=path, bg=BG, fg=MUTED, font=FONT).pack(fill="x", padx=14, pady=(12, 4), anchor="w")
        wrap = tk.Frame(win, bg=PANEL2); wrap.pack(fill="both", expand=True, padx=14, pady=4)
        txt = tk.Text(wrap, wrap="none", bg=ENTRY, fg=FG, insertbackground=FG, relief="flat",
                      font=MONO, padx=10, pady=8, bd=0, undo=True)
        sb = tk.Scrollbar(wrap, command=txt.yview, bg=PANEL2, troughcolor=ENTRY, bd=0)
        txt.configure(yscrollcommand=sb.set); sb.pack(side="right", fill="y"); txt.pack(side="left", fill="both", expand=True)
        txt.insert("1.0", text)
        bar = tk.Frame(win, bg=BG); bar.pack(fill="x", padx=14, pady=10)

        def save():
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(txt.get("1.0", "end-1c"))
                self.status.config(text="tags saved", fg=OK); win.destroy()
            except Exception as e:
                messagebox.showerror("Edit Tags", f"Save failed\n{e}")

        self._btn(bar, "Save", save, accent=True).pack(side="left")
        self._btn(bar, "Cancel", win.destroy, accent=False).pack(side="left", padx=8)
        tk.Label(bar, text="codes = first token per line inside ```tags blocks", bg=BG, fg=MUTED, font=FONT).pack(side="right")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
