@echo off
:: One-time fix for installs stuck on v0.1.0: its updater says a new version is
:: available but never installs it (a stray uv.lock in the clone blocks git pull).
:: Moves %USERPROFILE%\system-setup to the newest release and reinstalls.
:: No administrator rights needed. Newer versions update themselves.
:: (no goto/labels: this file may arrive with LF line endings, where cmd mishandles labels)
setlocal EnableDelayedExpansion

set REPO_DIR=%USERPROFILE%\system-setup
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"

set ERR=
if not exist "%REPO_DIR%\.git" set ERR=System Setup is not installed - run bootstrap.cmd instead / System Setup no esta instalado - ejecute bootstrap.cmd
if not defined ERR (
    tasklist /fi "imagename eq system-setupg.exe" 2>nul | find /i "system-setupg.exe" >nul && set ERR=Close System Setup first / Cierre System Setup primero
    tasklist /fi "imagename eq system-setup.exe" 2>nul | find /i "system-setup.exe" >nul && set ERR=Close System Setup first / Cierre System Setup primero
)

if not defined ERR (
    git config --global --add safe.directory "%REPO_DIR%"
    echo [fix] Fetching releases / Descargando versiones...
    git -C "%REPO_DIR%" fetch origin --tags --force --quiet || set ERR=git fetch failed / fallo git fetch
)

set TAG=
if not defined ERR (
    for /f "delims=" %%t in ('git -C "%REPO_DIR%" tag --list "v*" --sort=-v:refname') do if not defined TAG set TAG=%%t
    if not defined TAG set ERR=No release found / No se encontro ninguna version
)

if not defined ERR (
    echo [fix] Switching to !TAG! / Cambiando a !TAG!...
    git -C "%REPO_DIR%" -c advice.detachedHead=false checkout --quiet --force --detach !TAG! || set ERR=git checkout failed / fallo git checkout
)

if not defined ERR (
    echo [fix] Reinstalling / Reinstalando...
    uv tool install "%REPO_DIR%" --reinstall || set ERR=uv tool install failed / fallo uv tool install
)

echo.
if defined ERR (
    echo [fix] ERROR: !ERR!
) else (
    echo [fix] Done - System Setup is now !TAG! / Listo - System Setup ahora es !TAG!
)
endlocal
pause
