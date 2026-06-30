"""PyInstaller / flet-pack entry point for the docsort GUI executable.

When frozen, ``sys.executable`` is this GUI exe and ``python -m docsort.cli`` is
not available, so the GUI re-invokes this same exe with a ``--run-cli`` sentinel
to run the engine in-process-as-subprocess. Route that here before the GUI.
"""
import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--run-cli":
        from docsort.cli import main as cli_main
        cli_main(sys.argv[2:])
    else:
        from docsort.gui import main
        main()
