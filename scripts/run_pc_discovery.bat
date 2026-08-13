@echo off
REM ============================================================
REM  PC Discovery runner — feeds bot-gated job boards into the
REM  live InternTrack DB. Run manually (double-click) or schedule
REM  it daily via Windows Task Scheduler (see README "PC discovery").
REM  Uses your residential internet, which is NOT blocked by
REM  JobDexo / Foundit / Apna / Cutshort (unlike server IPs).
REM ============================================================
setlocal

cd /d "%~dp0.."

REM Use the repo's Python if present, else the system python.
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

where %PY% >nul 2>nul
if errorlevel 1 (
    echo [pc-discovery] Python not found. Install Python 3.11+ first.
    pause
    exit /b 1
)

REM Make sure httpx + the app deps are available.
%PY% -c "import httpx" >nul 2>nul
if errorlevel 1 (
    echo [pc-discovery] Installing dependencies once...
    %PY% -m pip install -q -r requirements.txt
)

set "PYTHONPATH=src"

REM One run covering every member's domains + cities.
REM Append "--limit N" to cap how many jobs are pushed per run.
%PY% scripts\pc_discovery.py --all-members --limit 15 >> "%USERPROFILE%\pc_discovery.log" 2>&1

echo [pc-discovery] Done. See %%USERPROFILE%%\pc_discovery.log
endlocal
