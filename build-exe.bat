@echo off
REM ---------------------------------------------------------------------------
REM Build docsort standalone .exe files locally on Windows.
REM Mirrors .github/workflows/release.yml. Run from the repo root:
REM     build-exe.bat
REM Output: dist\docsort-gui.exe  and  dist\docsort.exe
REM Requires the repo .venv with: pip install ".[gui]" pyinstaller flet
REM ---------------------------------------------------------------------------
setlocal
set "PY=.venv\Scripts\python.exe"
set "FLET=.venv\Scripts\flet.exe"
for /f "usebackq delims=" %%v in (`%PY% -c "import docsort;print(docsort.__version__)"`) do set "VER=%%v"
if "%VER%"=="" set "VER=0.0.0"

echo.
echo === Building GUI exe (flet pack, v%VER%) ===
REM --add-data bundles docsort/data (TAGS.md, prompt, config template);
REM --paths=. lets PyInstaller find the docsort package even on an editable install.
"%FLET%" pack run_gui.py --name docsort-gui --product-name docsort --product-version %VER% -i docsort\docsort.ico -y --add-data "docsort\data;docsort\data" --pyinstaller-build-args=--paths=.
if errorlevel 1 goto :err

echo.
echo === Building CLI exe (PyInstaller) ===
"%PY%" -m PyInstaller --onefile --console --name docsort --icon docsort\docsort.ico --collect-all docsort run_cli.py
if errorlevel 1 goto :err

echo.
echo === Done ===
echo   dist\docsort-gui.exe
echo   dist\docsort.exe
endlocal
exit /b 0

:err
echo.
echo BUILD FAILED (see output above).
endlocal
exit /b 1
