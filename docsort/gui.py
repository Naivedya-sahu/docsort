#!/usr/bin/env python3
"""docsort.gui — Flet front end (visual overhaul, v0.11.0+).

Replaces the Tkinter UI with a modern Flet app. The classifier engine still
runs as a ``python -m docsort.cli ...`` subprocess via
:class:`~docsort.runcore.RunController`, so this module is presentation-only.

  docsort-gui            (or: python -m docsort.gui)
Requires the [gui] extra:  pip install "docsort[gui]"
"""
from __future__ import annotations

import os
import sys
import time

try:
    import flet as ft
except ImportError:          # CLI-only install — no flet wheel
    ft = None  # type: ignore[assignment]

from . import config, tagsio
from .cli import available_models, load_tags
from .runcore import RunController, build_run_cmd

# repo root / site-packages dir so `-m docsort.cli` resolves from subprocess
PKG_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Palette  (Discord-like dark — reused by later view modules)
# ---------------------------------------------------------------------------
BG     = "#1b1b27"
PANEL  = "#232334"
PANEL2 = "#2a2a3d"
ENTRY  = "#15151f"
FG     = "#e6e6ef"
MUTED  = "#9aa0b4"
ACCENT = "#7c5cff"
OK     = "#3ddc84"
FAIL   = "#e0715e"

# Nav section names (index matches NavigationRail selected_index)
_SECTION_NAMES = ["Run", "Tags", "Folders", "Reports", "Stats"]


# ---------------------------------------------------------------------------
# Run view
# ---------------------------------------------------------------------------

