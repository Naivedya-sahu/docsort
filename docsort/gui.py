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

from . import config
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
            elif kind == "file":
                if payload.get("skipped"):
                    state["skipped"] += 1
                    c_skip.value = str(state["skipped"])
                feed.controls.append(_feed_row(payload))
            elif kind == "done":
                status.value = "done"
                status.color = OK
                run_btn.disabled = False
                stop_btn.disabled = True
                if state["t0"]:
                    elapsed.value = _fmt_mmss(time.time() - state["t0"])
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

    return ft.Column(
        [
            controls,
            hero,
            ft.Container(bgcolor=PANEL, border_radius=12, padding=6, expand=True, content=feed),
        ],
        spacing=14,
        expand=True,
    )


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

    # Build the Run view once and reuse it across nav switches.
    run_view = _run_view(page)

    content = ft.Container(expand=True, padding=18, content=run_view)

    def _on_nav_change(e: "ft.ControlEvent") -> None:
        idx: int = e.control.selected_index
        if idx == 0:
            content.content = run_view
        else:
            content.content = ft.Text(_SECTION_NAMES[idx], color=FG, size=18)
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
