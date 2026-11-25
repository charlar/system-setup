@echo off
:: Bootstrap script for Windows CMD — installs Chocolatey, uv, git, clones the repo, and runs setup.py
setlocal EnableDelayedExpansion

set REPO_URL=https://github.com/charlar/system-setup.git
set REPO_DIR=%USERPROFILE%\system-setup

:: ---------- admin check ----------
net session >nul 2>&1
if errorlevel 1 (
    echo [setup] ERROR: Run this script as Administrator / Ejecute este script como Administrador.
    pause
    exit /b 1
)

:: ---------- Chocolatey ----------
where choco >nul 2>&1
if errorlevel 1 (
    if exist "%ProgramData%\chocolatey\bin\choco.exe" (
        set "PATH=%ProgramData%\chocolatey\bin;!PATH!"
        echo [setup] choco already installed / ya instalado
    ) else (
        echo [setup] Installing Chocolatey / Instalando Chocolatey...
        powershell -NoProfile -InputFormat None -ExecutionPolicy Bypass -Command "[System.Net.ServicePointManager]::SecurityProtocol = 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"
        set "PATH=%ProgramData%\chocolatey\bin;!PATH!"
    )
) else (
    echo [setup] choco already installed / ya instalado
)

:: ---------- git ----------
where git >nul 2>&1
if errorlevel 1 (
    echo [setup] git not found. Installing... / git no encontrado. Instalando...
    choco install git -y --no-progress
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "SYS_PATH=%%B"
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USR_PATH=%%B"
    set "PATH=!SYS_PATH!;!USR_PATH!"
) else (
    for /f "delims=" %%v in ('git --version') do echo [setup] git already installed / ya instalado: %%v
)

:: ---------- uv ----------
set UV_FOUND=0
where uv >nul 2>&1 && set UV_FOUND=1
if !UV_FOUND!==0 if exist "%USERPROFILE%\.local\bin\uv.exe"  set UV_FOUND=1
if !UV_FOUND!==0 if exist "%USERPROFILE%\.cargo\bin\uv.exe"  set UV_FOUND=1

if !UV_FOUND!==1 (
    set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;!PATH!"
    for /f "delims=" %%v in ('uv --version 2^>nul') do echo [setup] uv already installed / ya instalado: %%v
) else (
    echo [setup] uv not found. Installing... / uv no encontrado. Instalando...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "SYS_PATH=%%B"
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USR_PATH=%%B"
    set "PATH=!SYS_PATH!;!USR_PATH!;%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin"
)

:: ---------- clone / update repo ----------
if exist "%REPO_DIR%\.git" (
    echo [setup] Repository already cloned -- pulling latest / Repositorio ya clonado -- actualizando...
    rem fetch + forced checkout, not pull: works from a detached release tag, and a stray
    rem file in the clone, e.g. an untracked uv.lock, can't block it
    git -C "%REPO_DIR%" fetch origin --tags --force --quiet
    git -C "%REPO_DIR%" checkout --quiet --force -B master origin/master
) else (
    echo [setup] Cloning repository / Clonando repositorio...
    git clone %REPO_URL% "%REPO_DIR%"
)

:: Allow git to trust this directory regardless of who created it
git config --global --add safe.directory "%REPO_DIR%"

:: ---------- Python via uv ----------
cd /d "%REPO_DIR%"
echo [setup] Ensuring Python is available / Verificando que Python este disponible...
uv python install

:: ---------- install ----------
echo [setup] Installing system-setup tool / Instalando herramienta system-setup...
uv tool install . --reinstall

:: Where uv puts tool commands (normally %USERPROFILE%\.local\bin)
set "UV_BIN=%USERPROFILE%\.local\bin"
for /f "delims=" %%p in ('uv tool dir --bin 2^>nul') do set "UV_BIN=%%p"
set "PATH=!UV_BIN!;!PATH!"

:: ---------- desktop app or command line ----------
:: (no goto/labels: this file may arrive with LF line endings, where cmd mishandles labels)
:: The desktop app inherits this window's admin rights and up-to-date PATH, so no restart.
echo.
echo What next? / Que sigue?
echo   [1] Desktop app / Aplicacion de escritorio  (recommended / recomendado)
echo   [2] Command line / Linea de comandos
choice /c 12 /n /t 30 /d 1 /m "Choice / Opcion [1]: "
if errorlevel 2 (
    echo [setup] Running setup / Ejecutando configuracion...
    system-setup
    endlocal
    pause
) else (
    echo [setup] Opening System Setup... / Abriendo System Setup...
    echo [setup] Later: Start menu - System Setup / Despues: menu Inicio - System Setup
    start "" "!UV_BIN!\system-setupg.exe"
    timeout /t 4 /nobreak >nul
    endlocal
)