def _fmt_mmss(seconds: int) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _feed_row(p: dict) -> "ft.Control":
    """One completed-file row for the live feed."""
    if p.get("failed"):
        icon, icol = ft.Icons.ALERT_TRIANGLE if hasattr(ft.Icons, "ALERT_TRIANGLE") else ft.Icons.ERROR_OUTLINE, FAIL
    elif p.get("skipped"):
        icon, icol = ft.Icons.REMOVE_CIRCLE_OUTLINE, MUTED
    else:
        icon, icol = ft.Icons.CHECK, OK
    return ft.Row(
        [
            ft.Icon(icon, color=icol, size=16),
            ft.Text(p["name"], color=FG, size=13, expand=True,
                    no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(p["source"], color=MUTED, size=11),
            ft.Container(
                bgcolor=PANEL2, border_radius=6,
                padding=ft.Padding(left=8, top=2, right=8, bottom=2),
                content=ft.Text(p["tag"], color=ACCENT, size=11),
            ),
        ],
        spacing=10,
    )


def _pick_folder(page: "ft.Page", field: "ft.TextField") -> None:
    """Open a native directory picker and write the chosen path into *field*."""
    def on_result(e: "ft.FilePickerResultEvent") -> None:
        if getattr(e, "path", None):
            field.value = e.path
            page.update()

    fp = ft.FilePicker(on_result=on_result)
    page.overlay.append(fp)
    page.update()
    fp.get_directory_path()


def _metric(label: str, value_ctrl: "ft.Text") -> "ft.Container":
    return ft.Container(
        bgcolor=PANEL, border_radius=8, padding=10, expand=True,
        content=ft.Column([ft.Text(label, size=11, color=MUTED), value_ctrl], spacing=2),
    )


def _run_view(page: "ft.Page") -> "ft.Control":
    """Build the Run view: controls, progress hero, counters, live feed."""
    streams, subjects, _types = load_tags(config.tags_path())
    cfg = config.load_config()

    # ---- input controls ----
    folder = ft.TextField(label="Folder", color=FG, expand=True,
                          value=str(cfg.get("last_folder") or ""))
    browse = ft.IconButton(ft.Icons.FOLDER_OPEN, tooltip="Browse",
                           on_click=lambda _e: _pick_folder(page, folder))
    host = ft.TextField(label="Host (name or URL, blank = default)", color=FG, width=320)
    model = ft.Dropdown(label="Model", width=240, value="auto",
                        options=[ft.dropdown.Option("auto")])
    refresh = ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh models")
    frontier = ft.Dropdown(label="Frontier", width=160, value="none",
                           options=[ft.dropdown.Option("none"), ft.dropdown.Option("claude")])
    t_vision = ft.Switch(label="Vision", value=False)
    t_apply = ft.Switch(label="Apply (rename)", value=False)
    t_copy = ft.Switch(label="Work on a copy", value=False)
    t_misc = ft.Switch(label="Move 99UNS → misc", value=True)
    t_skip = ft.Switch(label="Skip unknown", value=False)

    # ---- progress hero ----
    pct = ft.Text("0%", size=42, weight=ft.FontWeight.W_500, color=FG)
    of_n = ft.Text("file 0 / 0", size=13, color=MUTED)
    elapsed = ft.Text("0:00", size=18, weight=ft.FontWeight.W_500, color=FG)
    remaining = ft.Text("~—", size=18, weight=ft.FontWeight.W_500, color=ACCENT)
    bar = ft.ProgressBar(value=0.0, bar_height=10, color=ACCENT, bgcolor=PANEL2)
    c_done = ft.Text("0", size=20, color=OK, weight=ft.FontWeight.W_500)
    c_skip = ft.Text("0", size=20, color=FG, weight=ft.FontWeight.W_500)
    c_fail = ft.Text("0", size=20, color=FG, weight=ft.FontWeight.W_500)
    c_tps = ft.Text("0", size=20, color=FG, weight=ft.FontWeight.W_500)

    feed = ft.ListView(expand=True, spacing=2, padding=4, auto_scroll=True)
    status = ft.Text("idle", color=MUTED)

    # verbose live log (collapsed by default — full parity with the old GUI)
    log = ft.ListView(expand=True, spacing=1, padding=6, auto_scroll=True)

    def log_line(text, color=MUTED):
        log.controls.append(ft.Text(str(text).rstrip("\n"), color=color, size=11,
                                    font_family="Consolas", selectable=True))

    state = {"t0": None, "skipped": 0}

    # ---- model refresh ----
    def do_refresh(_e=None) -> None:
        api = config.resolve_api(cfg, host.value.strip() or None)
        try:
            ms = available_models(api)
        except Exception:
            ms = []
        model.options = [ft.dropdown.Option("auto")] + [ft.dropdown.Option(m) for m in ms]
        if model.value not in {o.key for o in model.options}:
            model.value = "auto"
        page.update()

    refresh.on_click = do_refresh
    host.on_blur = do_refresh

    # ---- event handling (RunController emits from a background thread) ----
    def on_event(ev) -> None:
        kind, payload = ev

        def apply() -> None:
            if kind == "progress":
                bar.value = payload["pct"] / 100
                pct.value = f"{payload['pct']}%"
                of_n.value = f"file {payload['i']} / {payload['n']}"
                c_done.value = str(payload["done"])
                c_fail.value = str(payload["failed"])
                c_tps.value = payload["tps"] or "0"
                remaining.value = "~" + (_fmt_mmss(int(payload["eta"])) if payload["eta"].isdigit() else "—")
                if state["t0"]:
                    elapsed.value = _fmt_mmss(time.time() - state["t0"])
                log_line(f"[progress] {payload['i']}/{payload['n']} done={payload['done']} "
                         f"failed={payload['failed']} tps={payload['tps']} eta={payload['eta']}s")
            elif kind == "file":
                if payload.get("skipped"):
                    state["skipped"] += 1
                    c_skip.value = str(state["skipped"])
                feed.controls.append(_feed_row(payload))
                log_line(f"{payload['tag']} {payload['source']:14} {payload['name']}", color=FG)
            elif kind == "log":
                log_line(payload)
            elif kind == "done":
                status.value = "done"
                status.color = OK
                run_btn.disabled = False
                stop_btn.disabled = True
                if state["t0"]:
                    elapsed.value = _fmt_mmss(time.time() - state["t0"])
                log_line("[done]", color=OK)
            page.update()

        page.run_thread(apply)

    ctrl = RunController(streams, subjects, on_event=on_event)

    # ---- run / stop ----
    def start_run(_e) -> None:
        f = folder.value.strip()
        if not os.path.isdir(f):
            status.value = f"not a folder: {f}"
            status.color = FAIL
            page.update()
            return
        opts = {"host": host.value.strip(), "model": model.value, "vision": t_vision.value,
                "apply": t_apply.value, "copy": t_copy.value, "misc": t_misc.value,
                "skip_unknown": t_skip.value, "frontier": frontier.value}
        cmd = build_run_cmd(opts, python=sys.executable, folder=f)
        feed.controls.clear()
        log.controls.clear()
        state["t0"] = time.time()
        state["skipped"] = 0
        pct.value = "0%"
        of_n.value = "file 0 / 0"
        bar.value = 0.0
        c_done.value = c_fail.value = c_skip.value = "0"
        c_tps.value = "0"
        elapsed.value = "0:00"
        remaining.value = "~—"
        status.value = "running…"
        status.color = ACCENT
        run_btn.disabled = True
        stop_btn.disabled = False
        page.update()
        ctrl.start(cmd, cwd=PKG_PARENT)

    run_btn = ft.FilledButton("Run", icon=ft.Icons.PLAY_ARROW, on_click=start_run,
                              style=ft.ButtonStyle(bgcolor=ACCENT))
    stop_btn = ft.OutlinedButton("Stop", icon=ft.Icons.STOP, disabled=True,
                                 on_click=lambda _e: ctrl.stop())

    # ---- layout ----
    hero = ft.Container(
        bgcolor=PANEL, border_radius=12, padding=18,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Row([pct, of_n], spacing=10,
                               vertical_alignment=ft.CrossAxisAlignment.END),
                        ft.Row(
                            [
                                ft.Column([ft.Text("elapsed", size=11, color=MUTED), elapsed], spacing=2),
                                ft.Column([ft.Text("remaining", size=11, color=MUTED), remaining], spacing=2),
                            ],
                            spacing=22,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                bar,
                ft.Row(
                    [_metric("done", c_done), _metric("skipped", c_skip),
                     _metric("failed", c_fail), _metric("tok/s", c_tps)],
                    spacing=10,
                ),
            ],
            spacing=14,
        ),
    )

    controls = ft.Column(
        [
            ft.Row([folder, browse]),
            ft.Row([host, model, refresh, frontier], wrap=True, vertical_alignment=ft.CrossAxisAlignment.END),
            ft.Row([t_vision, t_apply, t_copy, t_misc, t_skip], wrap=True),
            ft.Row([run_btn, stop_btn, status]),
        ],
        spacing=10,
    )

    log_panel = ft.ExpansionTile(
        title=ft.Text("Log (verbose)", color=MUTED, size=12),
        expanded=False,
        controls=[ft.Container(bgcolor=ENTRY, border_radius=8, padding=4,
                               height=180, content=log)],
    )

    view = ft.Column(
        [
            controls,
            hero,
            ft.Container(bgcolor=PANEL, border_radius=12, padding=6, expand=True, content=feed),
            log_panel,
        ],
        spacing=14,
        expand=True,
    )
    view.data = folder           # expose the folder field to the Reports view
    return view


