#!/usr/bin/env python3
"""docsort.gui — Flet front end (visual overhaul, v0.11.0+).

Replaces the Tkinter UI with a modern Flet app. The classifier engine still
runs as a ``python -m docsort.cli ...`` subprocess via
:class:`~docsort.runcore.RunController` (added in a later task), so this
module is presentation-only.

  docsort-gui            (or: python -m docsort.gui)
Requires the [gui] extra:  pip install "docsort[gui]"
"""
from __future__ import annotations

import os
import sys

try:
    import flet as ft
except ImportError:          # CLI-only install — no flet wheel
    ft = None  # type: ignore[assignment]

# repo root / site-packages dir so `-m docsort.cli` resolves from subprocess
PKG_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Palette  (Discord-like dark — reused by later view modules)
# ---------------------------------------------------------------------------
BG     = "#1b1b27"
PANEL  = "#232334"
PANEL2 = "#2a2a3d"
FG     = "#e6e6ef"
MUTED  = "#9aa0b4"
ACCENT = "#7c5cff"
OK     = "#3ddc84"
FAIL   = "#e0715e"

# Nav section names (index matches NavigationRail selected_index)
_SECTION_NAMES = ["Run", "Tags", "Folders", "Reports", "Stats"]


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

    # ---- content area -------------------------------------------------
    content = ft.Container(
        expand=True,
        padding=18,
        content=ft.Text(_SECTION_NAMES[0], color=FG, size=18),
    )

    # ---- nav rail change handler -------------------------------------
    def _on_nav_change(e: "ft.ControlEvent") -> None:
        idx: int = e.control.selected_index
        content.content = ft.Text(_SECTION_NAMES[idx], color=FG, size=18)
        page.update()

    # ---- nav rail ----------------------------------------------------
    rail = ft.NavigationRail(
        selected_index=0,
        bgcolor=PANEL,
        indicator_color=ACCENT,
        min_width=84,
        group_alignment=-0.9,
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.PLAY_ARROW, label="Run"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.LABEL, label="Tags"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.FOLDER_OPEN, label="Folders"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.DESCRIPTION, label="Reports"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.BAR_CHART, label="Stats"
            ),
        ],
        on_change=_on_nav_change,
    )

    page.add(
        ft.Row(
            [
                rail,
                ft.VerticalDivider(width=1, color=PANEL2),
                content,
            ],
            expand=True,
            spacing=0,
        )
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
