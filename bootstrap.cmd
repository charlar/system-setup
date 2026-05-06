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
    git -C "%REPO_DIR%" pull --ff-only
) else (
    echo [setup] Cloning repository / Clonando repositorio...
    git clone %REPO_URL% "%REPO_DIR%"
)

:: ---------- Python via uv ----------
cd /d "%REPO_DIR%"
echo [setup] Ensuring Python is available / Verificando que Python este disponible...
uv python install

:: ---------- run setup ----------
echo [setup] Running setup / Ejecutando configuracion...
uv run setup.py

endlocal
pause