# ---------------------------------------------------------------------------
# Tags view (structured editor over tagsio)
# ---------------------------------------------------------------------------

def _tags_view(page: "ft.Page") -> "ft.Control":
    path = config.tags_path()
    text = open(path, encoding="utf-8").read()
    palette = {"STREAMS": ACCENT, "SUBJECTS": "#5b8cff", "TYPES": OK}
    cols: dict = {}

    def make_col(name: str) -> "ft.Container":
        lv = ft.ListView(expand=True, spacing=4)
        fields: list = []
        holder: dict = {}

        def mk_row(value: str) -> "ft.Row":
            tf = ft.TextField(value=value, color=FG, text_size=13, expand=True)
            row = ft.Row(
                [tf, ft.IconButton(ft.Icons.DELETE, icon_color=FAIL,
                                   on_click=lambda e: (lv.controls.remove(holder[tf]),
                                                       fields.remove(tf), page.update()))],
                spacing=4,
            )
            holder[tf] = row
            fields.append(tf)
            return row

        for it in tagsio.tag_block(text, name):
            lv.controls.append(mk_row(it))

        def add(_e):
            lv.controls.append(mk_row(""))
            page.update()

        cols[name] = fields
        return ft.Container(
            bgcolor=PANEL, border_radius=12, padding=10, expand=True,
            content=ft.Column(
                [ft.Text(name, color=palette[name], weight=ft.FontWeight.W_500),
                 lv, ft.TextButton("+ add", on_click=add)],
                spacing=8, expand=True),
        )

    col_row = ft.Row([make_col("STREAMS"), make_col("SUBJECTS"), make_col("TYPES")],
                     expand=True, spacing=10)
    status = ft.Text("", color=OK)

    def save(_e):
        new = text
        for n in ("STREAMS", "SUBJECTS", "TYPES"):
            lines = [tf.value.rstrip() for tf in cols[n] if tf.value.strip()]
            new = tagsio.replace_block(new, n, lines)
        try:
            open(path, "w", encoding="utf-8").write(new)
            status.value, status.color = "tags saved", OK
        except Exception as e:
            status.value, status.color = f"save failed: {e}", FAIL
        page.update()

    return ft.Column(
        [ft.Text("First token on each line = the code.", color=MUTED, size=12),
         col_row,
         ft.Row([ft.FilledButton("Save", on_click=save, style=ft.ButtonStyle(bgcolor=ACCENT)), status])],
        spacing=12, expand=True)


