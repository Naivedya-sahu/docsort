#!/usr/bin/env python3
"""
Doc-handler TUI — animated terminal front-end (Rich).

A keyboard-driven menu over the same engine as doc_handler.py: tag (dry/apply),
move, and a live progress view with unicode spinners and per-subject bars.

  pip install rich
  python tui.py
"""
from __future__ import annotations
import os, sys
from types import SimpleNamespace
from collections import Counter
import doc_handler as dh

# Windows cmd.exe: enable ANSI/VT (Win10+) and UTF-8 stdout. Output is kept ASCII-safe
# below (no emoji, ascii box + spinner + bars) so it renders even on legacy codepages.
os.system("")  # turns on VT processing in cmd.exe
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

try:
    from rich.console import Console
    from rich import box
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    from rich.prompt import Prompt, Confirm
    from rich.live import Live
except Exception:
    raise SystemExit("Rich not installed. Run: pip install rich")

C=Console()                      # auto-detect terminal (legacy cmd vs Windows Terminal)
BOX=box.ASCII                    # +-| borders render on any Windows codepage
BANNER="[bold cyan]DOC-HANDLER[/]  [dim]local-LLM document tagger[/]"

def defaults(root, config=None, **kw):
    from config import load_config, arg_defaults
    cfg=load_config(config); ad,glb=arg_defaults(cfg)
    dh.MIN_TEXT,dh.DEEP_PAGES,dh.DEEP_CAP,dh.DPI=glb["MIN_TEXT"],glb["DEEP_PAGES"],glb["DEEP_CAP"],glb["DPI"]
    a=SimpleNamespace(root=root,
        tags=os.path.join(dh.HERE,"TAGS.md"), prompt=os.path.join(dh.HERE,"system_prompt.md"),
        move=None, log=None, **ad)
    a.__dict__.update(kw); return a

def bars(counts, total):
    tb=Table(show_header=True, header_style="bold magenta", expand=True, box=BOX)
    tb.add_column("subject"); tb.add_column("n", justify="right"); tb.add_column("", ratio=1)
    for code,n in counts.most_common():
        w=int(28*n/max(total,1)); tb.add_row(code, str(n), "[green]"+"#"*w+"[/]")
    return tb

def run_tag(a):
    sysp=dh.setup(a)
    targets=list(dh.iter_targets(a.root))
    if not targets:
        C.print("[yellow]No untagged documents found.[/]"); return
    counts=Counter(); rows=[]; conf_low=0
    prog=Progress(SpinnerColumn(spinner_name="line"),
                  TextColumn("[progress.description]{task.description}"),
                  BarColumn(), TextColumn("{task.completed}/{task.total}"),
                  TimeElapsedColumn(), console=C)
    task=prog.add_task("tagging", total=len(targets))
    with Live(console=C, refresh_per_second=8) as live:
        for dp,fn,base in targets:
            full=os.path.join(dp,fn); rel=os.path.relpath(dp,a.root)
            st,su,ty,cf,src=dh.classify(a,sysp,full,base,rel)
            counts[f"{st}-{su}"]+=1; conf_low+=(cf=="low")
            rows.append((full,fn,f"[{st}-{su}] {base}",st,su,ty,cf,src))
            if a.apply:
                try: os.rename(full,dh.unique_path(os.path.join(dp,f"[{st}-{su}] {base}")))
                except Exception: pass
            prog.advance(task)
            live.update(Panel.fit(prog, title=BANNER, subtitle=f"[dim]{fn[:48]}[/]", box=BOX))
    # log
    logp=os.path.join(a.root,"_doc_handler_log.csv")
    import csv
    with open(logp,"w",encoding="utf-8",newline="") as g:
        w=csv.writer(g); w.writerow(["path","old","new","stream","subject","type","conf","source"]); w.writerows(rows)
    C.print(Panel(bars(counts,len(targets)), box=BOX,
        title=f"[bold]{'APPLIED' if a.apply else 'DRY-RUN'}[/] {len(targets)} files  -  "
              f"[yellow]{conf_low} low-conf[/]", subtitle=f"log: {logp}"))

def run_move(root, dest, apply):
    n=dh.move_by_prefix(root,dest,apply)
    C.print(f"[green]{'moved' if apply else 'planned'} {n} files[/] -> {dest}")

def menu():
    C.print(Panel.fit(BANNER, subtitle="[dim]offline - subject+stream tagging[/]", box=BOX))
    while True:
        C.print("\n[bold]1[/] tag (dry-run)   [bold]2[/] tag (apply)   "
                "[bold]3[/] move by prefix   [bold]4[/] quit")
        ch=Prompt.ask(">", choices=["1","2","3","4"], default="1")
        if ch=="4": break
        root=Prompt.ask("root folder (work on a COPY)")
        if not os.path.isdir(root): C.print("[red]not a folder[/]"); continue
        if ch in ("1","2"):
            vis=Confirm.ask("use vision model for no-text PDFs?", default=True)
            fr=Prompt.ask("frontier fallback on hard 99UNS", choices=["none","claude","openai"], default="none")
            a=defaults(root, vision=vis, frontier=fr, apply=(ch=="2"))
            run_tag(a)
        elif ch=="3":
            dest=Prompt.ask("destination archive root")
            run_move(root,dest,Confirm.ask("apply the move now?", default=False))

if __name__=="__main__":
    try: menu()
    except KeyboardInterrupt: C.print("\n[dim]bye[/]")
