import types

import pytest

flet = pytest.importorskip("flet")
import flet as ft  # noqa: E402

from docsort import gui  # noqa: E402


# Shared fixtures for this and upcoming GUI view tests in the consolidation series.
def _stub_page():
    p = types.SimpleNamespace()
    p.services = []
    p.window = types.SimpleNamespace()
    p.added = []
    p.add = lambda *a, **k: p.added.append(a)
    p.update = lambda *a, **k: None
    p.run_task = lambda *a, **k: None
    p.run_thread = lambda *a, **k: None
    return p


def _walk(control):
    yield control
    for attr in ("controls", "content"):
        val = getattr(control, attr, None)
        if val is None:
            continue
        if isinstance(val, (list, tuple)):
            for c in val:
                yield from _walk(c)
        else:
            yield from _walk(val)


def test_build_toggles_keys_and_defaults():
    toggles = gui._build_toggles()
    assert set(toggles) == {"vision", "apply", "copy", "misc", "skip"}
    assert all(isinstance(s, ft.Switch) for s in toggles.values())
    assert toggles["vision"].value is False
    assert toggles["apply"].value is False
    assert toggles["copy"].value is False
    assert toggles["misc"].value is False   # flipped: misc-quarantine now opt-in
    assert toggles["skip"].value is True    # flipped: skip-unknown now default


def test_build_opts_reads_toggle_values():
    toggles = gui._build_toggles()
    toggles["vision"].value = True
    toggles["skip"].value = False
    host = types.SimpleNamespace(value="  myhost  ")
    model = types.SimpleNamespace(value="auto")
    frontier = types.SimpleNamespace(value="claude")
    opts = gui._build_opts(host, model, toggles, frontier)
    assert opts == {
        "host": "myhost",
        "model": "auto",
        "vision": True,
        "apply": False,
        "copy": False,
        "misc": False,
        "skip_unknown": False,
        "frontier": "claude",
    }


def test_run_view_takes_shared_toggles_and_has_no_inline_switches():
    page = _stub_page()
    toggles = gui._build_toggles()
    view = gui._run_view(page, toggles)
    found_switches = [c for c in _walk(view) if isinstance(c, ft.Switch)]
    assert found_switches == [], (
        "Run view should no longer render the 5 toggle switches inline — "
        "they moved to the Tags view"
    )


def test_tags_view_renders_the_shared_toggle_objects():
    page = _stub_page()
    toggles = gui._build_toggles()
    view = gui._tags_view(page, toggles)
    found = list(_walk(view))
    for key, switch in toggles.items():
        assert any(c is switch for c in found), f"toggle '{key}' not found in Tags view tree"


def test_stats_view_embeds_folders_and_reports_sections():
    page = _stub_page()
    folder_getter = lambda: ""
    view = gui._stats_view(page, folder_getter)
    found = list(_walk(view))
    texts = [c.value for c in found if isinstance(c, ft.Text) and c.value]
    assert "Folders" in texts
    assert "Reports" in texts
    assert "Exclude" in texts   # from _folders_view
    buttons = [c.content for c in found if isinstance(c, ft.FilledButton)]
    assert "Load report" in buttons   # from _reports_view


def test_build_produces_three_tab_nav_rail():
    page = _stub_page()
    gui._build(page)
    assert page.added, "page.add was never called"
    row = page.added[0][0]
    rail = row.controls[0]
    assert [d.label for d in rail.destinations] == ["Run", "Tags", "Stats"]