# ---------------------------------------------------------------------------
# Folders view (exclude / include → config.json)
# ---------------------------------------------------------------------------

def _folders_view(page: "ft.Page") -> "ft.Control":
    import json
    cfgp = config.config_path()
    try:
        data = json.load(open(cfgp, encoding="utf-8"))
    except Exception:
        data = {}

    def make_list(key: str, label: str, colour: str):
        items = list(data.get(key) or [])
        lv = ft.ListView(expand=True, spacing=2)

        def render():
            lv.controls.clear()
            for it in list(items):
                lv.controls.append(ft.Row(
                    [ft.Text(it, color=FG, size=12, expand=True, no_wrap=True,
                             overflow=ft.TextOverflow.ELLIPSIS),
                     ft.IconButton(ft.Icons.DELETE, icon_color=FAIL,
                                   on_click=lambda e, v=it: (items.remove(v), render(), page.update()))],
                    spacing=4))

        def add(_e):
            def on_result(ev):
                if getattr(ev, "path", None):
                    items.append(ev.path)
                    render()
                    page.update()
            fp = ft.FilePicker(on_result=on_result)
            page.overlay.append(fp)
            page.update()
            fp.get_directory_path()

        render()
        box = ft.Container(
            bgcolor=PANEL, border_radius=12, padding=10, expand=True,
            content=ft.Column(
                [ft.Text(label, color=colour, weight=ft.FontWeight.W_500), lv,
                 ft.TextButton("+ add folder", on_click=add)],
                spacing=8, expand=True))
        return box, items

    ex_box, ex_items = make_list("exclude", "Exclude", FAIL)
    in_box, in_items = make_list("include", "Include", OK)
    status = ft.Text("", color=OK)

    def save(_e):
        data["exclude"], data["include"] = list(ex_items), list(in_items)
        try:
            json.dump(data, open(cfgp, "w", encoding="utf-8"), indent=2)
            status.value, status.color = "folders saved", OK
        except Exception as e:
            status.value, status.color = f"save failed: {e}", FAIL
        page.update()

    return ft.Column(
        [ft.Text("Exclude = skip these. Include = if non-empty, ONLY these.", color=MUTED, size=12),
         ft.Row([ex_box, in_box], expand=True, spacing=10),
         ft.Row([ft.FilledButton("Save", on_click=save, style=ft.ButtonStyle(bgcolor=ACCENT)), status])],
        spacing=12, expand=True)


# ---------------------------------------------------------------------------
# Reports + Stats views
# ---------------------------------------------------------------------------

