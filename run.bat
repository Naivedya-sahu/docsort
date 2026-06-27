@echo off
REM ===========================================================================
REM  docsort launcher  -  works from cmd.exe AND PowerShell.
REM
REM    run.bat                         -> launch the dark GUI (folder picker)
REM    run.bat gui                     -> launch the GUI
REM    run.bat "C:\path\to\folder"     -> dry-run tag that folder (CLI)
REM    run.bat "C:\path" --apply       -> any docsort flags pass through
REM    run.bat "C:\path" --copy --apply
REM    run.bat "C:\path" --frontier claude   -> escalate hard 99UNS to haiku (your sub)
REM    run.bat --edit-tags             -> open your TAGS.md in an editor
REM
REM  Uses the repo's .venv (has pymupdf) if present, else system python.
REM  From PowerShell call it as:  .\run.bat   (or)   .\run.bat "C:\path"
REM ===========================================================================
setlocal
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

if "%~1"=="" goto :gui
if /i "%~1"=="gui" goto :gui

"%PY%" -m docsort.cli %*
goto :end

:gui
"%PY%" -m docsort.gui
goto :end

:end
endlocal
