@echo off
setlocal EnableDelayedExpansion

:: ============================================================
:: seed_review_events.bat
:: Interactive wrapper for backend/scripts/seed_review_events.py
:: Auto-detects DATABASE_URL from backend\.env or prompts for it.
:: ============================================================

set "SCRIPT_DIR=%~dp0"
set "PYTHON=%__PythonFallback__%"
where python >nul 2>&1 && set "PYTHON=python"

:: ── 1. Check psycopg2 ──────────────────────────────────────
%PYTHON% -c "import psycopg2" 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: psycopg2-binary is not installed.
    echo.
    echo Run this first, then re-run this script:
    echo   pip install psycopg2-binary
    echo.
    pause
    exit /b 1
)

:: ── 2. Load .env ─────────────────────────────────────────
if exist "%SCRIPT_DIR%.env" (
    for /f "usebackq eol=# delims=" %%L in ("%SCRIPT_DIR%.env") do (
        set "line=%%L"
        :: Skip blank lines and comment-only lines
        for /f "tokens1" %%F in ("!line!") do (
            if not "%%F"=="" (
                for /f "tokens=1,2 delims==" %%K in ("!line!") do (
                    endlocal
                    set "%%K=%%L"
                    setlocal EnableDelayedExpansion
                )
            )
        )
    )
)

:: ── 3. Build DATABASE_URL if not already set ──────────────
set "DB_URL=%DATABASE_URL%"

if not defined DB_URL (
    if defined SUPABASE_URL (
        :: Extract project ref: https://cyzpvltrayvpdooxgmaj.supabase.co -> cyzpvltrayvpdooxgmaj
        set "tmp=!SUPABASE_URL:https://=!"
        set "tmp=!tmp:http://=!"
        for /f "tokens=1 delims=." %%R in ("!tmp!") do set "PROJ_REF=%%R"

        if defined SUPABASE_SERVICE_KEY (
            echo.
            echo Auto-detected Supabase project: !SUPABASE_URL!
            echo NOTE: This script connects via the DIRECT database host
            echo       ^(db.!PROJ_REF!.supabase.co:5432^), not the pooler.
            echo       If your project uses a non-default region, edit the
            echo       connection string manually below.
            echo.
            set /p OK="Use direct connection db.!PROJ_REF!.supabase.co:5432? [Y/n]: "
            if /i "!OK!"=="n" goto :ask_manual

            set "DB_URL=postgresql://postgres:!SUPABASE_SERVICE_KEY!@db.!PROJ_REF!.supabase.co:5432/postgres"
            goto :run
        )
    )

    :ask_manual
    echo.
    echo ============================================================
    echo   CogniTrace Mastery Seed  -  Manual Setup
    echo ============================================================
    echo.
    echo Paste the full DATABASE_URL you copied from Supabase.
    echo.
    echo The simplest form is:
    echo   postgresql://postgres:PASSWORD@db.YOUR_REF.supabase.co:5432/postgres
    echo.
    set /p DB_URL="Full DATABASE_URL: "
    if not defined DB_URL (
        echo ERROR: DATABASE_URL is required.
        pause
        exit /b 1
    )
)

:run
:: Confirm
echo.
echo Will connect to:
echo   !DB_URL!
echo.
set /p OK="Proceed? [Y/n]: "
if /i "!OK!"=="n" exit /b 0

:: ── 4. Run the seed script ────────────────────────────────
%PYTHON% "%SCRIPT_DIR%seed_review_events.py" %*

pause