def _reports_view(page: "ft.Page", folder_getter) -> "ft.Control":
    body = ft.Text("", selectable=True, color=FG, font_family="Consolas", size=12)
    info = ft.Text("", color=MUTED, size=12)

    def load(_e=None):
        folder = (folder_getter() or "").strip()
        cands = [os.path.join(folder, "DOCSORT-REPORT.md"),
                 os.path.join(folder + "COPY", "DOCSORT-REPORT.md")]
        path = next((p for p in cands if folder and os.path.isfile(p)), None)
        if not path:
            info.value = "No DOCSORT-REPORT.md yet — run a tagging pass first."
            body.value = ""
        else:
            info.value = path
            body.value = open(path, encoding="utf-8").read()
        page.update()

    return ft.Column(
        [ft.Row([ft.FilledButton("Load report", on_click=load), info]),
         ft.Container(bgcolor=PANEL, border_radius=12, padding=12, expand=True,
                      content=ft.Column([body], scroll=ft.ScrollMode.AUTO, expand=True))],
        spacing=12, expand=True)


def _stats_view(page: "ft.Page") -> "ft.Control":
    import json
    import collections
    idx = os.path.join(config.user_dir(), "index.jsonl")
    lines = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, expand=True)
    if not os.path.isfile(idx):
        lines.controls.append(ft.Text("No runs yet — run a tagging pass first.", color=MUTED))
    else:
        runs = [json.loads(l) for l in open(idx, encoding="utf-8") if l.strip()]
        files = sum(int(r.get("n", 0) or 0) for r in runs)
        agg: "collections.Counter" = collections.Counter()
        for r in runs:
            agg.update(r.get("by") or {})
        lines.controls.append(ft.Text(f"{len(runs)} runs · {files} files tagged",
                                      color=FG, size=16, weight=ft.FontWeight.W_500))
        for k, c in agg.most_common(20):
            lines.controls.append(ft.Text(f"{k}  ×{c}", color=MUTED, size=13, font_family="Consolas"))

    return ft.Column([ft.Text("Lifetime stats", color=MUTED, size=12), lines],
                     spacing=12, expand=True)


# ---------------------------------------------------------------------------
# Flet page builder
# ---------------------------------------------------------------------------

def _build(page: "ft.Page") -> None:
    """Build the Flet UI tree and attach it to *page*."""
    page.title = "docsort"
    page.bgcolor = BG
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed=ACCENT)
    page.dark_theme = ft.Theme(color_scheme_seed=ACCENT)

    # Window minimum size (Page.window is a Window sub-object in Flet 0.85+)
    page.window.min_width = 720
    page.window.min_height = 560

    # Build the Run view once; other views are built lazily on first visit.
    run_view = _run_view(page)
    content = ft.Container(expand=True, padding=18, content=run_view)
    cache: dict = {0: run_view}

    def _folder_value() -> str:
        fld = getattr(run_view, "data", None)
        return fld.value if fld is not None else ""

    def _make_view(idx: int) -> "ft.Control":
        if idx == 1:
            return _tags_view(page)
        if idx == 2:
            return _folders_view(page)
        if idx == 3:
            return _reports_view(page, _folder_value)
        if idx == 4:
            return _stats_view(page)
        return run_view

    def _on_nav_change(e: "ft.ControlEvent") -> None:
        idx: int = e.control.selected_index
        if idx not in cache:
            cache[idx] = _make_view(idx)
        content.content = cache[idx]
        page.update()

    rail = ft.NavigationRail(
        selected_index=0,
        bgcolor=PANEL,
        indicator_color=ACCENT,
        min_width=84,
        group_alignment=-0.9,
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.PLAY_ARROW, label="Run"),
            ft.NavigationRailDestination(icon=ft.Icons.LABEL, label="Tags"),
            ft.NavigationRailDestination(icon=ft.Icons.FOLDER_OPEN, label="Folders"),
            ft.NavigationRailDestination(icon=ft.Icons.DESCRIPTION, label="Reports"),
            ft.NavigationRailDestination(icon=ft.Icons.BAR_CHART, label="Stats"),
        ],
        on_change=_on_nav_change,
    )

    page.add(
        ft.Row([rail, ft.VerticalDivider(width=1, color=PANEL2), content],
               expand=True, spacing=0)
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Launch the docsort GUI.  Called by the ``docsort-gui`` console script."""
    if ft is None:
        sys.stderr.write(
            "docsort-gui needs the GUI extra.  Install it with:\n"
            '    pip install "docsort[gui]"\n'
        )
        sys.exit(1)

    # ft.app() is deprecated since Flet 0.80 — use ft.run()
    ft.run(_build)


if __name__ == "__main__":
    main()
